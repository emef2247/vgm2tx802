#!/usr/bin/env python3
"""Audio-driven DX7II/TX802 rhythm candidates; no OPLL patch-table extraction."""
import argparse
import csv
import hashlib
import itertools
import json
import math
import struct
import subprocess
from pathlib import Path

import numpy as np
import calibrate_tx802_presets as cal
from tx802_voices import velocity

FAMILIES = ('BD', 'SD', 'TOM', 'CYM', 'HH')
BITS = dict(zip(FAMILIES, (16, 8, 4, 2, 1)))
# Authored control state, also exercised by the public rhythm_only_test02 fixture.
# These are performance registers, not ROM instrument parameters.
PITCHES = {6: (288, 2), 7: (336, 2), 8: (448, 0)}
ANCHORS = {'BD': 109.2, 'SD': 250., 'TOM': 42.5, 'CYM': 1000., 'HH': 1000.}
EXTRA_FIELDS = ['rhythm_family', 'reference_note', 'reference_hz']
FIELDS = cal.FIELDS + EXTRA_FIELDS
BAND_EDGES = np.r_[0., np.geomspace(40., 20000., 65), 24000.]
WINDOWS = ((0., .015), (.015, .04), (.04, .10), (.10, .25), (.25, .50))


def wait(samples):
    result = bytearray()
    while samples:
        n = min(samples, 65535)
        result.extend(b'\x61' + struct.pack('<H', n))
        samples -= n
    return bytes(result)


def reference_bytes(family, *, gate_samples, pre_samples=4410,
                    tail_samples=35280, attenuation=0, partner_shift=0):
    if family not in BITS or not 0 <= attenuation <= 15:
        raise ValueError('Unknown rhythm family or attenuation')
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0
           for n in (gate_samples, pre_samples, tail_samples)) or not gate_samples:
        raise ValueError('Reference times must be nonnegative integer source samples with a positive gate')
    reg = lambda a, v: bytes((0x51, a, v))
    commands = reg(14, 32)
    for ch, (fnum, block) in PITCHES.items():
        # Perturb the partner ch7 only in reserved interaction tests.
        fnum = max(1, min(511, fnum + (partner_shift if ch == 7 else 0)))
        commands += reg(0x10 + ch, fnum & 255) + reg(0x20 + ch, block * 2 + (fnum >> 8))
    commands += reg(0x36, attenuation) + reg(0x37, attenuation * 17) + reg(0x38, attenuation * 17)
    commands += wait(pre_samples) + reg(14, 32 | BITS[family])
    commands += wait(gate_samples) + reg(14, 32) + wait(tail_samples) + b'\x66'
    header = bytearray(0x100)
    header[:4] = b'Vgm '
    for offset, value in ((8, 0x170), (0x10, cal.CLOCK),
                          (0x18, pre_samples + gate_samples + tail_samples), (0x34, 0xcc)):
        struct.pack_into('<I', header, offset, value)
    data = header + commands
    struct.pack_into('<I', data, 4, len(data) - 4)
    return bytes(data)


def source_case(root, sim, family, label, *, gate=.12, pre=.1,
                tail=.8, attenuation=0, partner_shift=0):
    identity = family + '_' + label
    source, wav = root / (identity + '.vgm'), root / (identity + '.wav')
    samples = dict(gate_samples=round(gate * 44100), pre_samples=round(pre * 44100),
                   tail_samples=round(tail * 44100))
    source.write_bytes(reference_bytes(family, attenuation=attenuation,
                                      partner_shift=partner_shift, **samples))
    result = subprocess.run([str(sim), str(source), '--output', str(wav),
                             '--sample-rate', str(cal.RATE)], capture_output=True, text=True)
    (root / (identity + '.render.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('IKAOPLL reference failed: ' + identity)
    hz = ANCHORS[family]
    note = round(69 + 12 * math.log2(hz / 440))
    return dict(id=identity, family=family, note=note, hz=hz,
                gate=samples['gate_samples'] / 44100, pre=samples['pre_samples'] / 44100,
                tail=samples['tail_samples'] / 44100, velocity=velocity(attenuation),
                attenuation=attenuation, partner_shift=partner_shift,
                source=str(source), file=str(wav), **samples)


def features(path, case):
    target_frames = round(case['pre'] * cal.RATE) + round(case['gate'] * cal.RATE) + round(case['tail'] * cal.RATE)
    # IKAOPLL emits floor(total VGM samples * output rate / 44100); the probe
    # host rounds each scheduling interval. Validate each contract explicitly.
    source_frames = ((case['pre_samples'] + case['gate_samples'] + case['tail_samples']) * cal.RATE // 44100
                     if 'pre_samples' in case else target_frames)
    frames = source_frames if str(Path(path).resolve()) == str(Path(case.get('file', '')).resolve()) else target_frames
    data = cal.audio(path, frames)
    start = round(case['pre'] * cal.RATE)
    hit = data[start:]
    if len(hit) < round(.5 * cal.RATE):
        raise ValueError('Percussion analysis needs at least 500 ms after onset')
    # Absolute, onset-aligned 5ms RMS: no best-window or per-voice normalization.
    size = 240
    analysis_frames = min(source_frames, target_frames) - start
    envelope = np.array([np.sqrt(np.mean(hit[i:i+size] ** 2))
                         for i in range(0, analysis_frames-size+1, size)])
    bands, flatness, concentration = [], [], []
    for left, right in WINDOWS:
        section = hit[round(left*cal.RATE):round(right*cal.RATE)]
        fft_size = max(8192, 1 << (len(section)-1).bit_length())
        power = np.abs(np.fft.rfft(section * np.hanning(len(section)), n=fft_size)) ** 2
        freqs = np.fft.rfftfreq(fft_size, 1/cal.RATE)
        bands.append(np.histogram(freqs, bins=BAND_EDGES, weights=power)[0])
        audible = power[(freqs >= 80) & (freqs < 16000)]
        flatness.append(float(np.exp(np.mean(np.log(audible + 1e-20))) / max(np.mean(audible), 1e-20)))
        concentration.append(float(np.max(audible) / max(audible.sum(), 1e-20)))
    # Silence/noisy-tail checks are retained even when the aggregate score improves.
    peak_env = float(envelope.max())
    active = np.flatnonzero(envelope > max(1e-6, peak_env * .01))
    return dict(rms=float(np.sqrt(np.mean(hit ** 2))), envelope=envelope,
                bands=np.array(bands), flatness=np.array(flatness), concentration=np.array(concentration),
                peak=float(np.max(np.abs(data))), tail_rms=float(np.sqrt(np.mean(hit[-4800:] ** 2))),
                decay_40db_seconds=float((active[-1]+1)*.005) if len(active) else 0.,
                capture_truncated=bool(len(active) and active[-1] >= len(envelope)-2))


def distance(target, reference, gain):
    if gain <= 0 or not math.isfinite(gain):
        raise ValueError('Positive finite fixed gain required')
    if reference['rms'] < 1e-7:
        raise ValueError('Silent rhythm reference')
    for item in (target, reference):
        if not all(np.all(np.isfinite(item[k])) for k in ('rms', 'envelope', 'bands', 'flatness', 'concentration')):
            raise ValueError('Nonfinite rhythm features')
    if target['envelope'].shape != reference['envelope'].shape:
        raise ValueError('Different percussion analysis durations')
    if target['rms'] < 1e-8:
        return dict(score=1e6, amplitude=1e6, envelope=0., spectrum=0., flatness=0., ringing=0.)
    amplitude = .35 * math.log2(target['rms'] * gain / reference['rms']) ** 2
    norm = max(float(reference['envelope'].max()), 1e-8)
    envelope = 3 * float(np.mean(((target['envelope']*gain-reference['envelope'])/norm) ** 2))
    # Per-window energy weights preserve late ringing without comparing noise phase.
    weights = reference['bands'].sum(axis=1)
    weights = np.maximum(weights / max(weights.max(), 1e-20), .03)
    t = target['bands'] / np.maximum(target['bands'].sum(axis=1, keepdims=True), 1e-20)
    r = reference['bands'] / np.maximum(reference['bands'].sum(axis=1, keepdims=True), 1e-20)
    spectrum = 4 * float(np.average(np.sum((np.sqrt(t)-np.sqrt(r))**2, axis=1), weights=weights))
    flatness = .5 * float(np.average((np.log10(target['flatness']+1e-7)-np.log10(reference['flatness']+1e-7))**2, weights=weights))
    ringing = 2 * float(np.average(np.maximum(0., target['concentration']-reference['concentration'])**2, weights=weights))
    return dict(score=amplitude+envelope+spectrum+flatness+ringing,
                amplitude=amplitude, envelope=envelope, spectrum=spectrum, flatness=flatness, ringing=ringing)


def ratio_fields(ratio):
    if ratio < 1:
        return 0, max(0, min(99, round((ratio/.5-1)*100)))
    coarse = min(31, int(ratio))
    return coarse, max(0, min(99, round((ratio/coarse-1)*100)))


def seed_row(family):
    row = cal.base_row('OPLL ' + family)
    row.update(voice=16+FAMILIES.index(family), source_preset=0, rhythm_family=family,
               reference_note=round(69+12*math.log2(ANCHORS[family]/440)), reference_hz=ANCHORS[family])
    for op in range(1, 7):
        for field, value in dict(R1=99, R2=60, R3=99, R4=70, L1=99, L2=0, L3=0,
                                 L4=0, OL=0, KVS=0).items():
            row[f'OP{op}_{field}'] = value
    row.update(OP5_OL=87, OP5_KVS=7, OP6_OL=75, OP6_COARSE=2)
    return row


def structures(seed):
    family = seed['rhythm_family']
    ratios = (.5, 1., 2., 3.) if family in ('BD', 'TOM') else (1., 2.73, 7.13, 15.37)
    for ratio, feedback, pairs in itertools.product(ratios, (0, 5, 7), (1, 3)):
        row = dict(seed, FB=feedback)
        for i, (car, mod) in enumerate(((5, 6), (3, 4), (1, 2))):
            enabled = i < pairs
            carrier_ratio = (1., 2.73, 5.19)[i]
            row[f'OP{car}_COARSE'], row[f'OP{car}_FINE'] = ratio_fields(carrier_ratio)
            row[f'OP{mod}_COARSE'], row[f'OP{mod}_FINE'] = ratio_fields(ratio)
            row[f'OP{car}_OL'] = (87, 77, 69)[i] if enabled else 0
            row[f'OP{car}_KVS'] = 7
            row[f'OP{mod}_OL'] = 85 if enabled else 0
        yield row


def envelopes(parents):
    for parent in parents:
        for rate, mod_rate in itertools.product((40, 55, 70, 85), (45, 75)):
            row = dict(parent)
            for op in range(1, 7):
                row[f'OP{op}_R2'] = rate if op % 2 else mod_rate
                row[f'OP{op}_R4'] = rate if op % 2 else mod_rate
            yield row


def levels(parents):
    for parent in parents:
        for carrier, mod in itertools.product((-12, -6, 0, 6), (-12, 0, 12)):
            row = dict(parent)
            for op in range(1, 7):
                if row[f'OP{op}_OL']:
                    row[f'OP{op}_OL'] = max(0, min(99, row[f'OP{op}_OL'] + (carrier if op % 2 else mod)))
            yield row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--outdir', type=Path, required=True)
    p.add_argument('--families', nargs='+', choices=FAMILIES, default=list(FAMILIES))
    p.add_argument('--texed', type=Path, default=cal.ROOT.parent/'texed')
    p.add_argument('--ikaopll', type=Path, default=cal.ROOT.parent/'IKAOPLL-verilator/build/obj_dir/ikaopll_sim')
    a = p.parse_args()
    out = a.outdir.resolve(); out.mkdir(parents=True, exist_ok=True)
    dirs = {k: out/k for k in ('source', 'packets', 'waves')}
    for directory in dirs.values(): directory.mkdir(exist_ok=True)
    gain = json.loads((cal.ROOT/'data/tx802/OPLL_DX7II_calibration.json').read_text())['gain_anchor']['correction']
    config = dict(families=a.families, clock_hz=cal.CLOCK, rate=cal.RATE, raw_target_gain=.25,
                  fixed_gain_correction=gain, per_voice_normalization=False, training_gates=[.08, .3],
                  reserved_cases=['short45ms', 'medium190ms', 'attenuation4', 'preroll173ms', 'partner_ch7_shift47'],
                  source_pitch_state=PITCHES, reset='fresh simulator process for each case',
                  seed='authored generic decaying three-pair FM palette; no instrument-table extraction',
                  voice_slots='1-based 16..20', allocation='rhythm-only; mixed routing deferred by owner',
                  ikaopll_sha256=hashlib.sha256(a.ikaopll.read_bytes()).hexdigest(),
                  texed_commit=subprocess.check_output(['git','-c',f'safe.directory={a.texed.resolve()}',
                      '-C',str(a.texed.resolve()),'rev-parse','HEAD'], text=True).strip())
    (out/'configuration.json').write_text(json.dumps(config, indent=2)+'\n')
    trials, metrics, validation, selected, selections = [], [], [], [], {}
    def render(label, voices, cases):
        job, report = out/(label+'.job.json'), out/(label+'.render.json')
        job.write_text(json.dumps(dict(rate=cal.RATE, gain=.25, voices=voices, cases=cases,
                                       output=str(dirs['waves']), report=str(report)), indent=2)+'\n')
        subprocess.run(['npm','exec','--yes','--package=node@24','--','node',
            str(a.texed.resolve()/'texed-ts/node_modules/tsx/dist/cli.mjs'),
            str(cal.ROOT/'tools/texed_calibration_batch.mjs'), str(a.texed.resolve()), str(job)],
            cwd=a.texed/'texed-ts', check=True)
        return json.loads(report.read_text())['results']
    for family in a.families:
        cases = [source_case(dirs['source'], a.ikaopll.resolve(), family, f'train{i}', gate=g)
                 for i,g in enumerate(config['training_gates'])]
        refs = {c['id']: features(c['file'], c) for c in cases}
        candidates, ranking, seen = {}, {}, set()
        def evaluate(stage, rows):
            voices, ids = [], []
            for row in rows:
                signature = json.dumps(row, sort_keys=True)
                if signature in seen: continue
                seen.add(signature)
                identity = f'{family}_{stage}_{len(candidates):04d}'
                candidates[identity] = dict(row); ids.append(identity)
                voices.append(cal.emit_voice(dirs['packets'], identity, row))
                trials.append(dict(trial=identity, stage=stage, **row))
            if not ids: return
            print(f'{family} {stage}: {len(ids)} candidates x {len(cases)} cases', flush=True)
            results = render(f'{family}_{stage}', voices, cases)
            for identity in ids:
                values, valid = [], True
                for case in cases:
                    item = next(x for x in results if x['voice']==identity and x['case']==case['id'])
                    target = features(item['file'], case)
                    parts = distance(target, refs[case['id']], gain)
                    valid = valid and not item['clipped'] and target['rms'] >= 1e-8
                    values.append(parts['score'])
                    metrics.append(dict(family=family, trial=identity, stage=stage, case=case['id'], **parts,
                        peak=item['peak'], clipped=item['clipped'], tail_rms=target['tail_rms']*gain,
                        reference_tail_rms=refs[case['id']]['tail_rms'],
                        capture_truncated=target['capture_truncated'], file=item['file']))
                ranking[identity] = float(np.mean(values)+.25*max(values)) if valid else math.inf
            cal.write_csv(out/'trials.csv', trials, ['trial', 'stage']+FIELDS)
            cal.write_csv(out/'training_metrics.csv', metrics, list(metrics[0]))
            print(f'{family} {stage}: best {min(ranking.values()):.5f}', flush=True)
        seed = seed_row(family)
        evaluate('seed', [seed]); seed_id = next(iter(candidates))
        evaluate('structure', structures(seed))
        def parents():
            result = [candidates[k] for k in sorted(ranking, key=ranking.get) if math.isfinite(ranking[k])][:3]
            if not result:
                raise ValueError('No audible, unclipped rhythm candidate survived: '+family)
            return result
        evaluate('envelope', envelopes(parents()))
        evaluate('level', levels(parents()))
        best = min(ranking, key=ranking.get)
        if not math.isfinite(ranking[best]):
            raise ValueError('No audible, unclipped rhythm selection: '+family)
        selected.append(candidates[best])
        selections[family] = dict(trial=best, seed_trial=seed_id, seed_score=ranking[seed_id],
                                  selected_score=ranking[best], candidates=len(candidates),
                                  changes={k: [seed[k], candidates[best][k]] for k in FIELDS if seed[k]!=candidates[best][k]})
        # Freeze the choice before rendering any reserved reference/candidate cases.
        (out/'selection.json').write_text(json.dumps(selections, indent=2)+'\n')
        cal.write_csv(out/'OPLL_DX7II_rhythm.csv', selected, FIELDS)
        reserved = [source_case(dirs['source'], a.ikaopll.resolve(), family, label, **kw) for label,kw in (
            ('short45ms', dict(gate=.045)), ('medium190ms', dict(gate=.19)),
            ('attenuation4', dict(gate=.19, attenuation=4)),
            ('preroll173ms', dict(gate=.19, pre=.173)),
            ('partner_ch7_shift47', dict(gate=.19, partner_shift=47)))]
        vr = {c['id']: features(c['file'], c) for c in reserved}
        rendered = render(f'{family}_reserved', [cal.emit_voice(dirs['packets'], k, candidates[k])
                                                for k in dict.fromkeys((seed_id,best))], reserved)
        for item in rendered:
            case = next(c for c in reserved if c['id']==item['case'])
            target = features(item['file'], case)
            validation.append(dict(family=family, role='seed' if item['voice']==seed_id else 'selected',
                trial=item['voice'], case=case['id'], **distance(target, vr[case['id']], gain),
                clipped=item['clipped'], peak=item['peak'], tail_rms=target['tail_rms']*gain,
                reference_tail_rms=vr[case['id']]['tail_rms'], capture_truncated=target['capture_truncated'],
                reference_capture_truncated=vr[case['id']]['capture_truncated'], file=item['file']))
        cal.write_csv(out/'validation_metrics.csv', validation, list(validation[0]))
        cal.write_csv(out/'OPLL_DX7II_rhythm.csv', selected, FIELDS)
    summary = dict(configuration=config, selections=selections, reserved_used_for_selection=False,
                   validation=validation, limitations=['experimental FM approximation, not TX802 hardware proof',
                   'five separate voices; no kit/performance SysEx', 'no source ROM parameter extraction',
                   'no rapid-retrigger/overlap or song-level acceptance yet',
                   'reference context changes are not automatically mapped to target pitch'])
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    print(json.dumps(selections, indent=2), flush=True)


if __name__ == '__main__':
    main()
