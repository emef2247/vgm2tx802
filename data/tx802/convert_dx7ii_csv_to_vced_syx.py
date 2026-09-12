#!/usr/bin/env python3
import sys
import csv
from pathlib import Path

def yamaha_checksum(data: bytes) -> int:
    return (128 - (sum(data) & 0x7F)) & 0x7F

OP_FIELDS = [
    "AR","DR","SL","RR",
    "TL","KSL","MULTI","KSR",
    "AM","VIB","EGT","WS",
]

def build_dx7ii_vced_block(row):
    """
    DX7II VCEDっぽい 155バイトのボイスデータを組み立てる。
    - OP1〜OP6: AR/DR/SL/RR/TL/KSL/MULTI/KSR/AM/VIB/EGT/WS を詰めて残りは0でパディング
    - ALG/FB/LFO/Transpose/PitchEG/Name を後半に配置
    ※正確な公式VCED仕様ではなく、あなたのCSV構造に合わせた実用的なマッピング。
    """
    v = bytearray(155)
    offset = 0

    # ---- OP1〜OP6 ----
    for op_idx in range(1, 7):
        for f in OP_FIELDS:
            v[offset] = int(row.get(f"OP{op_idx}_{f}", 0)) & 0x7F
            offset += 1
        # 残りはパディング（1OPあたり21バイト程度に揃える）
        while offset % 21 != 0 and offset < 21 * op_idx:
            v[offset] = 0
            offset += 1

    # ---- ALG / FB ----
    v[offset] = int(row.get("ALG", 0)) & 0x1F; offset += 1
    v[offset] = int(row.get("FB", 0)) & 0x07; offset += 1

    # ---- LFO ----
    for key in ["LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD"]:
        v[offset] = int(row.get(key, 0)) & 0x7F; offset += 1

    # ---- LFO拡張（PMS/WAVE/SYNC）→ まとめて1バイトに詰める例 ----
    pms  = int(row.get("LFO_PMS", 0)) & 0x07
    wave = int(row.get("LFO_WAVE", 0)) & 0x07
    sync = int(row.get("LFO_SYNC", 0)) & 0x01
    v[offset] = (pms << 4) | (wave << 1) | sync
    offset += 1

    # ---- Transpose ----
    v[offset] = int(row.get("TRANSPOSE", 0)) & 0x7F
    offset += 1

    # ---- Pitch EG ----
    for key in [
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4"
    ]:
        v[offset] = int(row.get(key, 0)) & 0x7F
        offset += 1

    # ---- Name (10文字) ----
    name = row["name"][:10].ljust(10)
    for c in name:
        v[offset] = ord(c) & 0x7F
        offset += 1

    # 残りはゼロで埋める
    while offset < 155:
        v[offset] = 0
        offset += 1

    return bytes(v)

def build_dx7ii_vced_sysex(voice_data: bytes,
                           device: int = 0,
                           substatus: int = 0,
                           function: int = 1):
    """
    DX7II 単音VCED SysEx:
    F0 81 22 43 dd ss ff 1B [155 bytes] cs F7
    """
    dd = device & 0x7F
    ss = substatus & 0x7F
    ff = function & 0x7F

    header = bytes([0xF0, 0x81, 0x22, 0x43, dd, ss, ff, 0x1B])
    cs     = yamaha_checksum(voice_data)
    tail   = bytes([cs, 0xF7])

    return header + voice_data + tail

def main():
    if len(sys.argv) < 2:
        print("Usage: convert_dx7ii_csv_to_vced_syx.py DX7II.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))

    if not rows:
        print("No voices in CSV")
        sys.exit(1)

    # とりあえず全voice分のVCED SysExを1ファイルに連結して出力
    syx_blocks = []
    for i, row in enumerate(rows):
        voice = build_dx7ii_vced_block(row)
        syx   = build_dx7ii_vced_sysex(voice, device=0, substatus=0, function=1)
        syx_blocks.append(syx)

    out = csv_path.with_suffix(".dx7ii_vced_all.syx")
    out.write_bytes(b"".join(syx_blocks))

    print(f"Generated DX7II VCED SysEx (all voices): {out}")
    print(f"Voices: {len(rows)}, Total bytes: {len(b''.join(syx_blocks))}")

if __name__ == "__main__":
    main()


