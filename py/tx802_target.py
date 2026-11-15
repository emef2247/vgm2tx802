"""Direct NativePerformance projection to TX802-oriented, inspectable MIDI.

No source parser, MML renderer, or legacy 60 Hz Segment clock is consumed here.
Voice selection and the velocity lookup are retained target approximations.
"""
from collections import defaultdict
from dataclasses import asdict, dataclass
from fractions import Fraction
import csv
import json
import math

from tx802_midi import MidiRecord, encode_smf, meta
from tx802_voices import (velocity, expression, validate_voice, assign_user_patch,
                          preset_voice, bank_select, voice_csv_text)


class TX802ProjectionError(ValueError):
    pass


@dataclass(frozen=True)
class TX802Event:
    source_id: str
    device_id: str
    source_channel: int
    source_sample: int
    midi_tick: int
    port: int
    channel: int
    track: int
    order: int
    kind: str
    data_hex: str
    shift_samples: float


@dataclass(frozen=True)
class TX802Projection:
    events: tuple
    mappings: tuple
    report: dict
    user_voice_map: dict
    data: bytes
    voice_csv: str

    def dump(self, folder, stem):
        from pathlib import Path
        root = Path(folder)
        root.mkdir(parents=True, exist_ok=True)
        (root / f'{stem}_voice.csv').write_text(self.voice_csv, encoding='utf-8')
        (root / f'{stem}.tx802.projection.json').write_text(json.dumps(self.report, indent=2)+'\n', encoding='utf-8')
        (root / f'{stem}.user_voice_tx802.proposed.json').write_text(json.dumps(self.user_voice_map, indent=2)+'\n', encoding='utf-8')
        for name, rows, fields in (
            ('events', [asdict(e) for e in self.events], list(TX802Event.__dataclass_fields__)),
            ('routing', list(self.mappings), ['device_id','source_channel','port','channel','track','tg'])):
            with (root / f'{stem}.tx802.{name}.csv').open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)


def _at(curve, sample):
    value = None
    for at, item in curve:
        if at <= sample:
            value = item
    return value


def _midi_pitch(hz):
    if hz is None or not math.isfinite(hz) or hz <= 0:
        raise TX802ProjectionError('Sounding OPLL unit has no usable native pitch')
    return 69 + 12*math.log2(hz/440)


def project_tx802(performance, *, stem='song', ppq=480, bpm=120, melody_mode='default',
                  rhythm_mode='rx21', tx802_units=1, pitch_bend_range=12,
                  domino_init=True, init_lead_ticks=12, voice_map=None, force=False, preset_voice_map=None):
    """Return SMF plus an original-sample-to-MIDI event/routing plan."""
    if isinstance(ppq, bool) or not isinstance(ppq, int) or not 1 <= ppq <= 32767:
        raise ValueError('PPQ must be an integer in 1..32767')
    if not math.isfinite(bpm) or bpm <= 0:
        raise ValueError('BPM must be finite and positive')
    tempo_us = round(60000000/bpm)
    if not 1 <= tempo_us <= 0xffffff:
        raise ValueError('BPM is outside the SMF tempo range')
    if tx802_units not in (1,2) or isinstance(tx802_units, bool):
        raise ValueError('TX802 units must be 1 or 2')
    if isinstance(pitch_bend_range, bool) or not isinstance(pitch_bend_range, int) or not 1 <= pitch_bend_range <= 12:
        raise ValueError('TX802 pitch-bend range must be an integer in 1..12')
    if melody_mode not in ('default','name','gm','opll') or rhythm_mode not in ('gm','rx21'):
        raise ValueError('Unknown melody/rhythm mapping')
    if isinstance(init_lead_ticks, bool) or not isinstance(init_lead_ticks, int) or init_lead_ticks < 0:
        raise ValueError('Initialization lead must be nonnegative integer MIDI ticks')
    lead = init_lead_ticks if domino_init else 0
    ticks_per_sample = Fraction(ppq*1000000, 44100*tempo_us)
    samples_per_tick = 1/ticks_per_sample
    def tick(sample):
        return round(sample*ticks_per_sample)+lead
    devices = {d.device_id:d for d in performance.devices}
    voices = {v.voice_id:v for v in performance.voices}
    units = sorted((u for u in performance.units if devices[u.device_id].chip=='opll' and u.section=='fm'),
                   key=lambda u:(u.device_id,u.channel,u.start_sample,u.unit_id))
    drums = sorted((e for e in performance.percussion if devices[e.device_id].chip=='opll'),
                   key=lambda e:(e.start_sample,e.device_id,e.instrument_family,e.event_id))
    active = {x.device_id for x in (*performance.units,*performance.percussion,*performance.pcm_assets)}
    active.update(c.device_id for c in performance.controls)
    active.update(d.device_id for d in performance.devices if any(p.chip==d.chip for p in performance.pcm_packets))
    omitted = [dict(kind='unsupported_source_device', device_id=d.device_id, source_chip=d.chip)
               for d in performance.devices if d.device_id in active and d.chip!='opll']
    if omitted and not force:
        raise TX802ProjectionError('TX802 currently projects OPLL only; --force permits reported partial projection')
    keys = sorted({(u.device_id,u.channel) for u in units if u.end_sample>u.start_sample})
    if len(keys)>8*tx802_units:
        if not force:
            raise TX802ProjectionError(f'TX802 part capacity exceeded: {len(keys)}/{8*tx802_units}; use --tx802-units 2 or a reported --force projection')
        for device,ch in keys[8*tx802_units:]:
            omitted.append(dict(kind='part_capacity',device_id=device,source_channel=ch))
        keys = keys[:8*tx802_units]
    routes = {key:(i//8,i%8,i+1) for i,key in enumerate(keys)}
    mappings = tuple(dict(device_id=d,source_channel=ch,port=p,channel=c,track=t,tg=c+1)
                     for (d,ch),(p,c,t) in routes.items())
    if not keys and not drums:
        raise TX802ProjectionError('No OPLL melody or rhythm is available for TX802 output')
    assignments = {key:validate_voice(value) for key,value in (voice_map or {}).items() if not key.startswith('_')}
    for key in assignments:
        try:
            if len(bytes.fromhex(key)) != 8:
                raise ValueError()
        except (ValueError, TypeError) as exc:
            raise ValueError('User voice map requires eight-byte hexadecimal patch keys') from exc
    assignments = {key.lower():value for key,value in assignments.items()}
    losses, assumptions, selected, gates = [], [], {}, []
    selected_patches = {}
    def level(value, identity):
        if value is None:
            assumptions.append(dict(kind='unwritten_attenuation_assumed_zero',source_id=identity))
            return 0
        if not isinstance(value,int) or not 0<=value<=15:
            raise TX802ProjectionError('Native OPLL attenuation is outside 0..15')
        return value
    def choose(identity):
        if identity in selected:
            return selected[identity]
        if identity not in voices:
            raise TX802ProjectionError(f'Unknown native voice {identity}')
        fields = dict(voices[identity].parameters)
        number = fields.get('instrument')
        if number is None:
            assumptions.append(dict(kind='unwritten_instrument_assumed_custom',voice_id=identity))
            number = 0
        if number:
            if preset_voice_map is not None:
                if number not in preset_voice_map:
                    raise TX802ProjectionError(f'No explicit preset mapping for OPLL {number}')
                entry = validate_voice(preset_voice_map[number])
            else:
                entry = preset_voice(number,melody_mode)
        else:
            patch = fields.get('custom_patch',())
            if len(patch)!=8:
                raise TX802ProjectionError('Custom OPLL voice requires eight patch fields')
            if any(value is None for value in patch):
                assumptions.append(dict(kind='unwritten_custom_fields_assumed_zero',voice_id=identity))
            patch = bytes(0 if value is None else value for value in patch)
            entry = assign_user_patch(patch,assignments)
            selected_patches[patch.hex()] = entry
        selected[identity] = entry
        return entry
    # Resolve voices only when a settling target state is actually emitted.
    # Reserving slots for every zero-width native setup snapshot exhausts I21+
    # even when those intermediate patches never sound in the MIDI projection.
    events, names, ports = [], {0:stem}, {}
    def emit(identity,device,source_ch,sample,at,route,order,kind,data):
        port,ch,track = route
        events.append(TX802Event(identity,device,source_ch,sample,at,port,ch,track,order,kind,
                                data.hex(),float((at-lead)*samples_per_tick-sample)))
    for (device,ch),route in routes.items():
        port,channel,track = route
        names[track] = f'{device} FM ch{ch+1} -> TX802 {port+1} TG{channel+1}'
        ports[track] = port
        if domino_init:
            for cc,value in ((121,0),(7,100),(11,127),(10,64),(1,0),(64,0),(65,0)):
                emit('initialization',device,ch,0,0,route,0,'init_cc',bytes((0xb0|channel,cc,value)))
            emit('initialization',device,ch,0,0,route,0,'init_pitch_bend',bytes((0xe0|channel,0,64)))
    cursor = defaultdict(int)
    cache = {}
    for unit in units:
        key = unit.device_id,unit.channel
        if key not in routes:
            continue
        if unit.end_sample==unit.start_sample:
            losses.append(dict(kind='zero_duration_gate_not_sounded',source_id=unit.unit_id))
            continue
        route = routes[key];port,ch,track = route
        start = max(tick(unit.start_sample),cursor[key])
        stop = max(start+1,tick(unit.end_sample))
        change_times = sorted({unit.start_sample}|{at for curve in (unit.pitch_curve,unit.volume_curve,unit.voice_curve)
                              for at,_ in curve if unit.start_sample<at<unit.end_sample})
        projected = {}
        for sample in change_times:
            at = min(stop-1,start+round((sample-unit.start_sample)*ticks_per_sample))
            if at in projected:
                losses.append(dict(kind='internal_controls_settle_on_one_midi_tick',source_id=unit.unit_id,
                                   source_sample=sample,midi_tick=at))
            projected[at] = sample
        peak = min(level(_at(unit.volume_curve,sample),unit.unit_id) for sample in change_times)
        attack_velocity = velocity(peak)
        first_sample = projected[start]
        try:
            anchor = round(_midi_pitch(_at(unit.pitch_curve,first_sample)))
        except TX802ProjectionError:
            if not force:
                raise
            omitted.append(dict(kind='unknown_pitch',source_id=unit.unit_id))
            continue
        if not 0<=anchor<=127:
            if not force:
                raise TX802ProjectionError('Native melody pitch exceeds MIDI note range')
            clipped = max(0,min(127,anchor))
            losses.append(dict(kind='midi_note_clipped',source_id=unit.unit_id,original=anchor,projected=clipped))
            anchor = clipped
        previous_voice = None
        for at,sample in sorted(projected.items()):
            identity = _at(unit.voice_curve,sample)
            entry = choose(identity)
            selection = bank_select(entry)
            if cache.get((port,ch))!=selection:
                msb,lsb,program = selection
                emit(unit.unit_id,unit.device_id,unit.channel,sample,at,route,20,'bank_msb',bytes((0xb0|ch,0,msb)))
                emit(unit.unit_id,unit.device_id,unit.channel,sample,at,route,21,'bank_lsb',bytes((0xb0|ch,32,lsb)))
                emit(unit.unit_id,unit.device_id,unit.channel,sample,at,route,30,'program',bytes((0xc0|ch,program)))
                cache[port,ch] = selection
            if previous_voice is not None and previous_voice!=identity:
                losses.append(dict(kind='mid_gate_program_change_hardware_dependent',source_id=unit.unit_id,
                                   source_sample=sample,from_voice=previous_voice,to_voice=identity))
            previous_voice = identity
            pitch = _midi_pitch(_at(unit.pitch_curve,sample))
            delta = pitch-anchor
            if abs(delta)>pitch_bend_range:
                if not force:
                    raise TX802ProjectionError(f'Held pitch exceeds configured bend range on {unit.unit_id}; increase --pitch-bend-range up to 12 or use --force')
                losses.append(dict(kind='held_pitch_bend_clipped',source_id=unit.unit_id,source_sample=sample,
                                   semitones=delta,range=pitch_bend_range))
            raw_bend = round(8192+8192*max(-pitch_bend_range,min(pitch_bend_range,delta))/pitch_bend_range)
            bend = max(0,min(16383,raw_bend))
            emit(unit.unit_id,unit.device_id,unit.channel,sample,at,route,40,'pitch_bend',bytes((0xe0|ch,bend&127,bend>>7)))
            value = level(_at(unit.volume_curve,sample),unit.unit_id)
            cc11 = round(127*expression(value)/expression(peak))
            emit(unit.unit_id,unit.device_id,unit.channel,sample,at,route,50,'expression',bytes((0xb0|ch,11,cc11)))
        emit(unit.unit_id,unit.device_id,unit.channel,unit.start_sample,start,route,60,'note_on',bytes((0x90|ch,anchor,attack_velocity)))
        emit(unit.unit_id,unit.device_id,unit.channel,unit.end_sample,stop,route,10,'note_off',bytes((0x80|ch,anchor,0)))
        emit(unit.unit_id,unit.device_id,unit.channel,unit.end_sample,stop,route,15,'reset_pitch_bend',bytes((0xe0|ch,0,64)))
        gates.append(dict(source_id=unit.unit_id,source_start_sample=unit.start_sample,source_end_sample=unit.end_sample,
                          start_tick=start,end_tick=stop,peak_attenuation=peak,attack_velocity=attack_velocity,
                          onset_attenuation=level(_at(unit.volume_curve,unit.start_sample),unit.unit_id)))
        cursor[key] = stop
    if drums:
        route = 0,9,len(keys)+1
        ports[route[2]] = 0
        names[route[2]] = f'OPLL rhythm -> external {rhythm_mode.upper()} channel 10'
        gm = {'BD':35,'SD':38,'TOM':45,'CYM':49,'HH':42}
        rx21 = {'BD':45,'SD':52,'TOM':50,'CYM':60,'HH':57}
        drum_cursor = defaultdict(int)
        next_hits, following_hits = {}, {}
        for drum in reversed(drums):
            family = drum.instrument_family.upper()
            if family not in gm:
                raise TX802ProjectionError(f'Unknown rhythm family {family}')
            note = (rx21 if rhythm_mode=='rx21' else gm)[family]
            following_hits[drum.event_id] = next_hits.get(note)
            next_hits[note] = tick(drum.start_sample)
        for drum in drums:
            family = drum.instrument_family.upper()
            if family not in gm:
                raise TX802ProjectionError(f'Unknown rhythm family {family}')
            note = (rx21 if rhythm_mode=='rx21' else gm)[family]
            start = max(tick(drum.start_sample),drum_cursor[note])
            stop = max(start+1,tick(drum.stop_sample)) if drum.stop_sample is not None else start+max(1,ppq//8)
            following = following_hits[drum.event_id]
            if following is not None and stop > max(start+1,following):
                stop = max(start+1,following)
                losses.append(dict(kind='rhythm_gate_shortened_before_repeated_key',source_id=drum.event_id))
            v = level(_at(drum.volume_curve,drum.start_sample),drum.event_id)
            vel = max(1,round((15-v)*127/15))
            emit(drum.event_id,drum.device_id,-1,drum.start_sample,start,route,60,'drum_on',bytes((0x99,note,vel)))
            emit(drum.event_id,drum.device_id,-1,drum.stop_sample if drum.stop_sample is not None else drum.start_sample,
                 stop,route,10,'drum_off',bytes((0x89,note,0)))
            if drum.stop_sample is None:
                losses.append(dict(kind='unobserved_rhythm_stop_uses_short_midi_gate',source_id=drum.event_id))
            if len(drum.volume_curve)>1:
                losses.append(dict(kind='rhythm_internal_volume_retained_only_in_native',source_id=drum.event_id))
            drum_cursor[note] = stop
    source_end_tick = tick(performance.end_sample)
    end_tick = max([source_end_tick]+[e.midi_tick for e in events])+1
    for key,route in routes.items():
        emit('terminal',key[0],key[1],performance.end_sample,end_tick,route,90,'all_notes_off',bytes((0xb0|route[1],123,0)))
    if performance.song_loop_sample is not None:
        emit('source_loop','source',-1,performance.song_loop_sample,tick(performance.song_loop_sample),
             (0,0,0),0,'loop_marker',meta(6,b'loopStart'))
        emit('source_loop','source',-1,performance.end_sample,source_end_tick,(0,0,0),0,'loop_marker',meta(6,b'loopEnd'))
    events.sort(key=lambda e:(e.midi_tick,e.track,e.order,e.source_sample))
    records = [MidiRecord(e.midi_tick,e.track,e.order,bytes.fromhex(e.data_hex)) for e in events]
    data = encode_smf(records,ppq=ppq,end_tick=end_tick,tempo_us=tempo_us,track_names=names,track_ports=ports)
    displaced = [g['start_tick']-tick(g['source_start_sample']) for g in gates]
    report = dict(status='success',source_sha256=performance.source_sha256,source_clock_hz=44100,
        source_time_domain='original_source_samples',source_native_modified=False,ppq=ppq,tempo_us=tempo_us,
        init_lead_ticks=lead,end_tick=end_tick,source_end_tick=source_end_tick,
        ticks_per_sample_numerator=ticks_per_sample.numerator,ticks_per_sample_denominator=ticks_per_sample.denominator,
        events=len(events),notes=sum(e.kind in ('note_on','drum_on') for e in events),channels=len(keys),ports=tx802_units,
        bytes=len(data),omitted=omitted,losses=losses,assumptions=assumptions,gates=gates,
        maximum_shift_samples=max((abs(e.shift_samples) for e in events if not e.kind.startswith('init')),default=0),
        maximum_gate_delay_ticks=max(displaced,default=0),cumulative_gate_delay_ticks=sum(displaced),
        terminal_duration_change_ticks=end_tick-source_end_tick,
        pitch_bend=dict(range_semitones=pitch_bend_range,required_voice_step=0,automatic_hardware_setup=False),
        velocity_policy='inherited_nonlinear_table_at_gate_peak; peak_relative_inverse_CC11; hardware_combined_response_unverified',
        bank_policy='legacy_CC0_CC32_and_PC; hardware_bank_support_unverified; bank_only_change_reissues_PC',
        voice_policy='bank_program_assignments_only; no_six_operator_patch_upload',
        rhythm_policy=f'external_{rhythm_mode}_channel10; not_TX802_FM_synthesis',
        source_loop_policy='SMF_markers_only; no_standard_repeat_execution',
        melody_mode=melody_mode,preset_voice_map=preset_voice_map,rhythm_mode=rhythm_mode,requested_bpm=bpm,
        voice_slot_policy='first emitted settling state in stable source lane/time order; existing content maps win',
        voice_selections=selected,reference_vgm_policy='source_native_not_TX802_render')
    return TX802Projection(tuple(events),mappings,report,assignments,data,voice_csv_text(selected_patches))
