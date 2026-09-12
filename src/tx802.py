# py/tx802.py
from __future__ import annotations

import csv
import os
import json
import random

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict

from opll import (
    NUM_CH,
    RHYTHM_VOICE_ID_MAP,
    _ym2413_patch_to_mgsdrv
)

from segment_utils import (
    compute_velocity,
    compute_portamento_time
)

from midi_utils import (
    map_gm_drum,
    map_rx21_drum,
    DEFAULT_PPQ,
    MidiBuilder,
    _is_zero_patch,
    _tempo_meta_event,
    _track_name_meta_event,
    _opll_vol_to_velocity,
    _at_token_to_user_v_num,
    compute_cc11,
)
from note_event import build_drum_note_events, build_melody_note_events

from tx802_presets import (
    TX802_VOCES_AB
)

if TYPE_CHECKING:
    from .opl3_op2_extractor import Opl3Features2Op

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VOICE_CSV_DIR = os.path.join(_REPO_ROOT, "data/opll/presets")
_OPLL_PRESET_OP2_CSV = os.path.join(_VOICE_CSV_DIR, "OPLL_OP2_MB14.csv")

# ============================================================
# Format 1 channel-to-track routing (Domino-compatible)
# track0: meta only; track1: reserved; track2..10: ch0..8; track11: ch9
# ============================================================

# OPLL から展開されるリズム入力 ch (opll.py の RHYTHM_CH_MAP に対応)
RHYTHM_SRC_CHS_TX802 = {9, 10, 11, 12, 13}

# TX802 で実際に使う MIDI ドラム ch
RHYTHM_MIDI_CH_TX802 = 9

TX802_CHANNEL_TO_TRACK: dict[int, int] = {
    0: 2,
    1: 3,
    2: 4,
    3: 5,
    4: 6,
    5: 7,
    6: 8,
    7: 9,
    8: 10,
    9: 11,  # ← ドラムは全部この ch9 にまとめる
}


# ============================================================
# TX802 Voice Mapping
# ============================================================

@dataclass(frozen=True)
class Tx802Voice:
    bank: str
    voice: int  # 11..88 など（TX802 表示番号）

    def to_vnum(self) -> int:
        """
        TX802 の「内部ボイス番号」（0–127）に変換する。
        A/B/I/C バンクを DX7II 互換の 0–127 空間にマップする想定。
        """
        v = self.voice - 1
        b = self.bank.upper()
        if b == "I":
            return 0 + v      # Internal 1–32
        if b == "C":
            return 64 + v     # Internal 33–64 or Cartridge などの想定
        if b == "A":
            return 128 + v    # Preset A
        if b == "B":
            return 192 + v    # Preset B
        return v

# ============================================================
# Default TX802 Voice Name Based Mapping Table
# ============================================================
#   1: OPLL Violin          
#   2: OPLL Guitar          
#   3: OPLL Piano           
#   4: OPLL Flute           
#   5: OPLL Clarinet        
#   6: OPLL Oboe            
#   7: OPLL Trumpet         
#   8: OPLL Organ           
#   9: OPLL Horn            
#   10: OPLL Synth          
#   11: OPLL Harpsichord    
#   12: OPLL Vibraphone     
#   13: OPLL SynthBass      
#   14: OPLL AcousticBass   
#   15: OPLL ElectricGuitar 
TX802_MELODY_OPLL_TO_DEFAULT = {
    1:  Tx802Voice("I", 1), # I1: OPLL Violin 
    2:  Tx802Voice("I", 2), # I2: OPLL Guitar  
    3:  Tx802Voice("I", 3), # I3: OPLL Piano  
    4:  Tx802Voice("I", 5), # I4: OPLL Flute 
    5:  Tx802Voice("I", 5), # I5: OPLL Clarinet  
    6:  Tx802Voice("I", 6), # I6: OPLL Oboe     
    7:  Tx802Voice("I", 7), # I7: OPLL Trumpet    
    8:  Tx802Voice("I", 8), # I8: OPLL Organ  
    9:  Tx802Voice("I", 9), # I9: OPLL Horn    
    10: Tx802Voice("I", 10), # I10: OPLL Synth     
    11: Tx802Voice("I", 11), # I11: OPLL Harpsichord   
    12: Tx802Voice("I", 12), # I12: OPLL Vibraphone    
    13: Tx802Voice("I", 13), # I13: OPLL SynthBass    
    14: Tx802Voice("I", 14), # I14: OPLL AcousticBass  
    15: Tx802Voice("I", 15), # I15: OPLL ElectricGuitar 
}

# ============================================================
# PRESET A/B Based TX802 Voice Name Based Mapping Table
# ============================================================
#   1: OPLL Violin          -> A19 Violins,A11 Strings,A13 NewOrchest
#   2: OPLL Guitar          -> A35 KnockRoad,A36 RubbaRoad,A37 HardRoads
#   3: OPLL Piano           -> A33 Piano   1,A34 Piano   2,A32 PianoBrite
#   4: OPLL Flute           -> A23 Flute,A24 SongFlute,A27 Piccolo
#   5: OPLL Clarinet        -> A21 Clarinet,B40 ClariSolo,A20 Bassoon
#   6: OPLL Oboe            -> A22 Oboe,A20 Bassoon,A26 PanFloot
#   7: OPLL Trumpet         -> A7 Trumpet A,A8 SilvaTrmpt,A9 Trumpet B
#   8: OPLL Organ           -> A48 TouchOrga,A51 BriteOrga,A54 PipeOrgan
#   9: OPLL Horn            -> A1 MellowHorn,A10 FrenchHorn,A4 Tuba
#   10: OPLL Synthesizer    -> A38 FullTines,A39 ClaviStuf,A40 Clavi
#   11: OPLL Harpsichord    -> A41 Clavecin,A42 ClaviPluc,A44 HarpsiBox
#   12: OPLL Vibraphone     -> B21 VibraPhone,B18 DX Marimba,B19 Nu Marimba
#   13: OPLL Synth. Bass    -> B1 SuperBass,B2 StringBass,B3 SkweekBass
#   14: OPLL Acoust.Bass    -> B2 StringBass,B4 SmoohBass,B5 BopBass
#   15: OPLL ElectricGuitar -> B9 GuitarBox,B10 PickGuitar,B11 FingaPicka
#   16: OPLL BD1            -> B23 Swissnare,B24 Tom C4,B25 CongaDrum
#   17: OPLL SD1            -> B23 Swissnare,B24 Tom C4,B25 CongaDrum
#   18: OPLL TOM1           -> B24 Tom C4,B25 CongaDrum,B26 Tub Bells
#   19: OPLL CLOSED HH      -> B29 Claves,B30 Bells,B31 SteelCans
#   20: OPLL CYM            -> B27 Gong,B28 Timpani,B29 Claves
TX802_MELODY_OPLL_TO_PRESET_A_B = {
    1:  Tx802Voice("A", 11), # A11 Strings
    2:  Tx802Voice("A", 36), # A36 RubbaRoad -
    3:  Tx802Voice("A", 33), # A33 Piano   1
    4:  Tx802Voice("A", 23), # A23 Flute     -
    5:  Tx802Voice("B", 40), # B40 ClariSolo -
    6:  Tx802Voice("A", 20), # A20 Bassoon  -
    7:  Tx802Voice("A", 8),  # A8 SilvaTrmpt -
    8:  Tx802Voice("A", 48), # A48 TouchOrga
    9:  Tx802Voice("A", 10), # A10 FrenchHorn
    10: Tx802Voice("A", 38), # A38 FullTines -
    11: Tx802Voice("A", 41), # A41 Clavecin -
    12: Tx802Voice("B", 21), # B21 VibraPhone -
    13: Tx802Voice("B", 3), # B3 SkweekBass
    14: Tx802Voice("B", 2), # B2 StringBass -
    15: Tx802Voice("B", 11), # ,B11 FingaPicka
}

# ============================================================
# OPLL → TX802 Voice Name Based Mapping Table
# ============================================================
#   1: OPLL Violin          -> A19 Violins
#   2: OPLL Guitar          -> B10 PickGuitar
#   3: OPLL Piano           -> A33 Piano   1
#   4: OPLL Flute           -> A23 Flute
#   5: OPLL Clarinet        -> A21 Clarinet
#   6: OPLL Oboe            -> A22 Oboe
#   7: OPLL Trumpet         -> A07 Trumpet  A
#   8: OPLL Organ           -> A51 BriteOrgan
#   9: OPLL Horn            -> A10 FrenchHorn
#   10: OPLL Synth          -> B43 WhapSynth
#   11: OPLL Harpsichord    -> A44 HarpsiBox
#   12: OPLL Vibraphone     -> B21 VibraPhone
#   13: OPLL SynthBass      -> B48 HarmoSynth
#   14: OPLL AcousticBass   -> A16 BowedBass
#   15: OPLL ElectricGuitar -> B09 GuitarBox

TX802_MELODY_OPLL_TO_OPLL = {
    1:  Tx802Voice("A", 19), # A19 Violins
    2:  Tx802Voice("B", 10), # B10 PickGuitar
    3:  Tx802Voice("A", 23), # A23 Flute
    4:  Tx802Voice("A", 21), # A21 Clarinet
    5:  Tx802Voice("A", 22), # A22 Oboe
    6:  Tx802Voice("A", 7),  # A07 Trumpet  A
    7:  Tx802Voice("A", 21), # A21 Clarinet
    8:  Tx802Voice("A", 51), # A51 BriteOrgan
    9:  Tx802Voice("A", 10), # A10 FrenchHorn
    10: Tx802Voice("B", 43), # B43 WhapSynth
    11: Tx802Voice("A", 44), # A44 HarpsiBox
    12: Tx802Voice("B", 21), # B21 VibraPhone
    13: Tx802Voice("B", 48), # B48 HarmoSynth
    14: Tx802Voice("A", 16), # A16 BowedBass
    15: Tx802Voice("B", 9),  # B09 GuitarBox
}

# ============================================================
# GM → TX802 Voice Name Based Mapping Table
# ============================================================
#   1: OPLL Violin          -> GM 0  Piano       -> A33 Piano   1
#   2: OPLL Guitar          -> GM 6  Harpsi      -> A45 HarpsiWire
#   3: OPLL Piano           -> GM 11 Vibes       -> B21 VibraPhone
#   4: OPLL Flute           -> GM 19 Church Org  -> A51 BriteOrgan
#   5: OPLL Clarinet        -> GM 25 Ac.Gt       -> B09 GuitarBox
#   6: OPLL Oboe            -> GM 27 E.Gt        -> B10 PickGuitar
#   7: OPLL Trumpet         -> GM 32 AcBass      -> B03 SkweekBass
#   8: OPLL Organ           -> GM 38 SynBass     -> B07 JazzBass
#   9: OPLL Horn            -> GM 40 Violin      -> A19 Violins
#   10: OPLL Synth          -> GM 56 Trumpet     -> A07 Trumpet  A
#   11: OPLL Harpsichord    -> GM 60 Brass       -> B42 ClaviBrass
#   12: OPLL Vibraphone     -> GM 68 Oboe        -> A22 Oboe
#   13: OPLL SynthBass      -> GM 71 Clarinet    -> A21 Clarinet
#   14: OPLL AcousticBass   -> GM 73 Flute       -> A23 Flute
#   15: OPLL ElectricGuitar -> GM 81 Lead1       -> B12 LeadaPicka

TX802_MELODY_OPLL_TO_GM = {
    1:  Tx802Voice("A", 33), # A33 Piano   1
    2:  Tx802Voice("A", 45), # A45 HarpsiWire
    3:  Tx802Voice("B", 21), # B21 VibraPhone
    4:  Tx802Voice("A", 51), # A51 BriteOrgan
    5:  Tx802Voice("B", 9),  # B09 GuitarBox
    6:  Tx802Voice("B", 10), # B10 PickGuitar
    7:  Tx802Voice("B", 3),  # B03 SkweekBass
    8:  Tx802Voice("B", 7),  # B07 JazzBass
    9:  Tx802Voice("A", 19), # A19 Violins
    10: Tx802Voice("A", 7),  # A07 Trumpet  A
    11: Tx802Voice("B", 42), # B42 ClaviBrass
    12: Tx802Voice("A", 22), # A22 Oboe
    13: Tx802Voice("A", 21), # A21 Clarinet
    14: Tx802Voice("A", 23), # A23 Flute
    15: Tx802Voice("B", 12), # B12 LeadaPicka
}


# ============================================================
# Custom1 TX802 Voice Name Based Mapping Table
# ============================================================
#   1: OPLL Violin          -> A31 EbonyIvory
#   2: OPLL Guitar          -> A34 Piano 2 
#   3: OPLL Piano           -> A11 Strings
#   4: OPLL Flute           -> B14 12 Strings
#   5: OPLL Clarinet        -> B07 JazzBass
#   6: OPLL Oboe            -> B16 Shami
#   7: OPLL Trumpet         -> B15 Classipika
#   8: OPLL Organ           -> A12 HallOrch
#   9: OPLL Horn            -> A10 FrenchHorn
#   10: OPLL Synth          -> A15 LiveStrg 
#   11: OPLL Harpsichord    -> A45 HarpsWire
#   12: OPLL Vibraphone     -> A12 HallOrch
#   13: OPLL SynthBass      -> B11 FingaPicka
#   14: OPLL AcousticBass   -> B12 LeadaPicka
#   15: OPLL ElectricGuitar -> A14 Analog-Str

TX802_MELODY_OPLL_TO_CUSTOM1 = {
    1:  Tx802Voice("A", 31), # A31 EbonyIvory
    2:  Tx802Voice("A", 34), # A34 Piano 2 
    3:  Tx802Voice("A", 11), # A11 Strings
    4:  Tx802Voice("B", 14), # B14 12 Strings
    5:  Tx802Voice("B", 7),  # B07 JazzBass
    6:  Tx802Voice("B", 16), # B16 Shami
    7:  Tx802Voice("B", 15), # B15 Classipika
    8:  Tx802Voice("A", 12), # A12 HallOrch
    9:  Tx802Voice("A", 10), # A10 FrenchHorn
    10: Tx802Voice("A", 15), # A15 LiveStrg -
    11: Tx802Voice("A", 45), # A45 HarpsWire -
    12: Tx802Voice("A", 12), # A12 HallOrch
    13: Tx802Voice("B", 11), # B11 FingaPicka
    14: Tx802Voice("B", 12), # B12 LeadaPicka
    15: Tx802Voice("A", 14), # A14 Analog-Str - 
}

# TX802 の表示ラベル番号（1-based）では I21 からユーザ音色を割り当てる。
_USER_VOICE_ASSIGN_START = 21
# CSV の voice 列や内部 vnum は 0-based なので、I21 は vnum=20 に対応する。
_USER_VOICE_FIRST_VNUM = 20
assert _USER_VOICE_FIRST_VNUM == _USER_VOICE_ASSIGN_START - 1
# 「未使用」扱いにする TX802 プログラム番号（0-indexed）
_TX802_PROGRAM_UNUSED = 127

def tx802_bank_voice_to_vnum(bank: str, voice: int) -> int:
    """
    TX802 / DX7II の内部アドレス体系に基づく vnum 計算（0–255）。
    Bank:
        I : 0–63
        C : 64–127
        A : 128–191
        B : 192–255
    """
    bank = bank.upper()
    v = voice - 1

    if bank == "I":
        base = 0
    elif bank == "C":
        base = 64
    elif bank == "A":
        base = 128
    elif bank == "B":
        base = 192
    else:
        raise ValueError(f"Unknown TX802 bank: {bank}")

    return base + v



def classify_opl3_to_tx802(feat: Opl3Features2Op) -> Tx802Voice:
    """
    OPL3 2OP 特徴量から、最も近いと思われる TX802 プリセットを推定する。
    - EP / Bell
    - Brass
    - Lead
    - Reed / Wind
    - Bass
    - Strings / Pad
    くらいの大分類でざっくり振り分ける。
    """

    m = feat.mod
    c = feat.car
    fb = feat.fb
    alg = feat.alg

    # ざっくり特徴
    fast_attack = c.ar >= 12 or m.ar >= 12
    slow_attack = c.ar <= 5 and m.ar <= 5
    long_sustain = feat.long_sustain
    percussive = feat.percussive
    bright = feat.bright
    strong_fb = feat.strong_fb
    weak_fb = feat.weak_fb
    vib_used = (m.vib == 1) or (c.vib == 1)

    # 倍音の粗さ
    high_mul = (m.mul >= 4) or (c.mul >= 4)
    low_mul = (m.mul <= 2) and (c.mul <= 2)

    # キャリアの音量感（TL 小さいほど大きい）
    car_loud = c.tl <= 24
    car_soft = c.tl >= 32

    # --------------------------------------------------------
    # 1. EP / Bell 系
    # --------------------------------------------------------
    # ・FB 弱い
    # ・アタック速い
    # ・明るい
    # ・サスティンは短め〜中庸
    if weak_fb and fast_attack and bright and not long_sustain:
        # A11: E.PIANO 1 に寄せる
        return Tx802Voice("A", 11)

    # より Bell / Hard EP 寄り
    if weak_fb and fast_attack and high_mul and bright:
        # A12: E.PIANO 2 / Bell 系
        return Tx802Voice("A", 12)

    # --------------------------------------------------------
    # 2. Brass 系
    # --------------------------------------------------------
    # ・アタック速い
    # ・FB 中程度以上
    # ・MUL 低〜中
    if fast_attack and fb >= 2 and fb <= 5 and low_mul and not percussive:
        # A21: BRASS 1
        return Tx802Voice("A", 21)

    # シンセ寄りブラス
    if fast_attack and fb >= 3 and bright and not percussive:
        # A22: SYN-BRASS
        return Tx802Voice("A", 22)

    # --------------------------------------------------------
    # 3. Lead 系
    # --------------------------------------------------------
    # ・FB 強め
    # ・MUL 高め
    # ・サスティン長め or 中庸
    if strong_fb and high_mul and not percussive:
        # A23: SYN-LEAD 1
        return Tx802Voice("A", 23)

    # 細めのリード
    if strong_fb and bright and not long_sustain:
        # A24: SYN-LEAD 2
        return Tx802Voice("A", 24)

    # --------------------------------------------------------
    # 4. Reed / Wind 系
    # --------------------------------------------------------
    # ・VIB 使用
    # ・MUL 低め
    # ・FB 弱め
    if vib_used and low_mul and fb <= 3 and not percussive:
        # B14: REED / WIND 系
        return Tx802Voice("B", 14)

    # --------------------------------------------------------
    # 5. Bass 系
    # --------------------------------------------------------
    # ・TL 深い（小さくない）
    # ・MUL 低め
    # ・アタック中〜速め
    if car_soft and low_mul and not slow_attack:
        # B11: BASS 1
        return Tx802Voice("B", 11)

    # シンセベース寄り
    if car_soft and high_mul and strong_fb:
        # B12: SYN-BASS
        return Tx802Voice("B", 12)

    # --------------------------------------------------------
    # 6. Strings / Pad 系
    # --------------------------------------------------------
    # ・アタック遅め
    # ・サスティン長い
    if slow_attack and long_sustain and not strong_fb:
        # A31: STRINGS
        return Tx802Voice("A", 31)

    # Pad 系（少し FB あり）
    if long_sustain and fb >= 2 and not bright:
        # B21: PAD 系
        return Tx802Voice("B", 21)

    # --------------------------------------------------------
    # 7. Percussive / Pluck 系
    # --------------------------------------------------------
    # ・アタック速い
    # ・サスティン短い
    if percussive and fast_attack and not long_sustain:
        # A13 あたりでもいいが、ここでは汎用 EP/PLUCK として A11 に逃がす
        return Tx802Voice("A", 11)

    # --------------------------------------------------------
    # 8. Fallback
    # --------------------------------------------------------
    # どう分類しても微妙な場合は汎用リードに逃がす
    return Tx802Voice("A", 23)

def auto_classify_user_patch_tx802(patch_bytes: bytes) -> Tx802Voice:
    """
    YM2413 パッチを TX802 の最適プリセットに自動分類する。
    - OPLL → MGSDRV 形式に変換したパラメータを元に
    - 音色の「傾向」から TX802 プリセットを推定する
    """

    d = _ym2413_patch_to_mgsdrv(patch_bytes)
    tl, fb = d["tl"], d["fb"]
    m = d["mod"]
    c = d["car"]

    # modulator
    m_ar = m[0]
    m_dr = m[1]
    m_sl = m[2]
    m_rr = m[3]
    m_ks = m[4]
    m_mul = m[5]
    m_eg = m[6]
    m_vib = m[7]

    # carrier
    c_ar = c[0]
    c_dr = c[1]
    c_sl = c[2]
    c_rr = c[3]
    c_ks = c[4]
    c_mul = c[5]
    c_eg = c[6]
    c_vib = c[7]


    # ざっくり特徴量
    fast_attack = c_ar >= 12 or m_ar >= 12
    slow_attack = c_ar <= 5 and m_ar <= 5
    long_sustain = c_sl >= 8 or m_sl >= 8
    short_sustain = c_sl <= 3 and m_sl <= 3
    bright = tl <= 16 and (m_mul >= 3 or c_mul >= 3)
    dark = tl >= 24 and m_mul <= 2 and c_mul <= 2
    strong_fb = fb >= 4
    weak_fb = fb == 0
    vib_used = (m_vib == 1) or (c_vib == 1)

    # ─────────────────────────────────────
    # 1. EP / Bell 系
    # ─────────────────────────────────────
    # ・FB=0
    # ・アタック速い
    # ・サスティン短め or 中庸
    if weak_fb and fast_attack and not long_sustain and bright:
        # A11: E.PIANO 1
        return Tx802Voice("A", 11)

    # Bell 系（より硬い・高倍音）
    if weak_fb and fast_attack and bright and (m_mul >= 4 or c_mul >= 4):
        # A12: E.PIANO 2 / Bell 系に寄せる
        return Tx802Voice("A", 12)

    # ─────────────────────────────────────
    # 2. Brass 系
    # ─────────────────────────────────────
    # ・アタック速い
    # ・FB 中程度以上
    # ・MUL 低〜中
    if fast_attack and fb >= 2 and fb <= 5 and c_mul <= 4 and not short_sustain:
        # A21: BRASS 1
        return Tx802Voice("A", 21)

    # よりシンセ寄りブラス
    if fast_attack and strong_fb and bright:
        # A22: BRASS 2 / SYN-BRASS 系
        return Tx802Voice("A", 22)

    # ─────────────────────────────────────
    # 3. Lead 系
    # ─────────────────────────────────────
    # ・FB 強め
    # ・MUL 高め
    # ・サスティン長め or 中庸
    if strong_fb and (m_mul >= 4 or c_mul >= 4) and not short_sustain:
        # A23: SYN-LEAD 1
        return Tx802Voice("A", 23)

    # より細いリード
    if strong_fb and bright and short_sustain:
        # A24: SYN-LEAD 2
        return Tx802Voice("A", 24)

    # ─────────────────────────────────────
    # 4. Reed / Wind 系
    # ─────────────────────────────────────
    # ・VIB 使用
    # ・MUL 低め
    # ・FB 弱め
    if vib_used and m_mul <= 3 and c_mul <= 3 and fb <= 3:
        # B14: REED
        return Tx802Voice("B", 14)

    # ─────────────────────────────────────
    # 5. Bass 系
    # ─────────────────────────────────────
    # ・TL 深い
    # ・MUL 低め
    # ・アタック中〜速め
    if tl >= 20 and m_mul <= 3 and c_mul <= 3 and not slow_attack:
        # B11: BASS 1
        return Tx802Voice("B", 11)

    # よりシンセ寄りベース
    if tl >= 20 and (m_mul >= 3 or c_mul >= 3) and strong_fb:
        # B12: SYN-BASS
        return Tx802Voice("B", 12)

    # ─────────────────────────────────────
    # 6. Strings / Pad 系
    # ─────────────────────────────────────
    # ・アタック遅め
    # ・サスティン長い
    if slow_attack and long_sustain and not strong_fb:
        # A31: STRINGS
        return Tx802Voice("A", 31)

    # Pad 系（少し FB 強め）
    if long_sustain and fb >= 2 and not bright:
        # B21: PAD 系
        return Tx802Voice("B", 21)

    # ─────────────────────────────────────
    # 7. Fallback
    # ─────────────────────────────────────
    # どう分類しても微妙な場合は汎用リードに逃がす
    return Tx802Voice("A", 23)

def _distance_opll_to_tx802(mgs, txv):
    """
    MGSDRV パラメータと TX802 プリセットの距離を計算する。
    txv は TX802_VOCES_AB の 1 要素（dict）
    """

    # MGSDRV
    tl = mgs["tl"]
    fb = mgs["fb"]
    m = mgs["mod"]
    c = mgs["car"]

    # TX802
    def g(key, default=0):
        return int(txv.get(key, default))

    # 距離計算（L1 ノルム）
    dist = 0

    # FB
    dist += abs(fb - g("FB"))

    # TL → キャリア TL に寄せる
    dist += abs(tl - g("OP2_TL"))

    # Modulator
    dist += abs(m[0] - g("OP1_AR"))
    dist += abs(m[1] - g("OP1_DR"))
    dist += abs(m[2] - g("OP1_SL"))
    dist += abs(m[3] - g("OP1_RR"))
    dist += abs(m[4] - g("OP1_KSL"))
    dist += abs(m[5] - g("OP1_MULTI"))
    dist += abs(m[6] - g("OP1_AM"))
    dist += abs(m[7] - g("OP1_VIB"))

    # Carrier
    dist += abs(c[0] - g("OP2_AR"))
    dist += abs(c[1] - g("OP2_DR"))
    dist += abs(c[2] - g("OP2_SL"))
    dist += abs(c[3] - g("OP2_RR"))
    dist += abs(c[4] - g("OP2_KSL"))
    dist += abs(c[5] - g("OP2_MULTI"))
    dist += abs(c[6] - g("OP2_AM"))
    dist += abs(c[7] - g("OP2_VIB"))

    return dist


def classify_user_patch_by_distance_tx802(patch_bytes: bytes) -> Tx802Voice:
    """
    OPLL パッチを TX802 プリセットの中から
    距離計算で最も近いものを返す。
    """

    mgs = _ym2413_patch_to_mgsdrv(patch_bytes)

    best = None
    best_dist = 999999

    for txv in TX802_VOCES_AB:
        dist = _distance_opll_to_tx802(mgs, txv)
        if dist < best_dist:
            best_dist = dist
            best = txv

    if best is None:
        return Tx802Voice("A", 23)

    return Tx802Voice(best["bank"], best["voice"])

def _is_user_voice_csv_append_target(entry: dict) -> bool:
    """Return True when the mapping points to a TX802 user slot (I21+)."""
    if not isinstance(entry, dict):
        return False
    bank = str(entry.get("bank", "")).upper()
    try:
        voice = int(entry.get("voice", 0))
    except (TypeError, ValueError):
        return False
    return bank == "I" and voice >= _USER_VOICE_ASSIGN_START

def _build_user_voice_tx802_map(
    user_patches: dict[int, bytes],
    existing_map: dict[str, dict],
) -> tuple[dict[int, dict], dict[str, dict]]:

    at_v_to_tx802: dict[int, dict] = {}
    updated = dict(existing_map)

    # 既存の I バンクのユーザスロット（I21+）を収集
    used_i_label_voices = {
        v["voice"]
        for v in updated.values()
        if isinstance(v, dict)
        and str(v.get("bank", "")).upper() == "I"
        and int(v.get("voice", 0)) >= _USER_VOICE_ASSIGN_START
    }

    # 次に割り当てる I バンクのユーザスロット番号
    next_i_label_voice = _USER_VOICE_ASSIGN_START
    while next_i_label_voice in used_i_label_voices:
        next_i_label_voice += 1

    for at_v_num, patch_bytes in user_patches.items():
        patch_hex = patch_bytes.hex()

        # 1. all-zero → ユーザスロットは消費せず、適当なプリセットに逃がす
        if _is_zero_patch(patch_bytes):
            entry = {
                "bank": "A",
                "voice": 11,  # A11 Strings あたりに退避
                "label": "Unused (all-zero)",
            }
            at_v_to_tx802[at_v_num] = entry
            updated[patch_hex] = entry
            continue

        # 2. 既存マップがあればそれを優先（I1 もそのままプリセット扱い）
        if patch_hex in updated:
            entry = updated[patch_hex]
            at_v_to_tx802[at_v_num] = entry
            # もし I21+ なら used_i_label_voices に反映
            if (
                str(entry.get("bank", "")).upper() == "I"
                and int(entry.get("voice", 0)) >= _USER_VOICE_ASSIGN_START
            ):
                used_i_label_voices.add(int(entry["voice"]))
            continue

        # 3. 新規ユーザパッチ → I21 以降に割り当てる
        entry = {
            "bank": "I",
            "voice": next_i_label_voice,
            "label": f"I{next_i_label_voice}",
        }

        at_v_to_tx802[at_v_num] = entry
        updated[patch_hex] = entry
        used_i_label_voices.add(next_i_label_voice)
        next_i_label_voice += 1

    return at_v_to_tx802, updated

def _load_opll_preset_op2_rows(
    base_csv_path: str = _OPLL_PRESET_OP2_CSV,
) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with open(base_csv_path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            if not fieldnames:
                raise ValueError("missing CSV header")
            rows = [{name: row.get(name, "") for name in fieldnames} for row in reader]
    except OSError as exc:
        raise FileNotFoundError(
            f"Failed to load base OPLL voice CSV '{base_csv_path}': {exc}"
        ) from exc

    if not rows:
        raise ValueError(f"Base OPLL voice CSV '{base_csv_path}' has no rows")
    return fieldnames, rows


def _opll_patch_to_op2_row(voice: int, name: str, patch_bytes: bytes) -> dict[str, str]:
    d = _ym2413_patch_to_mgsdrv(patch_bytes)
    mod = d["mod"]
    car = d["car"]

    return {
        "voice": str(voice),
        "name": name,
        "ALG": "0",
        "FB": str(d["fb"]),
        "OP1_AR": str(mod[0]),
        "OP1_DR": str(mod[1]),
        "OP1_SL": str(mod[2]),
        "OP1_RR": str(mod[3]),
        "OP1_TL": str(d["tl"]),
        "OP1_KSL": str(mod[4]),
        "OP1_MULTI": str(mod[5]),
        "OP1_KSR": str(mod[9]),
        "OP1_AM": str(mod[6]),
        "OP1_VIB": str(mod[7]),
        "OP1_EGT": str(mod[8]),
        "OP1_WS": "0",
        "OP2_AR": str(car[0]),
        "OP2_DR": str(car[1]),
        "OP2_SL": str(car[2]),
        "OP2_RR": str(car[3]),
        "OP2_TL": "0",
        "OP2_KSL": str(car[4]),
        "OP2_MULTI": str(car[5]),
        "OP2_KSR": str(car[9]),
        "OP2_AM": str(car[6]),
        "OP2_VIB": str(car[7]),
        "OP2_EGT": str(car[8]),
        "OP2_WS": "0",
    }


def build_user_voice_tx802_csv(
    base_name: str,
    user_patches: dict[int, bytes],
    user_voice_tx802_map: dict[int, dict],
    output_dir: str = _VOICE_CSV_DIR,
) -> str:
    base_csv_path = _OPLL_PRESET_OP2_CSV
    fieldnames, preset_rows = _load_opll_preset_op2_rows(base_csv_path)
    rows = list(preset_rows)
    
    user_rows: list[tuple[int, dict[str, str]]] = []
    for at_v_num, patch_bytes in user_patches.items():
        entry = user_voice_tx802_map.get(at_v_num)
        if entry is None:
            continue
        if not _is_user_voice_csv_append_target(entry):
            continue
        label_voice = int(entry["voice"])
        voice = label_voice - 1
        label = entry.get("label") or f"I{label_voice}"
        name = f"{label} User patch v{at_v_num}"
        user_rows.append((voice, _opll_patch_to_op2_row(voice, name, patch_bytes)))

    user_rows.sort(key=lambda item: item[0])
    for _, row in user_rows:
        rows.append({field: row.get(field, "") for field in fieldnames})

    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    out_path = os.path.join(tables_dir, f"{base_name}_voice.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_path

def _reverse_lookup_tx802_voice(vnum: int) -> Tx802Voice | None:
    """
    内部 vnum (0–127) から Tx802Voice(bank, voice) を推定する。
    to_vnum() の逆写像として使う補助関数。
    実機のバンク構成に合わせて必要なら調整。
    """
    # I バンク
    if 0 <= vnum < 32:
        return Tx802Voice("I", vnum + 1)
    # C バンク
    if 64 <= vnum < 96:
        return Tx802Voice("C", (vnum - 64) + 1)
    # A バンク（to_vnum では 128+v を返しているので、そのままでは戻せない。
    # 実際には vnum & 0x7F などでマスクされる前提なら、ここは環境に合わせて調整が必要）
    # B バンクも同様。ここでは None を返すフォールバックにしておく。
    return None

def _format_user_patch_lines_tx802(
    at_v_num: int,
    patch_bytes: bytes,
    tx802_prog: dict,
    tx802_voice: dict,
    vnum: int,
):
    lines = []

    lines.append(
        f"User patch v{at_v_num}: TX802 {tx802_prog['bank']}{tx802_prog['voice']} (vnum={vnum})"
    )

    regs = patch_bytes.hex().upper()
    lines.append(f"Inst {vnum}: regs = {' '.join(regs[i:i+2] for i in range(0, 16, 2))}")

    # MGSDRV 形式のパラメータを表示
    d = _ym2413_patch_to_mgsdrv(patch_bytes)
    tl, fb = d["tl"], d["fb"]
    m = d["mod"]
    c = d["car"]

    lines.append(f"\tTL={tl} FB={fb}")
    lines.append(
        f"\tMO: AR={m[0]:2} DR={m[1]:2} SL={m[2]:2} RR={m[3]:2} KL={m[4]} MT={m[5]} AM={m[6]} VB={m[7]} EG={m[6]} KR={m[4]} DT=0"
    )
    lines.append(
        f"\tCA: AR={c[0]:2} DR={c[1]:2} SL={c[2]:2} RR={c[3]:2} KL={c[4]} MT={c[5]} AM={c[6]} VB={c[7]} EG={c[6]} KR={c[4]} DT=0"
    )

    return lines

def _user_voice_tx802_map_path(output_dir: str, base_name: str) -> str:
    return os.path.join(output_dir, f"{base_name}.user_voice_tx802.json")

def _save_user_voice_tx802_map(path: str, updated_map: dict[str, dict]):
    """
    Save TX802 user voice map JSON.
    JSON には bank / voice / label のみ保存し、
    vnum は保存しない（Python 側で自動計算する）。
    """

    out = {}
    voice_info = {}

    for patch_hex, entry in updated_map.items():
        bank = entry["bank"]
        voice = entry["voice"]
        label = entry.get("label", "")

        # JSON に保存するのは bank / voice / label のみ
        out[patch_hex] = {
            "bank": bank,
            "voice": voice,
            "label": label
        }

        # コメント用に vnum を計算
        vnum = tx802_bank_voice_to_vnum(bank, voice)

        voice_info[patch_hex] = [
            f"TX802 {bank}{voice} (vnum={vnum})",
            f"Inst {vnum}: regs = {patch_hex}"
        ]

    out["_voice_info"] = voice_info

    with open(path, "w") as f:
        json.dump(out, f, indent=2)

def _load_user_voice_tx802_map(path: str) -> dict[str, dict]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        result = {}
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if isinstance(k, str) and isinstance(v, dict):
                result[k.lower()] = v
        return result
    except Exception:
        return {}

def save_tx802_voice_syx(path: str, syx_bytes: bytes):
    with open(path, "wb") as f:
        f.write(syx_bytes)

def build_tx802_voice_sysex(txv_params: dict, name: str = "OPLL"):
    """
    txv_params: {
        "op1": { "ar":.., "dr":.., "sl":.., "rr":.., "tl":.., "rs":.., "dt":.., "mul":.., "am":.. },
        "op2": { ... },
        "fb": int,
        "alg": int
    }
    """

    def op_block(op):
        # TX802 operator block (17 bytes)
        return [
            op["ar"], op["dr"], op["sl"], op["rr"],
            op["tl"], op["rs"], op["dt"], op["mul"],
            op["am"], 0, 0, 0, 0, 0, 0, 0, 0
        ]

    # OP1, OP2 は OPLL から生成
    op1 = op_block(txv_params["op1"])
    op2 = op_block(txv_params["op2"])

    # OP3, OP4 はデフォルト（無音）
    op3 = [0]*17
    op4 = [0]*17

    # Pitch EG（デフォルト）
    peg = [0, 0, 0, 0]

    # Algorithm / Feedback
    alg = txv_params.get("alg", 0)
    fb  = txv_params.get("fb", 0)

    # LFO（デフォルト）
    lfo = [0, 0, 0, 0, 0]

    # Name（10 bytes）
    name_bytes = [ord(c) & 0x7F for c in name[:10]]
    name_bytes += [32] * (10 - len(name_bytes))

    # 残りは 86 bytes の 0x00
    tail = [0] * 86

    # 155 bytes voice data
    voice_data = (
        op1 + op2 + op3 + op4 +
        peg +
        [alg, fb] +
        lfo +
        name_bytes +
        tail
    )

    # SysEx header
    syx = [0xF0, 0x43, 0x00, 0x09, 0x20, 0x00]
    syx += voice_data
    syx.append(0xF7)

    return bytes(syx)


def get_tx802_melody_voice(opll_patch: int, melody_mode: str = "default") -> Tx802Voice:
    tables = {
        "default": TX802_MELODY_OPLL_TO_DEFAULT,
        "gm": TX802_MELODY_OPLL_TO_GM,
        "opll": TX802_MELODY_OPLL_TO_OPLL,
    }

    table = tables.get(melody_mode, TX802_MELODY_OPLL_TO_DEFAULT)

    # opll_patch は「instそのもの」（1..20）を渡す
    return table.get(opll_patch, Tx802Voice("I", 1))


def compute_portamento_time_tx802(prev_note, next_note, tick_length, bpm):
    # 音程差（半音）
    diff = abs(next_note - prev_note)

    # ノート長（秒）
    sec = tick_length * (60.0 / (bpm * ppq))

    # TX802 の CC5 は指数カーブなので補正
    # diff=12（1oct）で CC5=25〜35 が自然
    base = diff * 2.2

    # ノート長が短い場合は短縮
    if sec < 0.2:
        base *= 0.6
    elif sec > 0.5:
        base *= 1.3

    # CC5 の範囲に収める
    return int(max(1, min(63, base)))

VELOCITY_SENS_TABLE = {
    "piano": 1.00,
    "epiano": 0.90,
    "clav": 0.85,
    "brass": 0.70,
    "strings": 0.60,
    "pad": 0.40,
    "bass": 0.75,
    "lead": 0.80,
}

# OPLL VOL → TX802 MIDI Velocity
# Velocity Sensitivity = 7
#
# The mapping is derived from the DX7 velocity response data
# and scaling algorithm used by Google's
# music-synthesizer-for-android.
#
# Source:
# https://github.com/google/music-synthesizer-for-android/blob/master/app/src/main/jni/dx7note.cc
def compute_velocity_tx802(seg, is_portamento: bool = False) -> int:
    opll_vol = getattr(seg, "vol", 15)

    # OPLL VOL → TX802 MIDI Velocity
    # Velocity Sensitivity = 7 前提
    #
    # OPLL:
    #   VOL 0  =   0 dB
    #   VOL 1  =  -3 dB
    #   ...
    #   VOL 15 = -45 dB
    #
    # TX802 / DX7 velocity curve:
    #   VOL 0  → Velocity 98
    #   VOL 1  → Velocity 86
    #   VOL 2  → Velocity 76
    #   VOL 3  → Velocity 68
    #   VOL 4  → Velocity 60
    #   VOL 5  → Velocity 52
    #   VOL 6  → Velocity 44
    #   VOL 7  → Velocity 38
    #   VOL 8  → Velocity 32
    #   VOL 9  → Velocity 26
    #   VOL 10 → Velocity 22
    #   VOL 11 → Velocity 18
    #   VOL 12 → Velocity 14
    #   VOL 13 → Velocity 12
    #   VOL 14 → Velocity 10
    #   VOL 15 → Velocity 6

    velocity_map = [
        98,  # VOL 0
        86,  # VOL 1
        76,  # VOL 2
        68,  # VOL 3
        60,  # VOL 4
        52,  # VOL 5
        44,  # VOL 6
        38,  # VOL 7
        32,  # VOL 8
        26,  # VOL 9
        22,  # VOL 10
        18,  # VOL 11
        14,  # VOL 12
        12,  # VOL 13
        10,  # VOL 14
        6,   # VOL 15
    ]

    # 範囲外への安全対策
    opll_vol = max(0, min(15, opll_vol))

    v = velocity_map[opll_vol]

    # ポルタメント補正（必要ならここで有効化）
    # if is_portamento:
    #     v = int(v * 0.90)

    return max(1, min(127, v))

def tx802_append_init_events(builder, time0=0):
    """
    Domino TX802 初期化シーケンスを MidiBuilder に追加する。
    builder: MidiBuilder インスタンス
    time0: すべてのイベントを置く tick（通常 0）
    """

    def add_sysex(data, order=0):
        builder.add_event(time0, bytes(data), order=order)

    def add_cc(ch, cc, val, order=0):
        builder.add_event(time0, bytes([0xB0 | ch, cc, val]), order=order)

    def add_cp(ch, val, order=0):
        builder.add_event(time0, bytes([0xD0 | ch, val]), order=order)

    def add_pb(ch, val14, order=0):
        lo = val14 & 0x7F
        hi = (val14 >> 7) & 0x7F
        builder.add_event(time0, bytes([0xE0 | ch, lo, hi]), order=order)

    channels = range(8)

    # --- TG1〜TG8 Voice Number 初期化 ---
    sysex1 = [
        [0xF0,0x43,0x10,0x1A,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x08,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x01,0x01,0xF7],
        [0xF0,0x43,0x10,0x1A,0x09,0x01,0xF7],
        [0xF0,0x43,0x10,0x1A,0x02,0x02,0xF7],
        [0xF0,0x43,0x10,0x1A,0x0A,0x02,0xF7],
        [0xF0,0x43,0x10,0x1A,0x03,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x0B,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x04,0x04,0xF7],
        [0xF0,0x43,0x10,0x1A,0x0C,0x04,0xF7],
        [0xF0,0x43,0x10,0x1A,0x05,0x05,0xF7],
        [0xF0,0x43,0x10,0x1A,0x0D,0x05,0xF7],
        [0xF0,0x43,0x10,0x1A,0x06,0x06,0xF7],
        [0xF0,0x43,0x10,0x1A,0x0E,0x06,0xF7],
        [0xF0,0x43,0x10,0x1A,0x07,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x0F,0x07,0xF7],
    ]
    for s in sysex1:
        add_sysex(s, order=1)

    # --- CC 初期化 ---
    for ch in channels:
        add_cc(ch, 1, 0,   order=2)   # Mod
        add_cc(ch, 2, 127, order=2)   # Breath
        add_cc(ch, 4, 127, order=2)   # Foot
        add_cc(ch, 5, 0,   order=2)   # Porta Time
        add_cc(ch, 0x40, 0, order=2)  # Sustain
        add_cc(ch, 0x41, 0, order=2)  # Porta Sw
        add_cp(ch, 0,      order=2)   # Aftertouch
        add_pb(ch, 0x2000, order=2)   # PB center

    # --- TG Note Shift / Output Assign ---
    sysex2 = [
        [0xF0,0x43,0x10,0x1A,0x10,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x11,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x12,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x13,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x14,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x15,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x16,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x17,0x00,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x48,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x49,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x4A,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x4B,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x4C,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x4D,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x4E,0x00,0xF7],
        [0xF0,0x43,0x10,0x1A,0x4F,0x00,0xF7],
    ]
    for s in sysex2:
        add_sysex(s, order=3)

    # --- Volume ---
    for ch in channels:
        add_cc(ch, 7, 127, order=4)

    # --- EG Forced Damp / PB Range / Detune ---
    sysex3 = [
        [0xF0,0x43,0x10,0x1A,0x28,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x29,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x2A,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x2B,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x2C,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x2D,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x2E,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x2F,0x03,0xF7],
        [0xF0,0x43,0x10,0x1A,0x40,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x41,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x42,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x43,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x44,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x45,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x46,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x47,0x18,0xF7],
        [0xF0,0x43,0x10,0x1A,0x18,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x19,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x1A,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x1B,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x1C,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x1D,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x1E,0x07,0xF7],
        [0xF0,0x43,0x10,0x1A,0x1F,0x07,0xF7],
    ]
    for s in sysex3:
        add_sysex(s, order=5)

def midi_builder_tx802(
    segments_by_ch: dict,
    bpm: int,
    ppq: int = DEFAULT_PPQ,
    track_name: str = "vgm2midi",
    user_voice_tx802_map: dict[int, dict] | None = None,
    melody_mode: str = "default",
    rhythm_mode: str = "rx21",
    domino_compat_init: bool = True,
    domino_init_lead_ticks: int = 12,
) -> MidiBuilder:

    builder = MidiBuilder(ppq=ppq, smf_format=1)

    # ------------------------------------------------------------
    # TX802 が扱うチャンネルは 0〜9 のみ
    # ------------------------------------------------------------
    TX802_VALID_CHS = list(TX802_CHANNEL_TO_TRACK.keys())   # [0..9]
    DRUM_SRC_CHS = {9, 10, 11, 12, 13}                      # OPLL側のリズム展開
    DRUM_MIDI_CH = 9                                        # TX802ではドラムは ch9 に統合
    DRUM_TRACK = TX802_CHANNEL_TO_TRACK[DRUM_MIDI_CH]

    # ------------------------------------------------------------
    # 必須の初期化
    # ------------------------------------------------------------
    last_bank_by_ch: dict[int, tuple[int, int]] = {}
    last_program_by_ch: dict[int, int] = {}
    last_note_by_ch: dict[int, int] = {}
    last_melody_event_tick_by_ch: dict[int, int] = {}

    initialized_melody_channels: set[int] = set()
    used_melody_channels: set[int] = set()

    # ------------------------------------------------------------
    # Track0: meta
    # ------------------------------------------------------------
    builder.add_event(0, _tempo_meta_event(bpm), order=0, track=0)
    builder.add_event(0, _track_name_meta_event(track_name), order=1, track=0)

    # ------------------------------------------------------------
    # Bank → MSB/LSB
    # ------------------------------------------------------------
    def _bank_to_msb_lsb(bank_name: str) -> tuple[int, int]:
        b = (bank_name or "I").upper()
        if b == "A": return (1, 0)
        if b == "B": return (1, 1)
        if b == "C": return (0, 1)
        return (0, 0)  # I バンク

    # ------------------------------------------------------------
    # Domino 初期化ブロック（メロディのみ）
    # ------------------------------------------------------------
    def _add_domino_init_block(ch: int, msb: int, lsb: int, program: int, tick: int = 0):
        track_no = TX802_CHANNEL_TO_TRACK[ch]
        builder.add_event(tick, bytes([0xB0 | ch, 121, 0]), order=2, track=track_no)
        builder.add_event(tick, bytes([0xB0 | ch, 0, msb]), order=3, track=track_no)
        builder.add_event(tick, bytes([0xB0 | ch, 32, lsb]), order=4, track=track_no)
        builder.add_event(tick, bytes([0xC0 | ch, program]), order=5, track=track_no)
        builder.add_event(tick, bytes([0xB0 | ch, 7, 100]), order=6, track=track_no)
        builder.add_event(tick, bytes([0xB0 | ch, 11, 127]), order=7, track=track_no)
        builder.add_event(tick, bytes([0xB0 | ch, 10, 64]), order=8, track=track_no)
        builder.add_event(tick, bytes([0xB0 | ch, 1, 0]), order=9, track=track_no)
        builder.add_event(tick, bytes([0xB0 | ch, 64, 0]), order=10, track=track_no)
        builder.add_event(tick, bytes([0xE0 | ch, 0, 64]), order=11, track=track_no)

    lead_ticks = max(0, int(domino_init_lead_ticks)) if domino_compat_init else 0

    # ------------------------------------------------------------
    # まず OPLL のリズム展開 ch(9〜13) を TX802 ch9 に統合
    # ------------------------------------------------------------
    drum_mapper = map_rx21_drum

    for src_ch in DRUM_SRC_CHS:
        for event in build_drum_note_events(
            segments_by_ch.get(src_ch, []),
            ch=DRUM_MIDI_CH,     # TX802では常に ch9
            bpm=bpm,
            ppq=ppq,
            drum_note_mapper=drum_mapper,
            use_channel_drum=True,
        ):
            vel = _opll_vol_to_velocity(getattr(event.segment, "vol", 15))

            builder.add_event(
                event.start_tick,
                bytes([0x99, event.note, vel]),
                order=30,
                track=DRUM_TRACK,
            )
            builder.add_event(
                event.end_tick,
                bytes([0x89, event.note, 0]),
                order=40,
                track=DRUM_TRACK,
            )

    # ------------------------------------------------------------
    # 次にメロディ ch0〜8 を処理（TX802_VALID_CHS = 0..9）
    # ------------------------------------------------------------
    for ch in TX802_VALID_CHS:
        if ch == DRUM_MIDI_CH:
            continue  # ドラムは上で処理済み

        track_no = TX802_CHANNEL_TO_TRACK[ch]

        for event in build_melody_note_events(
            segments_by_ch.get(ch, []),
            ch=ch,
            bpm=bpm,
            ppq=ppq,
        ):
            
            if event.note is None:
                # inst=0 の音色変更イベントなど、note を持たないケースはスキップ
                continue

            start_tick = event.start_tick + lead_ticks
            end_tick = event.end_tick + lead_ticks

            midi_ch = ch
            used_melody_channels.add(midi_ch)

            # --------------------------------------------------------
            # Voice 選択
            # --------------------------------------------------------
            inst = event.inst

            if inst == 0:
                # vgm: inst=0 → OPLL ユーザパッチ
                # → TX802 I21 以降（user_voice_tx802_map に従う）
                at_v_num = _at_token_to_user_v_num(event.at_token)
                if at_v_num is not None and user_voice_tx802_map and at_v_num in user_voice_tx802_map:
                    entry = user_voice_tx802_map[at_v_num]
                    bank = entry["bank"]
                    voice = int(entry["voice"])
                    # TX802 Internal bank の program 番号 (0–63) に変換
                    program = max(0, min(63, voice - 1))
                else:
                    # ユーザマップが無い場合は安全に I1 にフォールバック
                    bank = "I"
                    voice = 1
                    program = 0
            else:
                # vgm: inst=1..14 → OPLL preset melody (Violin..ElectricGuitar)
                #      inst=15..19 → OPLL rhythm (BD1..CYM) だが、
                #      メロディ側では 1..15 を get_tx802_melody_voice で解決
                txv = get_tx802_melody_voice(inst, melody_mode)
                if txv is None:
                    bank = "I"
                    voice = 1
                    program = 0
                else:
                    bank = txv.bank
                    voice = txv.voice
                    program = max(0, min(63, voice - 1))

            msb, lsb = _bank_to_msb_lsb(bank)

            # --------------------------------------------------------
            # Domino 初期化（CHごとに1回）
            # --------------------------------------------------------
            if domino_compat_init and midi_ch not in initialized_melody_channels:
                _add_domino_init_block(midi_ch, msb, lsb, program, tick=0)
                initialized_melody_channels.add(midi_ch)
                last_bank_by_ch[midi_ch] = (msb, lsb)
                last_program_by_ch[midi_ch] = program

            # --------------------------------------------------------
            # Bank Select (CC0 + CC32)
            # --------------------------------------------------------
            bank_tick = max(0, start_tick - 1)
            if last_bank_by_ch.get(midi_ch) != (msb, lsb):
                builder.add_event(bank_tick, bytes([0xB0 | midi_ch, 0x00, msb]), order=8, track=track_no)
                builder.add_event(bank_tick, bytes([0xB0 | midi_ch, 0x20, lsb]), order=9, track=track_no)
                last_bank_by_ch[midi_ch] = (msb, lsb)

            # --------------------------------------------------------
            # Program Change
            # --------------------------------------------------------
            if last_program_by_ch.get(midi_ch) != program:
                builder.add_event(start_tick, bytes([0xC0 | midi_ch, program]), order=10, track=track_no)
                last_program_by_ch[midi_ch] = program

            # --------------------------------------------------------
            # CC11
            # --------------------------------------------------------
            cc11 = compute_cc11(event.segment)
            builder.add_event(start_tick, bytes([0xB0 | midi_ch, 11, cc11]), order=18, track=track_no)

            # --------------------------------------------------------
            # Note On / Off
            # --------------------------------------------------------
            is_portamento = bool(getattr(event, "is_portamento", 0))
            velocity = compute_velocity_tx802(event.segment, is_portamento=is_portamento)

            builder.add_event(start_tick, bytes([0x90 | midi_ch, event.note, velocity]), order=20, track=track_no)
            builder.add_event(end_tick, bytes([0x80 | midi_ch, event.note, 0]), order=40, track=track_no)

            last_note_by_ch[midi_ch] = event.note
            last_melody_event_tick_by_ch[midi_ch] = max(
                last_melody_event_tick_by_ch.get(midi_ch, 0), end_tick
            )

    # ------------------------------------------------------------
    # 曲末の All Notes Off
    # ------------------------------------------------------------
    if domino_compat_init and used_melody_channels:
        stop_tick = max(last_melody_event_tick_by_ch.values(), default=0) + 1
        for ch in sorted(used_melody_channels):
            track_no = TX802_CHANNEL_TO_TRACK[ch]
            builder.add_event(stop_tick, bytes([0xB0 | ch, 64, 0]), order=90, track=track_no)
            builder.add_event(stop_tick, bytes([0xB0 | ch, 123, 0]), order=91, track=track_no)

    return builder
