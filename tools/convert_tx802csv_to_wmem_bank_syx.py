#!/usr/bin/env python3
import sys
import csv
from pathlib import Path

def yamaha_checksum(data: bytes) -> int:
    return (128 - (sum(data) & 0x7F)) & 0x7F

# TX802 Packed Format operator fields (17 bytes)
OP_FIELDS = [
    "AR","DR","SR","RR",
    "SL","TL","KSL","MULTI",
    "DT","RS","AM","VIB",
    "EGT","KSR","WS","FINE","FIX",
]

def tx802_voice_to_packed(row):
    """
    Convert TX802 OP6 CSV row → 128-byte Packed Format (DX7/TX802 WMEM)
    """
    v = bytearray(128)
    offset = 0

    # ---- OP blocks (17 bytes × 6) ----
    for op in range(1, 7):
        for f in OP_FIELDS:
            v[offset] = int(row.get(f"OP{op}_{f}", 0)) & 0x7F
            offset += 1

    # ---- Pitch EG (8 bytes) ----
    for key in [
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4"
    ]:
        v[offset] = int(row.get(key, 0)) & 0x7F
        offset += 1

    # ---- Algorithm ----
    v[offset] = int(row.get("ALG", 0)) & 0x1F
    offset += 1

    # ---- Feedback ----
    v[offset] = int(row.get("FB", 0)) & 0x07
    offset += 1

    # ---- LFO (4 bytes) ----
    for key in ["LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD"]:
        v[offset] = int(row.get(key, 0)) & 0x7F
        offset += 1

    # ---- byte 116: PMS + LFO Waveform + Sync ----
    pms  = int(row.get("LFO_PMS", 0)) & 0x07
    wave = int(row.get("LFO_WAVE", 0)) & 0x07
    sync = int(row.get("LFO_SYNC", 0)) & 0x01
    v[offset] = (pms << 4) | (wave << 1) | sync
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

def build_wmem_bank(voices, device_id=1):
    """
    Build TX802 WMEM bank (32 voices → 4104 bytes)
    """
    bank = b"".join(voices)
    header = bytes([0xF0,0x43,(device_id-1)&0x0F,0x09,0x20,0x00])
    cs = yamaha_checksum(bank)
    return header + bank + bytes([cs,0xF7])

def main():
    if len(sys.argv) < 2:
        print("Usage: convert_tx802_csv_to_wmem_bank.py TX802.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))

    # 32 未満 → ダミー追加
    if len(rows) < 32:
        need = 32 - len(rows)
        print(f"Warning: voices={len(rows)} → {need} dummy voices added")
        dummy = rows[0].copy()
        for key in dummy.keys():
            if key.startswith("OP"):
                dummy[key] = "0"
        for i in range(need):
            d = dummy.copy()
            d["name"] = f"DUMMY{i:02d}"
            rows.append(d)

    # 32 以上 → 33以降は無視
    if len(rows) > 32:
        print(f"Warning: CSV has {len(rows)} voices → only first 32 used")
        rows = rows[:32]

    voices = [tx802_voice_to_packed(r) for r in rows]
    syx = build_wmem_bank(voices, device_id=1)

    out = csv_path.with_suffix(".tx802_wmem32.syx")
    out.write_bytes(syx)

    print(f"Generated TX802 WMEM 32‑Voice Bank: {out}")
    print(f"Size: {len(syx)} bytes (expected 4104)")

if __name__ == "__main__":
    main()


