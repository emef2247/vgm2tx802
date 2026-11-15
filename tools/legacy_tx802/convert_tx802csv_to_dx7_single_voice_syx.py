#!/usr/bin/env python3
import sys
import csv
from pathlib import Path

def yamaha_checksum(data: bytes) -> int:
    return (-sum(data)) & 0x7F

OP_FIELDS = [
    "AR","DR","SR","RR",
    "SL","TL","KSL","MULTI",
    "DT","RS","AM","VIB",
    "EGT","KSR","WS","FINE","FIX",
]

def debug_print(debug, msg):
    if debug:
        print(msg)

def tx802_voice_to_packed(row, debug=False):
    if 'OP1_R1' in row:
        from tx802_sysex_codec import pack_calibration_voice
        return pack_calibration_voice(row)
    v = bytearray(128)
    offset = 0

    debug_print(debug, "\n=== OPERATOR PARAMETERS (CSV → Packed128) ===")

    for op in range(1, 7):
        debug_print(debug, f"\nOP{op}:")
        for f in OP_FIELDS:
            key = f"OP{op}_{f}"
            val = int(row.get(key, 0))
            debug_print(debug, f"  {key:12s} = {val}")
            v[offset] = val & 0x7F
            offset += 1

    debug_print(debug, "\nPitch EG:")
    for key in [
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4"
    ]:
        val = int(row.get(key, 0))
        debug_print(debug, f"  {key:12s} = {val}")
        v[offset] = val & 0x7F
        offset += 1

    alg = int(row.get("ALG", 0))
    fb  = int(row.get("FB", 0))
    debug_print(debug, f"\nALG / FB:\n  ALG = {alg}\n  FB  = {fb}")
    v[offset] = alg & 0x1F; offset += 1
    v[offset] = fb  & 0x07; offset += 1

    debug_print(debug, "\nLFO:")
    for key in ["LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD"]:
        val = int(row.get(key, 0))
        debug_print(debug, f"  {key:12s} = {val}")
        v[offset] = val & 0x7F
        offset += 1

    pms  = int(row.get("LFO_PMS", 0)) & 0x07
    wave = int(row.get("LFO_WAVE", 0)) & 0x07
    sync = int(row.get("LFO_SYNC", 0)) & 0x01
    debug_print(debug, f"  LFO_PMS  = {pms}\n  LFO_WAVE = {wave}\n  LFO_SYNC = {sync}")
    v[offset] = (pms << 4) | (wave << 1) | sync
    offset += 1

    transpose = int(row.get("TRANSPOSE", 0))
    debug_print(debug, f"\nTRANSPOSE = {transpose}")
    v[offset] = transpose & 0x7F
    offset += 1

    name = row["name"][:10].ljust(10)
    debug_print(debug, f"\nName (Packed128 placeholder):\n  name = '{name}'")
    for c in name:
        v[offset] = ord(c) & 0x7F
        offset += 1

    debug_print(debug, "\nPacked128 Dump:")
    debug_print(debug, v.hex())

    return bytes(v)

def build_dx7_single_voice_payload(row, forced_name: str, debug=False):
    packed = tx802_voice_to_packed(row, debug)
    v = bytearray(155)

    debug_print(debug, "\n=== BUILDING DX7 SINGLE-VOICE PAYLOAD (155 bytes) ===")

    # A Format00 payload is unpacked VCED, not packed VMEM with padding.
    # Preserve the corresponding bank packet's parameters and only change its name.
    for op in range(6):
        source = op * 17
        dest = op * 21
        v[dest:dest+11] = packed[source:source+11]
        v[dest+11] = packed[source+11] & 3
        v[dest+12] = (packed[source+11] >> 2) & 3
        v[dest+13] = packed[source+12] & 7
        v[dest+14] = packed[source+13] & 3
        v[dest+15] = (packed[source+13] >> 2) & 7
        v[dest+16] = packed[source+14]
        v[dest+17] = packed[source+15] & 1
        v[dest+18] = (packed[source+15] >> 1) & 31
        v[dest+19] = packed[source+16]
        v[dest+20] = packed[source+12] >> 3
    v[126:134] = packed[102:110]
    v[134] = packed[110] & 31
    v[135] = packed[111] & 7
    v[136] = (packed[111] >> 3) & 1
    v[137:141] = packed[112:116]
    v[141] = packed[116] & 1
    v[142] = (packed[116] >> 1) & 7
    v[143] = (packed[116] >> 4) & 7
    v[144] = packed[117]

    name = forced_name[:10].ljust(10)
    debug_print(debug, f"DX7 Name (payload[145:155]) = '{name}'")
    for i, c in enumerate(name):
        v[145 + i] = ord(c) & 0x7F

    debug_print(debug, "\nPayload155 Dump:")
    debug_print(debug, v.hex())

    return bytes(v)

def wrap_dx7_single_voice(payload155: bytes, device_id=0, debug=False):
    header = bytes([0xF0, 0x43, device_id & 0x0F, 0x00, 0x01, 0x1B])
    cs = yamaha_checksum(payload155)
    syx = header + payload155 + bytes([cs, 0xF7])

    debug_print(debug, "\n=== FINAL SYSEX (163 bytes) ===")
    debug_print(debug, f"Checksum = {cs:02X}")
    debug_print(debug, syx.hex())

    return syx

def main():
    if len(sys.argv) < 2:
        print("Usage: convert_tx802csv_to_dx7_single_voice_syx.py TX802.csv [--debug]")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    debug = ("--debug" in sys.argv)

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    out_dir = csv_path.parent

    for index, row in enumerate(rows):
        voice_num = index + 1
        if voice_num < 21 and 'OP1_R1' not in row:
            continue

        forced_name = f"UserI{voice_num}"

        if debug:
            print("\n==============================================")
            print(f"GENERATING VOICE I{voice_num}  (name={forced_name})")
            print("==============================================")

        payload155 = build_dx7_single_voice_payload(row, forced_name, debug)
        syx = wrap_dx7_single_voice(payload155, debug=debug)

        out = out_dir / f"{csv_path.stem}_I{voice_num}_DX7_single_voice.syx"
        out.write_bytes(syx)

        print(f"Generated DX7 single-voice syx: {out} (size={len(syx)} bytes)")

if __name__ == "__main__":
    main()
