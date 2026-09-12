#!/usr/bin/env python3
import csv
import argparse
from pathlib import Path

def yamaha_checksum(data: bytes) -> int:
    return (128 - (sum(data) & 0x7F)) & 0x7F

def csv_to_dx7_voice(row):
    v = bytearray(128)
    ops = [6,5,4,3,2,1]
    offset = 0

    for op in ops:
        for _ in range(11):  # EG R1–4, L1–4, BP, LD, RD
            v[offset] = 0; offset += 1

        v[offset] = 0; offset += 1  # LC
        v[offset] = 0; offset += 1  # RC

        v[offset] = int(row[f"OP{op}_RS"]) & 0x07; offset += 1
        v[offset] = int(row[f"OP{op}_AM"]) & 0x03; offset += 1
        v[offset] = int(row[f"OP{op}_KSR"]) & 0x07; offset += 1
        v[offset] = int(row[f"OP{op}_TL"]) & 0x7F; offset += 1

    for key in [
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4"
    ]:
        v[offset] = int(row[key]) & 0x7F; offset += 1

    v[offset] = int(row["ALG"]) & 0x1F; offset += 1

    fb = int(row["FB"]) & 0x07
    v[offset] = fb; offset += 1

    for key in ["LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD"]:
        v[offset] = int(row[key]) & 0x7F; offset += 1

    # byte 116
    v[offset] = 0
    offset += 1

    # byte 117
    v[offset] = int(row["TRANSPOSE"]) & 0x7F
    offset += 1

    # byte 118–127: Name
    name = row["name"][:10].ljust(10)
    for c in name:
        v[offset] = ord(c) & 0x7F
        offset += 1

    return bytes(v)

def build_bulkdump(voices, device_id=1):
    bank = b"".join(voices)
    header = bytes([0xF0,0x43,(device_id-1)&0x0F,0x09,0x20,0x00])
    cs = yamaha_checksum(bank)
    return header + bank + bytes([cs,0xF7])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvfile")
    ap.add_argument("--device", type=int, default=1)
    args = ap.parse_args()

    csv_path = Path(args.csvfile)
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))

    if len(rows) < 32:
        need = 32 - len(rows)
        print(f"Warning: voices={len(rows)} → {need} dummy voices added")
        for i in range(need):
            rows.append(rows[0])

    if len(rows) > 32:
        print(f"Warning: CSV has {len(rows)} voices → only first 32 used")
        rows = rows[:32]

    voices = [csv_to_dx7_voice(r) for r in rows]
    syx = build_bulkdump(voices, device_id=args.device)

    # ★ 修正：同じディレクトリに .syx を生成する
    out = csv_path.with_suffix(".syx")
    out.write_bytes(syx)

    print(f"Generated 32‑Voice BulkDump: {out}")
    print(f"Size: {len(syx)} bytes (expected 4104)")

if __name__ == "__main__":
    main()
