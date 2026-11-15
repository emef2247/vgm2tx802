#!/usr/bin/env python3
"""Offline Texed reference rendering of actual generated SMF; no source projection changes."""
import argparse
import csv
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'py'))
from tx802_midi import decode_smf


def midi_job(data, rate=48000, omit_drums=False):
    decoded = decode_smf(data)
    ordered = []
    end = 0
    for track, records in enumerate(decoded['tracks']):
        port = 0
        for order, (tick, raw) in enumerate(records):
            end = max(end, tick)
            if raw[:2] == bytes((255, 0x21)):
                port = raw[-1]
            elif raw[:2] == bytes((255, 0x51)):
                ordered.append((tick, track, order, port, raw))
            elif raw[0] < 0xf0:
                ordered.append((tick, track, order, port, raw))
            elif raw[0] == 0xf0:
                raise ValueError('Embedded SysEx is not supported by this comparison host')
    ordered.sort(key=lambda x: x[:3])
    tempo, last, time = 500000, 0, Fraction(0)
    events, omitted = [], 0
    for tick, track, order, port, raw in ordered:
        time += Fraction((tick-last)*tempo, decoded['ppq']*1000000)
        last = tick
        if raw[0] == 255:
            tempo = int.from_bytes(raw[-3:], 'big')
            if tempo == 0:
                raise ValueError('Zero MIDI tempo')
            continue
        channel = raw[0] & 15
        if channel == 9 and omit_drums:
            omitted += 1
            continue
        if port not in (0, 1) or not 0 <= channel < 8:
            raise ValueError('Only two TX802 ports, channels 1..8; use --omit-drums for explicit external rhythm omission')
        kind = {0x80:'note_off',0x90:'note_on',0xb0:'cc',0xc0:'program',0xd0:'aftertouch',0xe0:'bend'}.get(raw[0]&0xf0)
        if kind is None:
            raise ValueError('Unsupported channel event in reference host')
        a, b = raw[1], raw[2] if len(raw)>2 else 0
        if kind == 'note_on' and b == 0:
            kind = 'note_off'
        events.append(dict(frame=round(time*rate),track=track,port=port,channel=channel,kind=kind,a=a,b=b))
    time += Fraction((end-last)*tempo, decoded['ppq']*1000000)
    return dict(events=events, end_frame=round(time*rate), omitted_drum_events=omitted,
                ordering='MIDI tick, track index, encoded within-track order')


def validate_sysex(data):
    # Deliberately accept standard Yamaha voice/AMEM bulk packets only.
    # Performance-only or editor-specific pseudo-VCED is not a voice bank.
    offset = 0
    while offset < len(data):
        if data[offset:offset+2] != bytes((0xf0,0x43)) or offset+8 > len(data):
            raise ValueError('Expected Yamaha bulk voice SysEx')
        if data[offset+2] > 15 or data[offset+3] not in (0,9):
            raise ValueError('Only the existing Yamaha VCED and VMEM bulk forms are accepted')
        size = data[offset+4]*128+data[offset+5]
        expected = {0:155,6:1120,9:4096}[data[offset+3]]
        stop = offset+size+8
        if size != expected or stop > len(data) or data[stop-1] != 0xf7:
            raise ValueError('Invalid Yamaha voice bulk size')
        payload = data[offset+6:stop-2]
        if any(x>127 for x in data[offset+2:stop-1]) or (sum(payload)+data[stop-2])&127:
            raise ValueError('Invalid Yamaha payload or checksum')
        # Packed VMEM operators retain eight literal EG values at each 17-byte block.
        if data[offset+3] == 9:
            for voice in range(32):
                for op in range(6):
                    if any(x>99 for x in payload[voice*128+op*17:voice*128+op*17+11]):
                        raise ValueError('Packed Yamaha EG/scaling parameter exceeds 99')
        elif data[offset+3] == 0:
            limits = ([99]*11+[3,3,7,3,7,99,1,31,99,14])*6
            limits += [99]*8+[31,7,1,99,99,99,99,1,5,7,48]+[127]*10
            if any(value>limit for value,limit in zip(payload,limits)):
                raise ValueError('Unpacked Yamaha parameter is outside its documented range')
        offset = stop
    if offset == 0:
        raise ValueError('Empty voice SysEx')


def load_voices(path):
    if path is None:
        return []
    rows = []
    seen = set()
    for row in csv.DictReader(path.open(encoding='utf-8-sig', newline='')):
        bank = row['bank'].upper(); voice = int(row['voice'])
        if bank not in ('I','C','A','B') or not 1 <= voice <= 64 or (bank, voice) in seen:
            raise ValueError('Voice CSV requires unique I/C/A/B, voice 1..64')
        syx = (path.parent / row['syx']).resolve()
        if not syx.is_file():
            raise FileNotFoundError(syx)
        program = int(row.get('program') or 0)
        library_bank = row.get('library_bank') or 'internalA'
        if not 0 <= program < 32 or library_bank not in ('internalA','internalB','cartridgeA','cartridgeB'):
            raise ValueError('Texed source slot requires library_bank and program 0..31')
        validate_sysex(syx.read_bytes())
        rows.append(dict(bank=bank,voice=voice,syx=str(syx),program=program,library_bank=library_bank,
                         sha256=hashlib.sha256(syx.read_bytes()).hexdigest()))
        seen.add((bank,voice))
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('midi', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--texed', type=Path, default=ROOT.parent/'texed')
    p.add_argument('--voices', type=Path, help='CSV: bank,voice,syx,library_bank,program')
    p.add_argument('--init-voice', action='store_true', help='Explicit plumbing check; NOT a musical comparison')
    p.add_argument('--omit-drums', action='store_true')
    p.add_argument('--rate', type=int, choices=(44100,48000), default=48000)
    p.add_argument('--tail', type=float, default=1)
    p.add_argument('--gain', type=float, default=0.25, help='Fixed reference gain; no automatic normalization')
    p.add_argument('--pitch-bend-range', type=int, choices=range(1,13), default=12)
    args = p.parse_args(argv)
    if not args.voices and not args.init_voice:
        p.error('--voices is required; --init-voice is only for a plumbing check')
    if args.voices and args.init_voice:
        p.error('Choose --voices or --init-voice')
    if any(not math.isfinite(v) or v < 0 for v in (args.gain,args.tail)):
        p.error('Gain and tail must be finite and nonnegative')
    if args.out.suffix.lower() != '.wav':
        p.error('--out must be a WAV path')
    if args.out.resolve() == args.midi.resolve():
        p.error('WAV must not overwrite input MIDI')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = args.midi.read_bytes()
    job = midi_job(payload,args.rate,args.omit_drums)
    job.update(output=str(args.out.resolve()),rate=args.rate,frames=job['end_frame']+round(args.tail*args.rate),
               gain=args.gain,bend_range=args.pitch_bend_range,voices=load_voices(args.voices),init_voice=args.init_voice,
               midi_sha256=hashlib.sha256(payload).hexdigest(),tail_seconds=args.tail)
    job_path = args.out.with_suffix('.job.json')
    job_path.write_text(json.dumps(job,indent=2)+'\n',encoding='utf-8')
    texed = args.texed.resolve()
    runner = texed/'texed-ts/node_modules/tsx/dist/cli.mjs'
    if not runner.is_file():
        p.error('Install Texed dependencies first; see docs/audio_comparison.md')
    cmd = ['npm','exec','--yes','--package=node@24','--','node',str(runner),str(ROOT/'tools/texed_render.mjs'),str(texed),str(job_path.resolve())]
    subprocess.run(cmd,check=True,cwd=texed/'texed-ts')
    report_path = Path(str(args.out)+'.render.json')
    report = json.loads(report_path.read_text())
    report.update(midi_sha256=job['midi_sha256'],voice_sources=job['voices'],omitted_drum_events=job['omitted_drum_events'],
                  ordering=job['ordering'],tail_seconds=args.tail,
                  texed_commit=subprocess.check_output(['git','-c',f'safe.directory={texed}','-C',str(texed),'rev-parse','HEAD'],text=True).strip())
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
