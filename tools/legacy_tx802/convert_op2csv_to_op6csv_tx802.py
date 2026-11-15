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
    """
    OPL3/OPLL OP2 → TX802 1OP
    prefix: "OP1" or "OP2" from source CSV
    """
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

    # TX802側で補完するもの
    dt   = 0
    rs   = ksr
    sr   = sl      # OPLのSLをTX802のSR/SL両方に使う簡易マッピング
    fine = 0
    fix  = 0

    return {
        "AR":    ar,
        "DR":    dr,
        "SR":    sr,
        "RR":    rr,
        "SL":    sl,
        "TL":    tl,
        "KSL":   ksl,
        "MULTI": multi,
        "DT":    dt,
        "RS":    rs,
        "AM":    am,
        "VIB":   vib,
        "EGT":   egt,
        "KSR":   ksr,
        "WS":    ws,
        "FINE":  fine,
        "FIX":   fix,
    }

def opl2_to_tx802_row_plain(row):
    """
    1行のOP2パラメータをTX802用OP6 CSV行に展開

    入力: OP1 → OP2
    出力: 3並列の 2OP チェーン
      チェーン1: OP2 → OP1
      チェーン2: OP4 → OP3
      チェーン3: OP6 → OP5
    """
    name = row["name"]
    fb   = int(row["FB"])
    alg  = int(row["ALG"])  # ALG=0のままでOK

    op1 = opl2_op_to_tx802(row, "OP1")  # モジュレータ
    op2 = opl2_op_to_tx802(row, "OP2")  # キャリア

    out = {
        "name": name,
        "ALG":  alg,
        "FB":   fb,

        # グローバル（とりあえず0で初期化）
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

    # --- 3並列チェーン構造 ---
    # チェーン1: OP2 → OP1
    for f in OP_FIELDS_TX802:
        out[f"OP2_{f}"] = op2[f]  # キャリア
        out[f"OP1_{f}"] = op1[f]  # モジュレータ

    # チェーン2: OP4 → OP3
    for f in OP_FIELDS_TX802:
        out[f"OP4_{f}"] = op2[f]
        out[f"OP3_{f}"] = op1[f]

    # チェーン3: OP6 → OP5
    for f in OP_FIELDS_TX802:
        out[f"OP6_{f}"] = op2[f]
        out[f"OP5_{f}"] = op1[f]

    return out

def apply_variation(op, variant_id):
    """
    3並列チェーンごとに微妙な音色バリエーションを付ける
    variant_id = 0,1,2
    """
    v = dict(op)  # コピー

    if variant_id == 0:
        # 元の音色（変化なし）
        return v

    elif variant_id == 1:
        # バリエーションA（少し明るく）
        v["TL"] = max(0, v["TL"] - 2)   # TLは小さいほど音量が大きい
        v["DT"] = min(7, v["DT"] + 1)
        v["RR"] = min(15, v["RR"] + 1)
        return v

    elif variant_id == 2:
        # バリエーションB（少し暗く）
        v["TL"] = min(127, v["TL"] + 2)
        v["DT"] = max(0, v["DT"] - 1)
        v["AR"] = min(31, v["AR"] + 1)
        return v

    return v

def apply_variation2(op, variant_id):
    """
    3並列チェーンごとに「丸み」を出すための音色バリエーション
    variant_id = 0,1,2
    """
    v = dict(op)  # コピー

    if variant_id == 0:
        # 元の音色（基準）
        return v

    elif variant_id == 1:
        # 丸みA：少し柔らかく
        v["TL"] = min(127, v["TL"] + 2)     # 音量を少し下げて倍音を弱める
        v["MULTI"] = max(0, v["MULTI"] - 1) # 倍音密度を下げる
        v["DT"] = min(7, v["DT"] + 1)       # 位相揺らぎ
        v["AR"] = max(0, v["AR"] - 1)       # アタックを丸める
        return v

    elif variant_id == 2:
        # 丸みB：さらに柔らかく
        v["TL"] = min(127, v["TL"] + 4)     # もっと丸く
        v["MULTI"] = max(0, v["MULTI"] - 1) # MULTIをさらに低く
        v["DT"] = max(0, v["DT"] - 1)       # 位相揺らぎ（逆方向）
        v["RR"] = min(15, v["RR"] + 1)      # リリースを伸ばす
        return v

    return v


def opl2_to_tx802_row(row):
    name = row["name"]
    fb   = int(row["FB"])
    alg  = int(row["ALG"])

    op1_base = opl2_op_to_tx802(row, "OP1")  # モジュレータ
    op2_base = opl2_op_to_tx802(row, "OP2")  # キャリア

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

    # --- 3並列チェーン ---
    for variant_id, (carrier_idx, mod_idx) in enumerate([(2,1),(4,3),(6,5)]):

        #op2 = apply_variation(op2_base, variant_id)
        #op1 = apply_variation(op1_base, variant_id)
        op2 = apply_variation2(op2_base, variant_id)
        op1 = apply_variation2(op1_base, variant_id)

        for f in OP_FIELDS_TX802:
            out[f"OP{carrier_idx}_{f}"] = op2[f]
            out[f"OP{mod_idx}_{f}"]     = op1[f]

    return out

def convert_csv(in_csv, out_csv):
    with open(in_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        src_rows = list(reader)

    dst_rows = [opl2_to_tx802_row(r) for r in src_rows]

    # フィールド定義
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
        print("Usage: convert_op2csv_to_op6csv_tx802.py OPLL_OP2.csv")
        sys.exit(1)

    in_csv = sys.argv[1]
    stem, _ = os.path.splitext(in_csv)
    out_csv = stem + "_tx802_op6.csv"

    convert_csv(in_csv, out_csv)
    print(f"Generated TX802 OP6 CSV: {out_csv}")
