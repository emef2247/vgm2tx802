"""Synthetic, independently authored SMF encoding and validation examples."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "py"))
from tx802_midi import MidiRecord, decode_smf, encode_smf, meta


def smf(*tracks, ppq=480):
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppq)
    return header + b"".join(b"MTrk" + struct.pack(">I", len(t)) + t for t in tracks)


class Tx802MidiTests(unittest.TestCase):
    def test_known_bytes_order_and_silence(self):
        records = [MidiRecord(240, 1, 20, b"\x90\x3c\x64"),
                   MidiRecord(120, 1, 0, b"\xb0\x07\x64"),
                   MidiRecord(240, 1, 10, b"\x80\x3c\x00"),
                   MidiRecord(240, 1, 20, b"\x90\x40\x64")]
        actual = encode_smf(records, end_tick=960)
        conductor = b"\x00\xff\x51\x03\x07\xa1\x20\x87\x40\xff\x2f\x00"
        music = (b"\x78\xb0\x07\x64\x78\x80\x3c\x00"
                 b"\x00\x90\x3c\x64\x00\x90\x40\x64\x85\x50\xff\x2f\x00")
        self.assertEqual(actual, smf(conductor, music))
        self.assertEqual(decode_smf(actual)["tracks"][1], [
            (120, b"\xb0\x07\x64"), (240, b"\x80\x3c\x00"),
            (240, b"\x90\x3c\x64"), (240, b"\x90\x40\x64"),
            (960, b"\xff\x2f\x00")])

    def test_sysex_uses_smf_length_not_wire_framing(self):
        raw = b"\xf0\x43" + bytes(range(128)) + b"\xf7"
        encoded = encode_smf([MidiRecord(0, 1, 0, raw)], end_tick=1)
        self.assertIn(b"\x00\xf0\x81\x02" + raw[1:], encoded)
        self.assertEqual(decode_smf(encoded)["tracks"][1][0], (0, raw))

    def test_utf8_name_port_missing_tracks_and_shared_end(self):
        name = "音" * 50
        encoded = encode_smf([], end_tick=480, track_names={2: name}, track_ports={2: 7})
        self.assertIn(b"\xff\x03\x81\x16" + name.encode("utf-8"), encoded)
        decoded = decode_smf(encoded)
        self.assertEqual(decoded["ppq"], 480)
        self.assertEqual(len(decoded["tracks"]), 3)
        self.assertEqual(decoded["tracks"][1], [(480, b"\xff\x2f\x00")])
        self.assertEqual(decoded["tracks"][2], [
            (0, meta(3, name.encode("utf-8"))), (0, b"\xff\x21\x01\x07"),
            (480, b"\xff\x2f\x00")])

    def test_channel_message_widths(self):
        events = [bytes((status, 10)) if status & 0xF0 in (0xC0, 0xD0)
                  else bytes((status, 10, 20)) for status in range(0x80, 0xF0)]
        encoded = encode_smf([MidiRecord(i, 1, 0, event) for i, event in enumerate(events)],
                             end_tick=len(events))
        self.assertEqual([e for _, e in decode_smf(encoded)["tracks"][1][:-1]], events)

    def test_encode_invalid_arguments(self):
        for kwargs in ({"ppq": 0}, {"ppq": 32768}, {"ppq": True},
                       {"end_tick": -1}, {"end_tick": 0x10000000},
                       {"tempo_us": 0}, {"tempo_us": 0x1000000},
                       {"track_names": {1: b"name"}}, {"track_names": {True: "x"}},
                       {"track_ports": {1: 128}}, {"track_ports": {1: True}},
                       {"track_names": []}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, TypeError)):
                encode_smf([], **({"end_tick": 10} | kwargs))
        for field, value in (("tick", -1), ("tick", True), ("tick", 11),
                             ("track", -1), ("track", 65535), ("track", 1.0),
                             ("order", -1), ("order", 0x10000000), ("order", False)):
            args = {"tick": 0, "track": 1, "order": 0, "data": b"\x90\x3c\x64"}
            args[field] = value
            with self.subTest(field=field, value=value), self.assertRaises((ValueError, TypeError)):
                encode_smf([MidiRecord(**args)], end_tick=10)

    def test_reject_invalid_messages(self):
        for message in (b"", b"\x90\x40", b"\x90\x80\x01", b"\xc0\x00\x00",
                        b"\x40\x00", b"\xf1\x00", b"\xf7\x01", b"\xf0",
                        b"\xf0\x80\xf7", b"\xf0\x01", b"\xff\x03\x02a",
                        b"\xff\x2f\x00", b"\xff\x51\x01\x00",
                        b"\xff\x21\x01\x80", bytearray(b"\xc0\x01")):
            with self.subTest(message=message), self.assertRaises((ValueError, TypeError)):
                encode_smf([MidiRecord(0, 1, 0, message)], end_tick=0)

    def test_decoder_known_running_status(self):
        track = b"\x00\x90\x3c\x64\x01\x40\x64\x00\xff\x2f\x00"
        self.assertEqual(decode_smf(smf(track))["tracks"][0], [
            (0, b"\x90\x3c\x64"), (1, b"\x90\x40\x64"), (1, b"\xff\x2f\x00")])

    def test_decoder_rejects_malformed_chunks_and_events(self):
        eot = b"\x00\xff\x2f\x00"
        malformed = [b"", smf(eot)[:-1], smf(eot) + b"x", smf(b""),
                     smf(eot + b"\x00\xc0\x00"), smf(b"\x00\xff\x2f\x01\x00"),
                     smf(b"\x00\x90\x40"), smf(b"\x00\x90\x80\x00" + eot),
                     smf(b"\x00\x40\x00" + eot), smf(b"\x00\xff\x03\x02x"),
                     smf(b"\x00\xf0\x03\x43\xf7"),
                     smf(b"\x00\xf0\x02\x43\x01" + eot),
                     smf(b"\x81\x80\x80\x80\x00\xff\x2f\x00"),
                     smf(eot, ppq=0x8001)]
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_smf(data)

    def test_meta_type_and_length_validation(self):
        self.assertEqual(meta(3, b"a" * 128), b"\xff\x03\x81\x00" + b"a" * 128)
        for kind, data in ((True, b""), (128, b""), (3, "text")):
            with self.assertRaises((ValueError, TypeError)):
                meta(kind, data)


if __name__ == "__main__":
    unittest.main()
