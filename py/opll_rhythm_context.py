"""Observed OPLL rhythm register context beside native percussion events.

Pitch registers here are oscillator inputs, not inferred MIDI pitches. In
particular, HH/CYM can depend on both channels 7 and 8. Trigger, observed stop
and an explicitly requested observation window remain separate from audible
decay. No native records or timing are changed.
"""
from bisect import bisect_right
from collections import defaultdict
import csv
import json
from pathlib import Path

from native_registers import encode_control


FAMILY_BITS = {'BD': 16, 'SD': 8, 'TOM': 4, 'CYM': 2, 'HH': 1}
CONTEXT_REGISTERS = (0x0e, 0x0f, 0x16, 0x17, 0x18,
                     0x26, 0x27, 0x28, 0x36, 0x37, 0x38)


def _active(value):
    # An unwritten register is unknown in the snapshot. As in the native
    # event collector, only an observed enabled mask establishes activity.
    return value & 31 if value is not None and value & 32 else 0


def _snapshot(values, sources):
    result = dict(register_values={f'{r:02x}': values.get(r) for r in CONTEXT_REGISTERS},
                  register_source_control_ids={f'{r:02x}': sources.get(r) for r in CONTEXT_REGISTERS})
    rhythm = values.get(0x0e)
    result['rhythm_enabled'] = bool(rhythm & 32) if rhythm is not None else None
    result['rhythm_mask'] = rhythm & 31 if rhythm is not None else None
    for channel in (6, 7, 8):
        low, high = values.get(0x10 + channel), values.get(0x20 + channel)
        result[f'ch{channel}_fnum'] = low | (high & 1) << 8 if low is not None and high is not None else None
        result[f'ch{channel}_block'] = (high >> 1) & 7 if high is not None else None
        result[f'ch{channel}_key_bit'] = bool(high & 16) if high is not None else None
        result[f'ch{channel}_sustain_bit'] = bool(high & 32) if high is not None else None
    for family, register, shift in (('BD', 0x36, 0), ('SD', 0x37, 0),
                                    ('TOM', 0x38, 4), ('CYM', 0x38, 0), ('HH', 0x37, 4)):
        value = values.get(register)
        result[f'{family.lower()}_attenuation'] = (value >> shift) & 15 if value is not None else None
    return result


def _timelines(performance, devices):
    timelines = defaultdict(list)
    values, sources = defaultdict(dict), defaultdict(dict)
    controls = sorted(enumerate(performance.controls), key=lambda item: (item[1].sample, item[1].order, item[0]))
    for source_index, control in controls:
        device = devices.get(control.device_id)
        if device is None:
            continue
        register = dict(control.parameters)['register']
        if register not in CONTEXT_REGISTERS:
            continue
        value = encode_control(control, device)[2]
        current, origin = values[device.device_id], sources[device.device_id]
        before = _snapshot(current, origin)
        old_active = _active(current.get(0x0e))
        current[register], origin[register] = value, control.control_id
        new_active = _active(current.get(0x0e))
        timelines[device.device_id].append(dict(
            control=control, source_control_index=source_index, register=register, value=value,
            before=before, after=_snapshot(current, origin),
            rising=(new_active & ~old_active) if register == 0x0e else 0,
            falling=(old_active & ~new_active) if register == 0x0e else 0))
    return timelines


def extract_opll_rhythm_context(performance, *, tail_samples=0):
    """Return flat inspectable rows, including state immediately before each hit.

    All times are integer source samples at 44100 Hz. ``tail_samples`` extends
    observation past an observed stop, bounded by source end; it neither measures
    nor invents a decay endpoint. An unobserved stop captures through source end.
    Events must match an observed rising rhythm mask at their start sample.
    Full source controls are replayed, including writes absent from control_ids.
    """
    if isinstance(tail_samples, bool) or not isinstance(tail_samples, int) or tail_samples < 0:
        raise ValueError('tail_samples must be a nonnegative integer source-sample count')
    devices = {d.device_id: d for d in performance.devices if d.chip == 'opll'}
    timelines = _timelines(performance, devices)
    candidates, stops = defaultdict(list), defaultdict(list)
    sample_positions = {}
    for device_id, timeline in timelines.items():
        sample_positions[device_id] = [record['control'].sample for record in timeline]
        for index, record in enumerate(timeline):
            for family, bit in FAMILY_BITS.items():
                if record['rising'] & bit:
                    candidates[device_id, family, record['control'].sample].append(index)
                if record['falling'] & bit:
                    stops[device_id, family, record['control'].sample].append(index)
    used = defaultdict(set)
    rows = []
    for event in performance.percussion:
        if event.device_id not in devices:
            continue
        family = event.instrument_family
        if family not in FAMILY_BITS:
            raise ValueError(f'Unknown OPLL percussion family: {family}')
        if not 0 <= event.start_sample <= performance.end_sample:
            raise ValueError(f'Percussion start outside source timeline: {event.event_id}')
        if event.stop_sample is not None and not event.start_sample <= event.stop_sample <= performance.end_sample:
            raise ValueError(f'Percussion stop outside source timeline: {event.event_id}')
        key = event.device_id, family, event.start_sample
        remaining = [index for index in candidates[key] if index not in used[key]]
        if not remaining:
            raise ValueError(f'No observed OPLL rhythm trigger for {event.event_id}')
        timeline = timelines[event.device_id]
        evidence = [index for index in remaining if timeline[index]['control'].control_id in event.control_ids]
        trigger_index = (evidence or remaining)[0]
        used[key].add(trigger_index)
        trigger = timeline[trigger_index]
        capture_end = min(performance.end_sample, event.stop_sample + tail_samples) if event.stop_sample is not None else performance.end_sample
        stop_index = None
        if event.stop_sample is not None:
            matching_stops = stops[event.device_id, family, event.stop_sample]
            position = bisect_right(matching_stops, trigger_index)
            if position < len(matching_stops):
                stop_index = matching_stops[position]
            if stop_index is None:
                raise ValueError(f'No observed OPLL rhythm stop for {event.event_id}')
        end_index = stop_index + 1 if stop_index is not None and tail_samples == 0 else bisect_right(sample_positions[event.device_id], capture_end)
        common = dict(event_id=event.event_id, device_id=event.device_id, instrument_family=family,
                      source_sample_rate=44100, start_sample=event.start_sample, stop_sample=event.stop_sample,
                      observation_end_sample=capture_end, requested_tail_samples=tail_samples,
                      trigger_control_id=trigger['control'].control_id,
                      trigger_order=trigger['control'].order,
                      trigger_match_basis='control_id' if evidence else 'same_sample_family_occurrence',
                      trigger_prior_rhythm_state_known=trigger['before']['rhythm_mask'] is not None,
                      audible_decay_end_sample=None)

        def append(record, phase, state, *, boundary_sample=None):
            control = record['control'] if record is not None else None
            rows.append(dict(common, phase=phase,
                             sample=control.sample if control is not None else boundary_sample,
                             order=control.order if control is not None else None,
                             source_control_index=record['source_control_index'] if record is not None else None,
                             control_id=control.control_id if control is not None else None,
                             source_event_id=control.source_event_id if control is not None else None,
                             register=record['register'] if record is not None else None,
                             value=record['value'] if record is not None else None,
                             state_position='before_control' if phase == 'before_trigger' else
                             'after_control' if record is not None else 'after_last_captured_control',
                             **state))

        append(trigger, 'before_trigger', trigger['before'])
        append(trigger, 'trigger', trigger['after'])
        last_state = trigger['after']
        for index in range(trigger_index + 1, end_index):
            record = timeline[index]
            phase = 'observed_stop' if index == stop_index else 'post_stop_control' if stop_index is not None and index > stop_index else 'control'
            append(record, phase, record['after'])
            last_state = record['after']
        append(None, 'observation_end', last_state, boundary_sample=capture_end)
    return tuple(rows)


def dump_opll_rhythm_context(performance, path, *, tail_samples=0):
    """Write context rows as CSV; raw state/provenance maps are JSON columns."""
    rows = extract_opll_rhythm_context(performance, tail_samples=tail_samples)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Even an empty extraction has an inspectable header.
    fields = list(rows[0]) if rows else ['event_id', 'device_id', 'instrument_family', 'sample', 'phase']
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, dict) else value
                             for key, value in row.items()})
    return rows
