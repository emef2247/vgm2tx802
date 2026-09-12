# TX802 ControlChangeMacroRestore (CCMR) — Official Specification (4-bank vnum-based)  
**Version:** 2.0  
**Target:** Yamaha TX802  
**Source:** vgm2midi output + Domino CCM Restore behavior + vnum-based TX802 model  
**Author:** Kentaro & Copilot

---

## 🎯 Purpose  
TX802 は **前の演奏状態を保持する FM 音源**であるため、  
Program Change や Note On の直前に **音源状態（Bank / Expression）を明示的に送る必要がある**。  

CCMR（ControlChangeMacroRestore）は、  
vgm2midi が生成した CC イベントを **正しい順序で再配置し、  
TX802 が毎回同じ状態で音色を鳴らすようにするための仕様**である。  

---

# 1. Event-Level Behavior

## ✔ CCMR は「MIDI イベント内容を変更しない」  

- CC0  
- CC32  
- Program Change  
- CC11  
- Note On  

**すべての値・tick 位置は vgm2midi が生成したまま**。  
Domino はこれらを変更せず、「並べ替え」と「トラック分割」だけを行う。  

## ✔ CCMR が行う処理  

- MIDI Format 0 → Format 1 の変換  
- トラック分割（チャンネルごとに track を分離）  

---

# 2. CC Event Specification (TX802, 4-bank vnum-based)

## 2.1 TX802 の内部ボイス番号 vnum

```python
@dataclass(frozen=True)
class Tx802Voice:
    bank: str   # "I", "C", "A", "B"
    voice: int  # TX802 表示番号 (1..64)

    def to_vnum(self) -> int:
        v = self.voice - 1
        b = self.bank.upper()
        if b == "I":
            return 0 + v      # Internal 1–64 → vnum 0–63
        if b == "C":
            return 64 + v     # Cartridge 1–64 → vnum 64–127
        if b == "A":
            return 128 + v    # Preset A 1–64 → vnum 128–191
        if b == "B":
            return 192 + v    # Preset B 1–64 → vnum 192–255
        return v
```

`vnum` が TX802 の音色を一意に決定するキー。

---

## 2.2 Bank Select (CC0 / CC32) — 4-bank 正式仕様

TX802 のバンク選択は **CC0（MSB）と CC32（LSB）の 2bit で 4バンクを選択する**。

`Tx802Voice(bank, voice)` から vnum を計算し、  
その `bank` に応じて CC0/CC32 を次のように決定する：

```python
vnum = tx802_bank_voice_to_vnum(bank, voice)

if bank == "I":
    msb, lsb = 0, 0   # Internal  vnum 0–63
elif bank == "C":
    msb, lsb = 1, 0   # Cartridge vnum 64–127
elif bank == "A":
    msb, lsb = 0, 1   # Preset A vnum 128–191
elif bank == "B":
    msb, lsb = 1, 1   # Preset B vnum 192–255
else:
    msb, lsb = 0, 0   # fallback: Internal
```

- `bank="I"` → `(CC0,CC32) = (0,0)`  
- `bank="C"` → `(CC0,CC32) = (1,0)`  
- `bank="A"` → `(CC0,CC32) = (0,1)`  
- `bank="B"` → `(CC0,CC32) = (1,1)`  

**A/B/C/I は CC0/CC32 だけで一意に決まる。  
vnum はその内部アドレス（0–255）として扱う。**

---

## 2.3 Expression (CC11)

実測値：

| チャンネル | CC11 |
|------------|------|
| 多くの ch  | 25   |
| ch=4       | 16   |
| ch=5       | 0    |
| ch=9       | 挿入なし |

Expression は **チャンネルの音量設定値**であり、  
Domino は値を変更しない。  

---

# 3. Event Ordering Rules

## ✔ Program Change がある場合

```text
tick=N-1:  CC0   (Bank MSB)
tick=N-1:  CC32  (Bank LSB)
tick=N:    Program Change
tick=N:    CC11  (Expression)
tick=N:    Note On
```

## ✔ Program Change がない場合（Note On のみ）

```text
tick=N-1:  CC0
tick=N-1:  CC32
tick=N:    CC11
tick=N:    Note On
```

## ✔ リズムチャンネル（ch=9）

- CC0 挿入なし  
- CC32 挿入なし  
- CC11 挿入なし  
- Note On / Note Off のみ  

---

# 4. Track Assignment (Format 1)

| track | channel |
|-------|---------|
| 2     | ch=0    |
| 3     | ch=1    |
| 4     | ch=2    |
| 5     | ch=3    |
| 6     | ch=4    |
| 7     | ch=5    |
| 11    | ch=9    |

---

# 5. Algorithm (Implementation Spec, 4-bank vnum)

```python
for each note_on event on channel C:
    if C == 9:  # Rhythm channel
        emit note_on
        continue

    tick_n    = note_on.tick
    tick_prev = tick_n - 1

    txv       = get_tx802_melody_voice(inst, melody_mode)
    vnum      = tx802_bank_voice_to_vnum(txv.bank, txv.voice)

    if txv.bank == "I":
        bank_msb, bank_lsb = 0, 0
    elif txv.bank == "C":
        bank_msb, bank_lsb = 1, 0
    elif txv.bank == "A":
        bank_msb, bank_lsb = 0, 1
    elif txv.bank == "B":
        bank_msb, bank_lsb = 1, 1
    else:
        bank_msb, bank_lsb = 0, 0

    expression = get_expression(C)
    program    = txv.voice - 1  # 0..63

    emit CC0  (channel=C, value=bank_msb, tick=tick_prev)
    emit CC32 (channel=C, value=bank_lsb, tick=tick_prev)

    if program_change exists at tick_n:
        emit program_change (channel=C, value=program, tick=tick_n)

    emit CC11 (channel=C, value=expression, tick=tick_n)
    emit note_on
```

---

# 6. Why CCMR Stabilizes TX802 Playback

- Bank が毎回明示的に確定（I/A/C/B を CC0/CC32 で指定）  
- Expression が毎回初期化  
- Program Change が正しい状態で適用  
- 前曲の状態を引きずらない  

---

# 7. Summary (Official, 4-bank)

- CCMR は **イベント内容を変更しない**  
- CC0/CC32/CC11 を **正しい順序で再配置するだけ**  
- CC0/CC32 で **I/A/C/B を 4通り一意に指定する**  
- CC11 はチャンネルごとの音量設定値  
- リズムチャンネルは CC を挿入しない  
- Program Change / Note On の直前に **CC0/CC32/CC11 を揃える**ことで TX802 の演奏が安定する  

