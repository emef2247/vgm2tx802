# ControlChangeMacro 復元処理まとめ（TX802 向け）

## 🎯 目的  
ControlChangeMacro の復元は、Domino が内部で保持している **音源状態（CC 値）を MIDI イベントとして再構築する処理**。

これにより、  
**Program Change / Note On の直前に音源状態が正しく初期化され、TX802 の演奏が安定する。**

---

## ⚠️ 実測結果：2ファイルの差分について

`FMPAC01_tx802_default_rx21.mid` と `FMPAC01_tx802_default_rx21.domino.mid` の  
MIDI イベント内容（tick・チャンネル・CC 値・Note 値・velocity）を完全比較した結果：

**両ファイルのイベント内容は完全に一致している。**

すなわち、vgm2midi が出力する `.mid` の時点で  
**すでに CC0/CC32/Program Change/CC11 パターンが含まれている**。

Domino の「Restore Control Change Macro」が行う実質的な変更は  
**MIDI フォーマットの変換のみ**である：

| 変更項目 | 内容 |
|---|---|
| MIDI フォーマット | Format 0（シングルトラック）→ Format 1（マルチトラック） |
| トラック分割 | 全チャンネル 1 トラック → チャンネルごとに別トラック |
| delta-time | トラック内相対値に再計算（実効タイミングは不変） |
| イベント値・tick 位置 | **変更なし** |

---

## 🎯 vgm2midi が生成する CC パターン（実測値）

### 1. **CC0（Bank Select MSB）**

Note On / Program Change の **1 tick 前**に挿入される。  
値はチャンネルが属するバンクによって決まる（常に 0 ではない）。

| チャンネル | CC0 value | 備考 |
|---|---|---|
| ch=0〜3 | 0 | TX802 Bank A |
| ch=4〜5（一部） | **1** | TX802 Bank B |
| ch=9（リズム） | なし | CC0 挿入なし |

---

### 2. **CC32（Bank Select LSB）**

CC0 と同 tick に挿入される。値は常に **0**。

リズムチャンネル（ch=9）には挿入されない。

---

### 3. **CC11（Expression）**

Note On / Program Change と **同 tick**に挿入される（Note On の直前）。  
値はチャンネルの音量設定により異なる。**常に 25 ではない**。

| チャンネル / 状況 | CC11 value |
|---|---|
| 多くのチャンネル（通常） | 25 |
| ch=5（特定区間） | **0** |
| ch=4（特定区間） | **16** |
| ch=9（リズム） | なし（CC11 挿入なし） |

---

### 4. **Program Change との組み合わせパターン**

```
tick=N-1:  CC0  (Bank Select MSB) = バンクに応じた値（0 or 1）
tick=N-1:  CC32 (Bank Select LSB) = 0
tick=N:    Program Change
tick=N:    CC11 (Expression)     = チャンネルの音量設定値
tick=N:    Note On
```

Program Change が存在しない場合（Note On のみの場合）も、  
CC0/CC32 の 1-tick 前挿入と CC11/Note On の同-tick 挿入は同様に行われる。

---

## 🎯 チャンネル別の動作差異

| チャンネル種別 | CC0 挿入 | CC32 挿入 | CC11 挿入 |
|---|---|---|---|
| 通常チャンネル（ch=0〜5） | ✅ あり（値はバンク依存） | ✅ あり（常に 0） | ✅ あり（値は音量設定依存） |
| リズムチャンネル（ch=9） | ❌ なし | ❌ なし | ❌ なし |

リズムチャンネル（ch=9）は Note On / Note Off のみ。CC 系イベントは挿入されない。

---

## 🎯 復元処理の動作フロー（確定版アルゴリズム）

```
for each note_on event on channel C:
    if C == 9:  # リズムチャンネル
        emit note_on  # CC 挿入なし
        continue

    tick_n    = note_on.tick
    tick_prev = tick_n - 1
    bank_msb  = get_bank_msb(C)      # バンク A → 0、バンク B → 1
    bank_lsb  = 0                    # 常に 0
    expression = get_expression(C)   # チャンネルの音量設定値

    emit CC0  (channel=C, value=bank_msb,  tick=tick_prev)
    emit CC32 (channel=C, value=bank_lsb,  tick=tick_prev)
    if program_change exists at tick_n for channel C:
        emit program_change (channel=C, tick=tick_n)
    emit CC11 (channel=C, value=expression, tick=tick_n)
    emit note_on
```

---

## 🎯 復元処理が TX802 の演奏を安定させる理由

TX802 は **前の状態を保持する音源**であるため、CC 値が不定のまま Program Change を受けると  
音色・音量が意図と異なる状態になる可能性がある。

毎回の Note On 前に CC0/CC32/CC11 を明示的に送ることで：

- Bank Select が確定し、Program Change が正しい音色を選択する  
- Expression（音量）が毎回初期化され、前の演奏状態を引きずらない  
- Domino 以外のプレーヤーでも同じ状態で再生される  

---

## 🎯 Domino 以外のプレーヤーでも安定する理由

出力する CC はすべて **標準 MIDI CC** であり、Domino 独自の情報は一切含まれない。

- CC0（Bank Select MSB）  
- CC32（Bank Select LSB）  
- CC11（Expression）  
- Program Change  

これらだけで音源状態が完全に決まるため、**どのプレーヤーでも TX802 が同じ状態で鳴る。**

---

## 🎯 最終まとめ（仕様書として）

- vgm2midi の出力には **すでに CC0/CC32/CC11 の挿入が含まれている**
- Domino の「Restore Control Change Macro」は MIDI フォーマットを変換するが **イベント値は変更しない**
- CC0 の値は **バンク依存（0 または 1）**であり、常に 0 ではない
- CC11 の値は **チャンネルの音量設定依存**であり、常に 25 ではない
- **リズムチャンネル（ch=9）には CC0/CC32/CC11 は挿入されない**
- CC0/CC32 は Note On / Program Change の **1 tick 前**に配置される
- CC11 と Note On は **同 tick** で、CC11 が先行する

---

## 🎯 CC32 について補足

CC32（Bank Select LSB）は元の MID にすでに入っており、Domino はこれを変更しない。  
`_tx802.xml` の CCM 定義には CC32 が存在しないため、復元の対象外。

```xml
<CCM ID="1" ...>   ← Modulation
<CCM ID="7" ...>   ← Volume
<CCM ID="64" ...>  ← Sustain
<CCM ID="65" ...>  ← Portamento
（CC32 は定義なし）
```

したがって CC32 は vgm2midi が直接生成する値（常に 0）がそのまま使用される。
