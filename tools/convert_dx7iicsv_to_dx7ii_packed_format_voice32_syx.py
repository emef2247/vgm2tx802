#!/usr/bin/env python3
import csv
import argparse
from pathlib import Path

def yamaha_checksum(data: bytes) -> int:
    return (128 - (sum(data) & 0x7F)) & 0x7F

def csv_to_dx7ii_voice(row):
    v = bytearray(128)
    ops = [6,5,4,3,2,1]
    offset = 0

    # ---- Operator blocks (17 bytes × 6) ----
    for op in ops:
        # EG R1–4, L1–4, BP, LD, RD → 全て 0
        for _ in range(11):
            v[offset] = 0; offset += 1

        # LC / RC → 0
        v[offset] = 0; offset += 1
        v[offset] = 0; offset += 1

        # RS
        v[offset] = int(row.get(f"OP{op}_RS", 0)) & 0x07; offset += 1

        # AMS
        v[offset] = int(row.get(f"OP{op}_AM", 0)) & 0x03; offset += 1

        # KVS
        v[offset] = int(row.get(f"OP{op}_KSR", 0)) & 0x07; offset += 1

        # OL = TL
        v[offset] = int(row.get(f"OP{op}_TL", 0)) & 0x7F; offset += 1

    # ---- Pitch EG (8 bytes) ----
    for key in [
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4"
    ]:
        v[offset] = int(row.get(key, 0)) & 0x7F; offset += 1

    # ---- Algorithm ----
    v[offset] = int(row.get("ALG", 0)) & 0x1F; offset += 1

    # ---- Feedback ----
    v[offset] = int(row.get("FB", 0)) & 0x07; offset += 1

    # ---- LFO (4 bytes) ----
    for key in ["LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD"]:
        v[offset] = int(row.get(key, 0)) & 0x7F; offset += 1

    # ---- byte 116: DX7初代互換のため 0 固定 ----
    v[offset] = 0
    offset += 1

    # ---- Transpose ----
    v[offset] = int(row.get("TRANSPOSE", 0)) & 0x7F
    offset += 1

    # ---- Name (10 bytes) ----
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

    # 32 未満 → ダミー追加
    if len(rows) < 32:
        need = 32 - len(rows)
        print(f"Warning: voices={len(rows)} → {need} dummy voices added")
        for i in range(need):
            dummy = rows[0].copy()
            dummy["name"] = f"DUMMY{i:02d}"
            for key in dummy.keys():
                if key.startswith("OP"):
                    dummy[key] = "0"
            rows.append(dummy)

    # 32 以上 → 33 以降は無視
    if len(rows) > 32:
        print(f"Warning: CSV has {len(rows)} voices → only first 32 used")
        rows = rows[:32]

    voices = [csv_to_dx7ii_voice(r) for r in rows]
    syx = build_bulkdump(voices, device_id=args.device)

    out = csv_path.with_suffix(".dx7ii_bulkdump32.syx")
    out.write_bytes(syx)

    print(f"Generated DX7II 32‑Voice BulkDump: {out}")
    print(f"Size: {len(syx)} bytes (expected 4104)")

if __name__ == "__main__":
    main()
