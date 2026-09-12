#!/usr/bin/env python3
import sys
import csv
import os

WS_MAP = {
    "0": 0, "1": 1, "2": 2, "3": 3,
    "4": 4, "5": 4, "6": 5, "7": 5,
}

OP_FIELDS = ["RS","AM","KSR","TL","WS"]

def extract_op(row, prefix):
    return {
        "RS":  int(row[f"{prefix}_KSR"]) & 0x07,
        "AM":  int(row[f"{prefix}_AM"])  & 0x03,
        "KSR": int(row[f"{prefix}_KSR"]) & 0x07,
        "TL":  int(row[f"{prefix}_TL"])  & 0x7F,
        "WS":  WS_MAP[row[f"{prefix}_WS"]],
    }

def opll_to_tx802(row):
    name = row["name"]
    fb = int(row["FB"])
    alg = int(row["ALG"])

    op1 = extract_op(row, "OP1")
    op2 = extract_op(row, "OP2")

    ops = [op1, op2, op1, op2, op1, op2]

    out = {
        "name": name,
        "ALG": alg,
        "FB": fb,
        "LFO_SPEED": 0,
        "LFO_DELAY": 0,
        "LFO_PMD": 0,
        "LFO_AMD": 0,
        "TRANSPOSE": 0,
        "PITCH_EG_R1": 0,
        "PITCH_EG_R2": 0,
        "PITCH_EG_R3": 0,
        "PITCH_EG_R4": 0,
        "PITCH_EG_L1": 0,
        "PITCH_EG_L2": 0,
        "PITCH_EG_L3": 0,
        "PITCH_EG_L4": 0,
    }

    for i, op in enumerate(ops, start=1):
        for p in OP_FIELDS:
            out[f"OP{i}_{p}"] = op[p]

    return out

def dummy_voice(n):
    """ダミー voice を作成"""
    out = {
        "name": f"DUMMY{n:02d}",
        "ALG": 0,
        "FB": 0,
        "LFO_SPEED": 0,
        "LFO_DELAY": 0,
        "LFO_PMD": 0,
        "LFO_AMD": 0,
        "TRANSPOSE": 0,
        "PITCH_EG_R1": 0,
        "PITCH_EG_R2": 0,
        "PITCH_EG_R3": 0,
        "PITCH_EG_R4": 0,
        "PITCH_EG_L1": 0,
        "PITCH_EG_L2": 0,
        "PITCH_EG_L3": 0,
        "PITCH_EG_L4": 0,
    }
    for i in range(1,7):
        for p in OP_FIELDS:
            out[f"OP{i}_{p}"] = 0
    return out

def convert_csv(in_csv, out_csv):
    rows = list(csv.DictReader(open(in_csv, encoding="utf-8")))
    out_rows = [opll_to_tx802(r) for r in rows]

    # 32 未満ならダミー追加
    if len(out_rows) < 32:
        need = 32 - len(out_rows)
        print(f"Warning: voices={len(out_rows)} → {need} dummy voices added")
        for i in range(need):
            out_rows.append(dummy_voice(i))

    # 32 以上ならそのまま（警告なし）
    fieldnames = [
        "name","ALG","FB",
        "LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD",
        "TRANSPOSE",
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4",
    ]
    for i in range(1,7):
        for p in OP_FIELDS:
            fieldnames.append(f"OP{i}_{p}")

    with open(out_csv,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

if __name__ == "__main__":
    in_csv = sys.argv[1]
    out_csv = os.path.splitext(in_csv)[0] + "_tx802.csv"
    convert_csv(in_csv, out_csv)
    print("Generated:", out_csv)


