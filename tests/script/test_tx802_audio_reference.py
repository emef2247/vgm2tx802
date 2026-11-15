"""Offline host timing and asset validation, independent of Texed installation."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'py'),str(ROOT/'scripts')]
from tx802_midi import MidiRecord,encode_smf,meta
from render_tx802 import midi_job,validate_sysex

class ReferenceHostTests(unittest.TestCase):
    def test_tempo_map_and_end_silence(self):
        data=encode_smf([MidiRecord(480,0,0,meta(0x51,(1000000).to_bytes(3,'big'))),
                         MidiRecord(240,1,0,bytes((0x90,69,98))),
                         MidiRecord(720,1,0,bytes((0x80,69,0)))],end_tick=960)
        job=midi_job(data)
        self.assertEqual([e['frame'] for e in job['events']],[12000,48000])
        self.assertEqual(job['end_frame'],72000)

    def test_two_ports_same_channel_are_independent(self):
        data=encode_smf([MidiRecord(0,t,0,bytes((0x90,60+t,98))) for t in (1,2)],end_tick=480,
                        track_ports={1:0,2:1})
        self.assertEqual([(e['port'],e['channel']) for e in midi_job(data)['events']],[(0,0),(1,0)])

    def test_external_drums_require_explicit_omission(self):
        data=encode_smf([MidiRecord(0,1,0,bytes((0x99,42,98)))],end_tick=480)
        with self.assertRaises(ValueError): midi_job(data)
        job=midi_job(data,omit_drums=True)
        self.assertEqual(job['events'],[])
        self.assertEqual(job['omitted_drum_events'],1)

    def test_retrigger_encoded_order_is_preserved(self):
        events=[MidiRecord(0,1,0,bytes((0x90,60,98))),MidiRecord(480,1,1,bytes((0x80,60,0))),
                MidiRecord(480,1,2,bytes((0x90,60,98)))]
        kinds=[e['kind'] for e in midi_job(encode_smf(events,end_tick=960))['events']]
        self.assertEqual(kinds,['note_on','note_off','note_on'])

    def test_voice_frame_length_checksum_and_ranges(self):
        body=bytearray(155);body[134]=31;body[144]=24
        def packet(payload):
            return bytes((0xf0,0x43,0,0,1,27))+payload+bytes(((-sum(payload))&127,0xf7))
        validate_sysex(packet(body))
        with self.assertRaises(ValueError): validate_sysex(packet(body)[:-1])
        wrong=bytearray(packet(body));wrong[-2]^=1
        with self.assertRaises(ValueError): validate_sysex(wrong)
        body[0]=100
        with self.assertRaises(ValueError): validate_sysex(packet(body))

if __name__=='__main__': unittest.main()
