"""Explicit experimental rhythm-only FM projection, independent of GM/RX21."""
import csv
from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path

from tx802_midi import MidiRecord, encode_smf
from tx802_voices import velocity

FAMILIES = ('BD', 'SD', 'TOM', 'CYM', 'HH')


def load_rhythm_profile(path):
    with Path(path).open(encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    result = {}
    for row in rows:
        family = row['rhythm_family']
        if family not in FAMILIES or family in result:
            raise ValueError('Unknown or duplicate rhythm family')
        voice, note, hz = int(row['voice']), int(row['reference_note']), float(row['reference_hz'])
        if not 1 <= voice <= 32 or not 0 <= note <= 127 or not math.isfinite(hz) or hz <= 0:
            raise ValueError('Invalid rhythm voice, reference note or frequency')
        semitones = 69 + 12*math.log2(hz/440) - note
        if abs(semitones) >= 12:
            raise ValueError('Rhythm reference pitch exceeds the configured bend range')
        result[family] = dict(voice=voice, note=note, hz=hz,
                              bend=max(0,min(16383,round(8192+8192*semitones/12))))
    if set(result) != set(FAMILIES):
        raise ValueError('Rhythm profile requires all five families')
    if len({p['voice'] for p in result.values()}) != 5:
        raise ValueError('Each rhythm family needs its own voice slot')
    return result


@dataclass(frozen=True)
class RhythmProjection:
    data: bytes
    hits: tuple
    report: dict

    def dump(self, outdir, stem):
        outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
        (outdir/(stem+'.mid')).write_bytes(self.data)
        (outdir/(stem+'.rhythm.json')).write_text(json.dumps(self.report,indent=2)+'\n',encoding='utf-8')
        with (outdir/(stem+'.rhythm.hits.csv')).open('w',newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f,fieldnames=list(self.hits[0]))
            writer.writeheader();writer.writerows(self.hits)


def project_rhythm(performance, profiles, *, missing_gate_samples=5512):
    if isinstance(missing_gate_samples,bool) or not isinstance(missing_gate_samples,int) or missing_gate_samples < 1:
        raise ValueError('Missing-stop gate must be a positive integer source-sample duration')
    devices = {d.device_id:d for d in performance.devices}
    drums = [d for d in performance.percussion if devices[d.device_id].chip=='opll']
    if not drums:
        raise ValueError('No observed OPLL percussion available')
    if len({d.device_id for d in drums}) > 1:
        raise ValueError('Rhythm-only audition currently requires one OPLL source device')
    if any(d.instrument_family not in FAMILIES for d in drums):
        raise ValueError('Unknown OPLL percussion family')
    tick = lambda n: round(Fraction(n*960,44100))  # PPQ480 / 120BPM
    records, hits, losses = [], [], []
    end = tick(performance.end_sample)
    for channel, family in enumerate(FAMILIES):
        profile = profiles[family]; track = channel+1
        messages = ((0xb0|channel,0,0), (0xb0|channel,32,0),
                    (0xc0|channel,profile['voice']-1), (0xb0|channel,7,100),
                    (0xb0|channel,11,127),
                    (0xe0|channel,profile['bend']&127,profile['bend']>>7))
        for order, message in enumerate(messages,20):
            records.append(MidiRecord(0,track,order,bytes(message)))
        events = sorted((d for d in drums if d.instrument_family==family),key=lambda d:d.start_sample)
        cursor = 0
        for i, event in enumerate(events):
            if not 0 <= event.start_sample <= performance.end_sample or (event.stop_sample is not None and
                    not event.start_sample <= event.stop_sample <= performance.end_sample):
                raise ValueError('Percussion event outside source timeline')
            initial = [v for at,v in event.volume_curve if at <= event.start_sample]
            if not initial or initial[-1] is None or not 0 <= initial[-1] <= 15:
                raise ValueError('Unknown initial rhythm attenuation: '+event.event_id)
            requested_start = tick(event.start_sample)
            start = max(requested_start,cursor)
            source_stop = event.stop_sample
            requested_stop = tick(source_stop if source_stop is not None else event.start_sample+missing_gate_samples)
            stop = max(start+1,requested_stop)
            if i+1 < len(events):
                stop = min(stop,max(start+1,tick(events[i+1].start_sample)))
            if start != requested_start:
                losses.append(dict(kind='subtick_hit_displaced',source_id=event.event_id,ticks=start-requested_start))
            if stop != requested_stop:
                losses.append(dict(kind='gate_shortened_or_minimum_tick',source_id=event.event_id,requested_tick=requested_stop,target_tick=stop))
            if source_stop is None:
                losses.append(dict(kind='unobserved_stop_uses_target_gate',source_id=event.event_id,samples=missing_gate_samples))
            if len(event.volume_curve)>1:
                losses.append(dict(kind='internal_volume_curve_retained_only_in_native',source_id=event.event_id))
            note = profile['note']; level = velocity(initial[-1])
            records += [MidiRecord(start,track,60,bytes((0x90|channel,note,level))),
                        MidiRecord(stop,track,10,bytes((0x80|channel,note,0)))]
            hits.append(dict(source_id=event.event_id,family=family,source_start_sample=event.start_sample,
                observed_stop_sample=source_stop,port=0,channel=channel+1,voice=profile['voice'],
                note=note,reference_hz=profile['hz'],bend=profile['bend'],velocity=level,
                start_tick=start,stop_tick=stop))
            cursor=stop;end=max(end,stop)
    data = encode_smf(records,ppq=480,end_tick=end,tempo_us=500000,
                      track_names={i+1:family+' / TX802 experimental FM' for i,family in enumerate(FAMILIES)},
                      track_ports={i+1:0 for i in range(5)})
    return RhythmProjection(data,tuple(hits),dict(status='experimental_rhythm_only_FM',notes=len(hits),
        source_sample_rate=44100,ppq=480,bpm=120,losses=losses,profiles=profiles,
        source_rhythm_pitch_context_not_projected=True,
        excluded_native_melodic_units=len(performance.units),excluded_pcm_assets=len(performance.pcm_assets),
        excluded_other_percussion=len(performance.percussion)-len(drums),
        receiver_setup='Five independent TGs on MIDI channels1..5; voices loaded in I16..I20 for bundled profile; pitch bend range12, step0',
        release_policy='Observed stop is a gate, not an audible tail endpoint; repeated keys shorten prior gate',
        limitations=['source pitch/partner changes remain in native context, not target notes',
                     'no per-hit CC11 changes that would alter existing release tails',
                     'two-note TG polyphony, rapid retriggers and song-level fidelity not certified']))
