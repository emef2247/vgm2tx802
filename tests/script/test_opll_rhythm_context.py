"""OPLL rhythm context retains ordered evidence without inventing pitch/tails."""
from dataclasses import asdict
import csv
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'py'))
from native_music import NativeDevice, NativePerformance, NativePercussion
from native_registers import decode_control
from opll_rhythm_context import extract_opll_rhythm_context, dump_opll_rhythm_context


DEVICE = NativeDevice('opll:0', 'opll', 0, 3579545)


def write(register, value, sample, order, device=DEVICE):
    event = SimpleNamespace(command=0x51, address=0, vgmticks=sample, source_event_id=order)
    return decode_control(device, event, bytes((0x51, register, value)))


def performance(controls, events=None, end=100):
    events = (NativePercussion('bd', DEVICE.device_id, '0', 'BD', 20, 50),) if events is None else events
    return NativePerformance((DEVICE,), (), tuple(controls), (), tuple(events), (), end, 'authored', '')


class OPLLRhythmContextTests(unittest.TestCase):
    def test_pretrigger_registers_have_provenance_and_native_stays_unchanged(self):
        source = performance([write(0x16, 0x8a, 0, 1), write(0x26, 0x09, 1, 2),
                              write(0x36, 4, 2, 3), write(0x0e, 0x30, 20, 4),
                              write(0x0e, 0x20, 50, 5)])
        before = asdict(source)
        rows = extract_opll_rhythm_context(source)
        self.assertEqual(asdict(source), before)
        self.assertEqual([x['phase'] for x in rows], ['before_trigger', 'trigger', 'observed_stop', 'observation_end'])
        hit = rows[1]
        self.assertEqual(hit['ch6_fnum'], 394)
        self.assertEqual(hit['ch6_block'], 4)
        self.assertEqual(hit['bd_attenuation'], 4)
        self.assertEqual(hit['register_source_control_ids']['16'], 'opll:0:control:1')
        self.assertFalse(hit['trigger_prior_rhythm_state_known'])
        self.assertIsNone(rows[0]['rhythm_enabled'])
        self.assertEqual(source.percussion[0].pitch_curve, ())
        self.assertEqual(source.percussion[0].control_ids, ())

    def test_same_sample_order_keeps_before_and_after_trigger_distinct(self):
        controls = [write(0x16, 90, 20, 11), write(0x0e, 0x30, 20, 10),
                    write(0x26, 6, 20, 9), write(0x16, 80, 20, 8), write(0x0e, 0x20, 50, 12)]
        rows = extract_opll_rhythm_context(performance(controls))
        self.assertEqual(rows[0]['ch6_fnum'], 80)
        self.assertEqual(rows[1]['ch6_fnum'], 80)
        update = next(x for x in rows if x['phase'] == 'control')
        self.assertEqual((update['sample'], update['order'], update['ch6_fnum']), (20, 11, 90))
        self.assertEqual(rows[0]['state_position'], 'before_control')
        self.assertEqual(rows[1]['trigger_order'], 10)

    def test_unwritten_pitch_and_volume_remain_unknown(self):
        rows = extract_opll_rhythm_context(performance([write(0x0e, 0x30, 20, 1), write(0x0e, 0x20, 50, 2)]))
        hit = rows[1]
        self.assertIsNone(hit['ch6_fnum'])
        self.assertIsNone(hit['ch6_block'])
        self.assertIsNone(hit['bd_attenuation'])
        self.assertIsNone(hit['register_values']['16'])
        self.assertIsNone(hit['register_source_control_ids']['16'])

    def test_partner_state_and_changes_are_retained_for_hihat(self):
        event = NativePercussion('hh', DEVICE.device_id, '4', 'HH', 20, 50)
        rows = extract_opll_rhythm_context(performance([
            write(0x17, 70, 0, 1), write(0x27, 6, 0, 2), write(0x18, 80, 0, 3),
            write(0x28, 8, 0, 4), write(0x37, 0x72, 0, 5), write(0x0e, 0x21, 20, 6),
            write(0x18, 100, 30, 7), write(0x38, 0x3a, 40, 8), write(0x0e, 0x20, 50, 9)], (event,)))
        self.assertEqual((rows[1]['ch7_fnum'], rows[1]['ch8_fnum']), (70, 80))
        changed = next(x for x in rows if x['control_id'] == 'opll:0:control:7')
        self.assertEqual(changed['ch8_fnum'], 100)
        self.assertEqual(changed['hh_attenuation'], 7)
        self.assertEqual(changed['sd_attenuation'], 2)
        changed = next(x for x in rows if x['control_id'] == 'opll:0:control:8')
        self.assertEqual((changed['tom_attenuation'], changed['cym_attenuation']), (3, 10))

    def test_stop_and_explicit_tail_window_are_not_audible_decay(self):
        source = performance([write(0x0e, 0x30, 20, 1), write(0x0e, 0x20, 50, 2),
                              write(0x16, 60, 50, 3), write(0x16, 70, 55, 4), write(0x16, 90, 80, 5)])
        short = extract_opll_rhythm_context(source)
        self.assertNotIn('opll:0:control:3', [x['control_id'] for x in short])
        self.assertEqual(short[-1]['observation_end_sample'], 50)
        tail = extract_opll_rhythm_context(source, tail_samples=10)
        self.assertEqual([x['control_id'] for x in tail if x['phase'] == 'post_stop_control'],
                         ['opll:0:control:3', 'opll:0:control:4'])
        self.assertEqual(tail[-1]['sample'], 60)
        self.assertTrue(all(x['audible_decay_end_sample'] is None for x in tail))
        self.assertTrue(all(x['stop_sample'] == 50 for x in tail))
        self.assertEqual(extract_opll_rhythm_context(source, tail_samples=200)[-1]['sample'], 100)

    def test_unobserved_stop_uses_source_observation_end_without_invented_off(self):
        event = NativePercussion('bd', DEVICE.device_id, '0', 'BD', 20)
        rows = extract_opll_rhythm_context(performance([write(0x0e, 0x30, 20, 1), write(0x16, 5, 80, 2)], (event,)))
        self.assertEqual(rows[-1]['sample'], 100)
        self.assertTrue(all(x['stop_sample'] is None for x in rows))
        self.assertNotIn('observed_stop', [x['phase'] for x in rows])

    def test_simultaneous_families_and_same_sample_retrigger_have_distinct_triggers(self):
        events = (NativePercussion('bd1', DEVICE.device_id, '0', 'BD', 20, 20),
                  NativePercussion('hh', DEVICE.device_id, '4', 'HH', 20, 50),
                  NativePercussion('bd2', DEVICE.device_id, '0', 'BD', 20, 50))
        rows = extract_opll_rhythm_context(performance([write(0x0e, 0x31, 20, 1), write(0x0e, 0x21, 20, 2),
                                                       write(0x0e, 0x31, 20, 3), write(0x0e, 0x20, 50, 4)], events))
        triggers = {x['event_id']: x['control_id'] for x in rows if x['phase'] == 'trigger'}
        self.assertEqual(triggers, {'bd1': 'opll:0:control:1', 'hh': 'opll:0:control:1', 'bd2': 'opll:0:control:3'})

    def test_csv_encodes_raw_values_and_provenance_without_filling_unknowns(self):
        source = performance([write(0x16, 7, 0, 1), write(0x0e, 0x30, 20, 2), write(0x0e, 0x20, 50, 3)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'context.csv'
            dump_opll_rhythm_context(source, path)
            with path.open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(json.loads(rows[1]['register_values'])['16'], 7)
            self.assertIsNone(json.loads(rows[1]['register_values'])['26'])
            self.assertEqual(rows[1]['ch6_fnum'], '')
            self.assertEqual(rows[1]['source_sample_rate'], '44100')

    def test_control_identity_resolves_same_sample_hits_even_if_event_list_reordered(self):
        first = NativePercussion('first', DEVICE.device_id, '0', 'BD', 20, 20,
                                 control_ids=('opll:0:control:1', 'opll:0:control:2'))
        second = NativePercussion('second', DEVICE.device_id, '0', 'BD', 20, 50,
                                  control_ids=('opll:0:control:3', 'opll:0:control:4'))
        rows = extract_opll_rhythm_context(performance([write(0x0e, 0x30, 20, 1), write(0x0e, 0x20, 20, 2),
                                                       write(0x0e, 0x30, 20, 3), write(0x0e, 0x20, 50, 4)], (second, first)))
        triggers = {x['event_id']: x for x in rows if x['phase'] == 'trigger'}
        self.assertEqual(triggers['first']['control_id'], 'opll:0:control:1')
        self.assertEqual(triggers['second']['control_id'], 'opll:0:control:3')
        self.assertEqual(triggers['first']['trigger_match_basis'], 'control_id')

    def test_dual_device_state_does_not_leak(self):
        other = NativeDevice('opll:1', 'opll', 1, 3579545)
        controls = [write(0x16, 5, 0, 1), write(0x26, 0, 0, 2),
                    write(0x16, 9, 0, 3, other), write(0x26, 1, 0, 4, other),
                    write(0x0e, 0x30, 20, 5), write(0x0e, 0x30, 20, 6, other),
                    write(0x0e, 0x20, 50, 7), write(0x0e, 0x20, 50, 8, other)]
        events = (NativePercussion('left', DEVICE.device_id, '0', 'BD', 20, 50),
                  NativePercussion('right', other.device_id, '0', 'BD', 20, 50))
        source = NativePerformance((DEVICE, other), (), tuple(controls), (), events, (), 100, 'authored', '')
        triggers = {x['event_id']: x for x in extract_opll_rhythm_context(source) if x['phase'] == 'trigger'}
        self.assertEqual(triggers['left']['ch6_fnum'], 5)
        self.assertEqual(triggers['right']['ch6_fnum'], 265)
        self.assertEqual(triggers['right']['register_source_control_ids']['16'], 'opll:1:control:3')

    def test_missing_trigger_stop_and_invalid_tail_are_explicit(self):
        with self.assertRaisesRegex(ValueError, 'No observed OPLL rhythm trigger'):
            extract_opll_rhythm_context(performance([]))
        with self.assertRaisesRegex(ValueError, 'No observed OPLL rhythm stop'):
            extract_opll_rhythm_context(performance([write(0x0e, 0x30, 20, 1)]))
        for tail in (-1, 0.5, True):
            with self.subTest(tail=tail), self.assertRaisesRegex(ValueError, 'nonnegative integer'):
                extract_opll_rhythm_context(performance([]), tail_samples=tail)


if __name__ == '__main__':
    unittest.main()
