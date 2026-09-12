#!/usr/bin/env python3
import sys
import csv
import os

# TX802 operator parameter fields (per OP)
OP_FIELDS_TX802 = [
    "AR","DR","SR","RR",
    "SL","TL","KSL","MULTI",
    "DT","RS","AM","VIB",
    "EGT","KSR","WS","FINE","FIX",
]

def opl2_op_to_tx802(row, prefix):
    ar    = int(row[f"{prefix}_AR"])
    dr    = int(row[f"{prefix}_DR"])
    sl    = int(row[f"{prefix}_SL"])
    rr    = int(row[f"{prefix}_RR"])
    tl    = int(row[f"{prefix}_TL"])
    ksl   = int(row[f"{prefix}_KSL"])
    multi = int(row[f"{prefix}_MULTI"])
    ksr   = int(row[f"{prefix}_KSR"])
    am    = int(row[f"{prefix}_AM"])
    vib   = int(row[f"{prefix}_VIB"])
    egt   = int(row[f"{prefix}_EGT"])
    ws    = int(row[f"{prefix}_WS"])

    return {
        "AR":    ar,
        "DR":    dr,
        "SR":    sl,
        "RR":    rr,
        "SL":    sl,
        "TL":    tl,
        "KSL":   ksl,
        "MULTI": multi,
        "DT":    0,
        "RS":    ksr,
        "AM":    am,
        "VIB":   vib,
        "EGT":   egt,
        "KSR":   ksr,
        "WS":    ws,
        "FINE":  0,
        "FIX":   0,
    }

def opl2_to_tx802_row(row):
    name = row["name"]
    fb   = int(row["FB"])
    alg  = int(row["ALG"])

    op1 = opl2_op_to_tx802(row, "OP1")  # モジュレータ
    op2 = opl2_op_to_tx802(row, "OP2")  # キャリア

    out = {
        "name": name,
        "ALG":  alg,
        "FB":   fb,

        "LFO_SPEED": 0,
        "LFO_DELAY": 0,
        "LFO_PMD":   0,
        "LFO_AMD":   0,
        "LFO_WAVE":  0,
        "LFO_SYNC":  0,
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

    # --- OP1/OP2 のみ展開 ---
    for f in OP_FIELDS_TX802:
        out[f"OP2_{f}"] = op2[f]  # キャリア
        out[f"OP1_{f}"] = op1[f]  # モジュレータ

    # --- OP3〜OP6 は完全に 0 ---
    for i in [3,4,5,6]:
        for f in OP_FIELDS_TX802:
            out[f"OP{i}_{f}"] = 0

    return out

def convert_csv(in_csv, out_csv):
    with open(in_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        src_rows = list(reader)

    dst_rows = [opl2_to_tx802_row(r) for r in src_rows]

    fieldnames = [
        "name","ALG","FB",
        "LFO_SPEED","LFO_DELAY","LFO_PMD","LFO_AMD",
        "LFO_WAVE","LFO_SYNC",
        "TRANSPOSE",
        "PITCH_EG_R1","PITCH_EG_R2","PITCH_EG_R3","PITCH_EG_R4",
        "PITCH_EG_L1","PITCH_EG_L2","PITCH_EG_L3","PITCH_EG_L4",
    ]
    for i in range(1, 7):
        for f in OP_FIELDS_TX802:
            fieldnames.append(f"OP{i}_{f}")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(dst_rows)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: convert_op2csv_to_op2csv_tx802.py OPLL_OP2.csv")
        sys.exit(1)

    in_csv = sys.argv[1]
    stem, _ = os.path.splitext(in_csv)
    out_csv = stem + "_tx802_op2.csv"

    convert_csv(in_csv, out_csv)
    print(f"Generated TX802 OP2 CSV: {out_csv}")
