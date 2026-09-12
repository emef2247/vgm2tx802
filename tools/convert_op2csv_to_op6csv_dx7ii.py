#!/usr/bin/env python3
import sys
import csv
import os

# DX7II operator waveform mapping (OPLL WS → DX7II WS)
# DX7II has 8 waveforms (0–7). OPLL WS also has 0–7, so direct mapping is OK.
WS_MAP = {
    "0": 0, "1": 1, "2": 2, "3": 3,
    "4": 4, "5": 4, "6": 5, "7": 5,
}

# DX7II operator fields (expanded)
OP_FIELDS_DX7II = [
    "AR","DR","SL","RR",
    "TL","KSL","MULTI","KSR",
    "AM","VIB","EGT","WS"
]

def extract_op(row, prefix):
    """OPLL 2OP → DX7II operator conversion"""
    return {
        "AR":   int(row[f"{prefix}_AR"]),
        "DR":   int(row[f"{prefix}_DR"]),
        "SL":   int(row[f"{prefix}_SL"]),
        "RR":   int(row[f"{prefix}_RR"]),
        "TL":   int(row[f"{prefix}_TL"]),
        "KSL":  int(row[f"{prefix}_KSL"]),
        "MULTI":int(row[f"{prefix}_MULTI"]),
        "KSR":  int(row[f"{prefix}_KSR"]),
        "AM":   int(row[f"{prefix}_AM"]),
        "VIB":  int(row[f"{prefix}_VIB"]),
        "EGT":  int(row[f"{prefix}_EGT"]),
        "WS":   WS_MAP[row[f"{prefix}_WS"]],
    }

def opll_to_dx7ii(row):
    """Convert one OPLL 2OP voice → DX7II 6OP CSV row"""
    name = row["name"]
    fb = int(row["FB"])
    alg = int(row["ALG"])

    op1 = extract_op(row, "OP1")
    op2 = extract_op(row, "OP2")

    # OP1→1,3,5 / OP2→2,4,6
    ops = [op1, op2, op1, op2, op1, op2]

    out = {
        "name": name,
        "ALG": alg,
        "FB": fb,

        # DX7II global parameters (CSV に保持する)
        "LFO_SPEED": 0,
        "LFO_DELAY": 0,
        "LFO_PMD": 0,
        "LFO_AMD": 0,
        "LFO_PMS": 0,     # DX7II 拡張
        "LFO_WAVE": 0,    # DX7II 拡張
        "LFO_SYNC": 0,    # DX7II 拡張

        "TRANSPOSE": 0,

        # Pitch EG
        "PITCH_EG_R1": 0,
        "PITCH_EG_R2": 0,
        "PITCH_EG_R3": 0,
        "PITCH_EG_R4": 0,
        "PITCH_EG_L1": 0,
        "PITCH_EG_L2": 0,
        "PITCH_EG_L3": 0,
        "PITCH_EG_L4": 0,
    }

    # OP1〜OP6 を埋める
    for i, op in enumerate(ops, start=1):
        for p in OP_FIELDS_DX7II:
            out[f"OP{i}_{p}"] = op[p]

    return out

def dummy_voice(n):
    """DX7II ダミー voice を作成"""
    out = {
        "name": f"DUMMY{n:02d}",
        "ALG": 0,
        "FB": 0,
        "LFO_SPEED": 0,
        "LFO_DELAY": 0,
        "LFO_PMD": 0,
        "LFO_AMD": 0,
        "LFO_PMS": 0,
        "LFO_WAVE": 0,
        "LFO_SYNC": 0,
        "TRANSPOSE": 0,
        "PITCH_EG_R1": 0,"PITCH_EG_R2": 0,"PITCH_EG_R3": 0,"PITCH_EG_R4": 0,
        "PITCH_EG_L1": 0,"PITCH_EG_L2": 0,"PITCH_EG_L3": 0,"PITCH_EG_L4": 0,
    }
    for i in range(1,7):
        for p in OP_FIELDS_DX7II:
            out[f"OP{i}_{p}"] = 0
    return out

def convert_csv(in_csv, out_csv):
    rows = list(csv.DictReader(open(in_csv, encoding="utf-8")))
    out_rows = [opll_to_dx7ii(r) for r in rows]

    # 32 未満 → ダミー追加
    if len(out_rows) < 32:
        need = 32 - len(out_rows)
        print(f"Warning: voices={len(out_rows)} → {need} dummy voices added")
        for i in range(need):
            out_rows.append(dummy_voice(i))

    # 32 以上 → そのまま（警告なし）
    fieldnames = [
        "name","ALG","FB",
        "LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD",
        "LFO_PMS","LFO_WAVE","LFO_SYNC",
        "TRANSPOSE",
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4",
    ]

    for i in range(1,7):
        for p in OP_FIELDS_DX7II:
            fieldnames.append(f"OP{i}_{p}")

    with open(out_csv,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

if __name__ == "__main__":
    in_csv = sys.argv[1]
    out_csv = os.path.splitext(in_csv)[0] + "_dx7ii.csv"
    convert_csv(in_csv, out_csv)
    print("Generated:", out_csv)


