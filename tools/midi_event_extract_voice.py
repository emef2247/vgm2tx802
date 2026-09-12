#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import mido
from collections import defaultdict

def decode_tx802_vnum(cc0, pc):
    if cc0 is None or pc is None:
        return None
    return (cc0 * 64) + pc

def decode_tx802_bank_from_vnum(vnum):
    if vnum is None:
        return "?"
    if 0 <= vnum <= 63:
        return "I"
    if 64 <= vnum <= 127:
        return "C"
    if 128 <= vnum <= 191:
        return "A"
    if 192 <= vnum <= 255:
        return "B"
    return "?"

def extract_tx802_voices(path: str):
    mid = mido.MidiFile(path)

    # トラックごとの音色セット
    track_voices = defaultdict(set)

    # チャンネルごとの現在の CC0 / PC
    channel_state = defaultdict(lambda: {"cc0": None, "pc": None})

    for tidx, track in enumerate(mid.tracks):
        for msg in track:

            # CC0 (Bank MSB)
            if msg.type == "control_change" and msg.control == 0:
                channel_state[msg.channel]["cc0"] = msg.value

            # Program Change
            elif msg.type == "program_change":
                channel_state[msg.channel]["pc"] = msg.program

            # Note On → この瞬間の CC0+PC が「そのノートの音色」
            elif msg.type == "note_on" and msg.velocity > 0:
                st = channel_state[msg.channel]
                cc0 = st["cc0"]
                pc = st["pc"]
                vnum = decode_tx802_vnum(cc0, pc)
                bank = decode_tx802_bank_from_vnum(vnum)
                voice = (pc + 1) if pc is not None else None

                track_voices[tidx].add((msg.channel, bank, voice, vnum))

    return track_voices


def main(path: str):
    track_voices = extract_tx802_voices(path)

    print("=== TX802 Voice Usage by Track ===")
    for tidx in sorted(track_voices.keys()):
        print(f"\nTrack {tidx}:")
        for (ch, bank, voice, vnum) in sorted(track_voices[tidx]):
            if voice is None or vnum is None:
                # PC / CC0 が揃っていない場合のフォールバック表示
                print(f"  ch={ch} → Bank={bank}, Voice=?, vnum=? (PC/CC0 missing)")
            else:
                print(f"  ch={ch} → {bank}{voice:02d} (vnum={vnum})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file.mid>")
        sys.exit(1)
    main(sys.argv[1])
