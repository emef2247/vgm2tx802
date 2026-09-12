
# moonbl_opll2tx802.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from py.opl3_op2_extractor import (
    OPLL_OPL3_2OP_INSTRS,
    extract_opl3_2op_features,
)
from py.tx802 import (
    Tx802Voice,
    classify_opl3_to_tx802
) 


def generate_moonblaster_opll_to_tx802():
    table = {}

    for opll_num, inst in enumerate(OPLL_OPL3_2OP_INSTRS):
        feat = extract_opl3_2op_features(inst.regs)
        txv = classify_opl3_to_tx802(feat)

        table[opll_num] = {
            "bank": txv.bank,
            "voice": txv.voice,
            "label": f"{txv.bank}{txv.voice}",
            "source": inst.name,
        }

    return table


if __name__ == "__main__":
    table = generate_moonblaster_opll_to_tx802()

    print("MOONBLASTER_OPLL_TO_TX802_VOICE = {")
    for k, v in table.items():
        print(f"    {k}: {v},")
    print("}")


