# ✅ **OPLL → TX802 Converter — Stable MIDI Output Specification (Official, vnum + 4‑bank)**  
**Version: 3.0（完全修正版）**  
**Author: Kentaro & Copilot**  
**Target: Yamaha TX802**

---

# 🎯 目的  
OPLL→TX802 変換器は、VGM の OPLL 音源データを TX802 の 6OP FM 音色に変換し、  
**どの MIDI プレーヤーでも安定して TX802 が正しい音色・正しい音量で演奏できる MIDI を生成すること**を目的とする。

TX802 は **前の演奏状態を保持する FM 音源**であるため、  
Bank / Program / Expression の初期化順序が乱れると音色がズレたり音量が乱れる。  
（引用）「TX802 は **前の演奏状態を保持する FM 音源**であるため」

---

# 1. 🎼 MIDI Format の選択（Format 1 を公式採用）

- TX802 はチャンネルごとに独立した状態を持つ  
- CC0/CC32/CC11 の直前挿入が Format 1 の方が安全  
- Domino CCMR も Format 1  
- GM/GS/XG プレーヤー互換性が高い

📌 **結論：Format 1 を標準出力とする。**

---

# 2. 🎛 TX802 のバンク仕様（vnum + 4‑bank 正式版）

## 2.1 TX802 Internal Voice Number (vnum)

TX802 の音色は **内部ボイス番号 vnum（0〜255）で一意に決まる**。

```python
@dataclass(frozen=True)
class Tx802Voice:
    bank: str   # "I", "C", "A", "B"
    voice: int  # 1..64

    def to_vnum(self) -> int:
        v = self.voice - 1
        if self.bank == "I": return 0   + v
        if self.bank == "C": return 64  + v
        if self.bank == "A": return 128 + v
        if self.bank == "B": return 192 + v
        return v
```

---

## 2.2 TX802 の 4バンク × 64音色構造（正しい完全版）

| Bank | vnum範囲 | Offset | 内容 |
|------|-----------|--------|------|
| **I** | 0–63 | 0 | Internal（RAM） |
| **C** | 64–127 | 64 | Cartridge（RAM） |
| **A** | 128–191 | 128 | Preset A（ROM） |
| **B** | 192–255 | 192 | Preset B（ROM） |

---

## 2.3 **MIDI Bank Select（CC0/CC32）— 4bank 正式仕様**

TX802 は **CC0（MSB）＋CC32（LSB）＝2bit で I/A/C/B を完全選択する**。

| Bank | CC0 | CC32 |
|------|-----|------|
| **I** | 0 | 0 |
| **C** | 1 | 0 |
| **A** | 0 | 1 |
| **B** | 1 | 1 |

### ✔ 正しい生成コード

```python
if bank == "I": msb, lsb = 0, 0
elif bank == "C": msb, lsb = 1, 0
elif bank == "A": msb, lsb = 0, 1
elif bank == "B": msb, lsb = 1, 1
```

📌 **CC32=0固定は誤り。  
TX802 は 4bank を CC0/CC32 で完全選択できる。**

---

## 2.4 Program Change の扱い

Program Change は **バンク内の 1〜64 を選ぶだけ**。

```
program = voice - 1   # 0..63
vnum = bank_offset + program
```

---

## 2.5 Converter が使用するバンク（PR15）

- Internal I01〜I15 を使用  
- vnum = 0〜14  
- CC0=0, CC32=0  
- PC = 0〜14

---

# 3. 🎚 Expression (CC11)

（引用）「Expression は **チャンネルの音量設定値**であり、Domino は変更しない。」

| ch | CC11 |
|----|------|
| 多くの ch | 25 |
| ch=4 | 16 |
| ch=5 | 0 |
| ch=9 | 挿入なし |

---

# 4. 🎯 CC 挿入ルール（公式）

## Program Change がある場合

```
tick=N-1: CC0
tick=N-1: CC32
tick=N:   Program Change
tick=N:   CC11
tick=N:   Note On
```

## Program Change がない場合

```
tick=N-1: CC0
tick=N-1: CC32
tick=N:   CC11
tick=N:   Note On
```

## ch=9（リズム）

- CC0 なし  
- CC32 なし  
- CC11 なし  

---

# 5. 🎼 Format 1 のトラック割り当て

（引用）「Domino はチャンネルごとにトラックを分割する」

| track | channel |
|-------|---------|
| 2 | ch=0 |
| 3 | ch=1 |
| 4 | ch=2 |
| 5 | ch=3 |
| 6 | ch=4 |
| 7 | ch=5 |
| 11 | ch=9 |

---

# 6. 🧠 公式アルゴリズム（4bank + vnum）

```python
for each note_on event on channel C:

    if C == 9:
        emit note_on
        continue

    txv  = get_tx802_melody_voice(inst, mode)
    vnum = tx802_bank_voice_to_vnum(txv.bank, txv.voice)

    # 4-bank CC0/CC32
    if txv.bank == "I": msb, lsb = 0, 0
    elif txv.bank == "C": msb, lsb = 1, 0
    elif txv.bank == "A": msb, lsb = 0, 1
    elif txv.bank == "B": msb, lsb = 1, 1

    program = txv.voice - 1
    expr    = get_expression(C)

    emit CC0  at tick-1
    emit CC32 at tick-1
    emit ProgramChange at tick
    emit CC11 at tick
    emit NoteOn
```

---

# 7. 🎧 なぜこの仕様で TX802 が安定するのか？

- Bank が **I/A/C/B の 4bank で毎回確定**  
- Expression が毎回初期化  
- Program Change が正しい状態で適用  
- 前曲の状態を引きずらない  

---

# 8. 🎉 最終まとめ（vnum + 4bank 正式版）

- **TX802 の音色は vnum（0〜255）で一意に決まる**  
- **I/A/C/B は CC0/CC32 の 2bit で完全選択する（4bank）**  
- **Program Change はバンク内の 1〜64 を選ぶだけ**  
- **Expression はチャンネルごとに適切な値**  
- **Note On の直前に CC0/CC32/CC11 を必ず挿入**  
- **Format 1 でチャンネル状態を完全分離**  
- **Domino CCMR と完全互換**
