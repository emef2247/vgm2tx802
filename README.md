# vgm2midi

YM2413 / OPLL を使用した VGM ファイルを  
Standard MIDI File（SMF Format 0）へ変換するツールです。

FM メロディ（ch0–8）と OPLL リズム（BD/SD/TOM/TC/HH/CYM）を解析し、  
**General MIDI（GM）** または **Yamaha TX802** 向けの MIDI データを生成します。

---

## 特徴

- YM2413（OPLL）の FM チャンネルを MIDI ノートへ変換  
- OPLL リズムを GM または RX21 ドラムノートへ変換  
- BPM を VGM から自動検出  
- ポルタメント（is_portamento=1）を MIDI CC84/65/5 で再現  
- inst=0（ユーザー音色）は JSON に保存し、再変換時に反映  
- GM / TX802 のどちらにも対応  
- melody_mode による **2 種類の音色マッピングルール**  
  - default：OPLLの音色の特徴を考慮した変換テーブル
  - name：音名ベースのマッピング  

---

## インストール

Python 3.10 以上を推奨。

```bash
git clone https://github.com/xxxx/vgm2midi
cd vgm2midi
pip install -r requirements.txt
```

---

## 使い方

```bash
python vgm2midi.py [オプション] <入力VGMファイル>
```

### 出力ファイル

| ファイル | 説明 |
|---------|------|
| `<stem>.mid` | 生成された MIDI ファイル（SMF Format 0） |
| `<stem>.user_voice.json` | inst=0 のユーザー音色マッピング（必要時のみ生成） |
| `csv/<stem>_voice.csv` | TX802 用ユーザー音色バンク。`OPLL_OP2_MB14.csv` の 20 音色 + I21 以降のユーザー音色（voice 列は 0 ベース vnum） |

---

## 主なオプション

| オプション | 説明 |
|-----------|------|
| `--target {gm,tx802}` | 出力先音源（デフォルト: gm） |
| `--melody_mode {default,name}` | メロディ音色のマッピング方式 |
| `--rhythm_mode {gm,rx21}` | リズムマッピング方式 |
| `--[no-]tx802-domino-init` | TX802向けDomino互換初期化ブロック（既定: 有効） |
| `--outdir DIR` | 出力ディレクトリ |
| `--ppq N` | MIDI PPQ（デフォルト: 480） |
| `--debug` | 中間 CSV を保持し詳細ログを表示 |

---

## --target {gm,tx802}

出力先音源を選択します。

- **gm**  
  標準 GM 音源向けの MIDI を生成（デフォルト）

- **tx802**  
  Yamaha TX802 向けに Bank Select + Program Change を出力  
  TX802 のプリセット A/B を使用した音色マッピングを行う

  **現在の対応範囲: TX802 はメロディパスのみ最適化対象です。**  
  リズムチャンネル（OPLL リズム音源 bd/sd/tom/tc/hh）は最適化・変換なしの
  パススルーとして扱い、標準 GM ドラムチャンネル（MIDI ch 9）にそのまま出力します。

  さらに既定で、Domino の「コントロールチェンジマクロ復元」で再構築される前提状態を
  **メロディ CH のみ**曲頭に明示的な初期化イベントとして挿入し、他プレーヤーとの差分を吸収します。
  リズムチャンネルへの初期化ブロック挿入は行いません。

---

## --melody_mode {default,name}

OPLL の FM メロディ音色を GM/TX802 に割り当てる方式を選択します。

### **default**
TX802:
OPLL の音色の各パラメータとTX802のプリセット A/Bの各パラメータ間の最短距離を計算し、最も距離が近いものTOP3から選定した変換テーブルを使用
ユーザパッチも同様にTX802のプリセット A/Bから最も距離が近いものを選択

GM:
--target=tx802, --melody_mode=defaultで選出された音色をリファレンスとして、GMの音色を選出

### **name**
プリセットの音色の名前ベースでの対応付け

---

## --rhythm_mode {gm,rx21}

OPLL リズムのマッピング方式を選択します。

- **gm**  
  GM ドラムノートにマッピング  
  TOM / HH / TC は OPLL の scale に応じて可変

- **rx21**  
  Yamaha RX21 のドラムパッドにマッピング  
  scale に応じて音程が変化

---

## 出力ファイル名の命名規則
```
<stem>_<postfix>.mid
```
- <stem> … 入力ファイル名のベース部分

- <postfix> … target / melody_mode / rhythm_mode の組み合わせで決定

## postfix 対応表
| target | melody_mode | rhythm_mode | postfix |
| --- | --- | --- | --- |
| tx802 | default | gm | ``_default_gm`` |
| tx802 | default | rx21 | ``_default_rx21`` |
| tx802 | name | gm | ``_name_gm`` |
| tx802 | name | rx21 | ``_name_rx21`` |
| gm | default | gm | ``_default_gm`` |
| gm | default | rx21 | ``_default_r21`` |
| gm | name | gm | ``_name_gm`` |
| gm | name | rx21 | ``_name_rx21`` |
---

## 使用例

### 1. GM 用に変換（デフォルト）

```bash
python vgm2midi.py mysong.vgm
```

### 2. TX802 用に変換 (--melody_mode=default : OPLL の音色性格を再現したマッピングで変換)

```bash
python vgm2midi.py --target=tx802 mysong.vgm
```

### 3.  音名に忠実なマッピングで変換

```bash
python vgm2midi.py --melody_mode=name mysong.vgm
```

### 4. RX21 リズムマッピングを使用

```bash
python vgm2midi.py --rhythm_mode=rx21 mysong.vgm
```

### 5. 出力先ディレクトリを指定

```bash
python vgm2midi.py --outdir=./out mysong.vgm
```

---

## ユーザー音色（inst=0）について

変換時に inst=0 の音色が検出されると、  
`<stem>.user_voice.json` が生成されます。

- GM モードでは GM Program 番号を指定  
- TX802 モードでは Bank(A or B) / Voice 番号を指定  

JSON を編集して再度変換すると、指定した音色が反映されます。  
既存の JSON は上書きされません。

`--target=tx802` では、同時に `csv/<stem>_voice.csv` も生成または更新されます。

- 先頭 20 行は `csv/OPLL_OP2_MB14.csv` をそのまま使用（I1-I20 相当）
- 末尾に検出したユーザー音色を追加（I21 以降のみ）
- TX802 ラベル番号は 1 ベース（I1, I2, ...）だが、CSV の `voice` 列は 0 ベース vnum（0, 1, ...）を使用
- たとえば I1→`voice=0`、I20→`voice=19`、I21→`voice=20`
- Inst=0 でも I1（vnum=0）など非ユーザースロットに割り当てられた音色は CSV 追記対象から除外
- `<stem>.user_voice_tx802.json` が存在する場合は、その割り当て値を再利用

### 実行例

```bash
# 初回: JSON が無ければ自動生成し、voice CSV も生成
python vgm2midi.py --target=tx802 mysong.vgm

# 2回目以降: 既存 JSON の割り当てを使い、voice CSV を更新
python vgm2midi.py --target=tx802 mysong.vgm
```

### voice CSV の用途

`csv/<stem>_voice.csv` は将来の TX802 32 ボイスバンク syx 変換の入力を想定しています。

```bash
python3 py/convert_op2csv_to_op6csv_tx802.py csv/<stem>_voice.csv
python3 py/convert_tx802csv_to_wmem_bank_syx.py csv/<stem>_voice_tx802.csv
```

### 最低限の検証手順

- JSON が無い状態で `--target=tx802` を実行し、`<stem>.user_voice_tx802.json` と `csv/<stem>_voice.csv` が生成されることを確認
- JSON を残したまま再実行し、`csv/<stem>_voice.csv` が更新されることを確認
- `csv/<stem>_voice.csv` の先頭 20 行が `csv/OPLL_OP2_MB14.csv` と一致し、21 行目以降にユーザー音色が追加されることを確認
- 追記行では TX802 ラベル I21 が CSV 上で `voice=20` になることを確認

---

## ライセンス

MIT License

---
# vgm2midi

`vgm2midi` converts VGM files using YM2413 / OPLL into  
Standard MIDI File (SMF Format 0).

It analyzes FM melody channels (ch0–8) and OPLL rhythm (BD / SD / TOM / TC / HH / CYM),  
and generates MIDI data for **General MIDI (GM)** or **Yamaha TX802**.

---

## Features

- Converts YM2413 (OPLL) FM channels into MIDI notes  
- Converts OPLL rhythm into GM or RX21 drum notes  
- Automatically detects BPM from the VGM stream  
- Portamento (`is_portamento=1`) reproduced using CC84 / CC65 / CC5  
- `inst=0` (user patches) are saved into JSON and reused on subsequent conversions  
- Supports both GM and TX802 output  
- Two melody‑mapping modes:  
  - **default** — mapping based on OPLL timbral characteristics  
  - **name** — mapping based on instrument names  

---

## Installation

Python 3.10+ recommended.

```bash
git clone https://github.com/xxxx/vgm2midi
cd vgm2midi
pip install -r requirements.txt
```

---

## Usage

```bash
python vgm2midi.py [options] <input.vgm>
```

### Output Files

| File | Description |
|------|-------------|
| `<stem>.mid` | Generated MIDI file (SMF Format 0) |
| `<stem>.user_voice.json` | User‑patch mapping (created only when inst=0 is used) |
| `csv/<stem>_voice.csv` | TX802 user voice bank: 20 rows from `OPLL_OP2_MB14.csv` plus appended user voices from I21 onward (`voice` column uses zero-based vnum values) |

---

## Main Options

| Option | Description |
|--------|-------------|
| `--target {gm,tx802}` | Output sound module (default: gm) |
| `--melody_mode {default,name}` | Melody‑voice mapping method |
| `--rhythm_mode {gm,rx21}` | Rhythm mapping method |
| `--[no-]tx802-domino-init` | Domino-compatible TX802 init block for melody channels (default: enabled) |
| `--outdir DIR` | Output directory |
| `--ppq N` | MIDI PPQ (default: 480) |
| `--debug` | Keep intermediate CSV and show detailed logs |

---

## --target {gm,tx802}

Select the output sound module.

### **gm**
Generates standard GM‑compatible MIDI output (default).

### **tx802**
Outputs Bank Select + Program Change for Yamaha TX802.  
Uses TX802 preset banks A/B and applies OPLL→TX802 timbre mapping.

**Current scope: TX802 optimization applies to the melody path only.**  
Rhythm channels (OPLL rhythm: bd/sd/tom/tc/hh) are written as-is (passthrough)
to the standard GM drum channel (MIDI ch 9) without any TX802-specific
transformation.

By default the converter also inserts a Domino-compatible controller init block
**for melody channels only** at song start.  This explicitly replicates the
controller state that Domino's "CC macro restore" builds implicitly, improving
playback stability on non-Domino players.  
Rhythm channels are never touched by this init block.

---

## --melody_mode {default,name}

Select how OPLL FM melody voices are mapped to GM or TX802 instruments.

### **default**

#### TX802
Uses a parameter‑distance–based mapping:

- Computes the shortest parameter distance between each OPLL preset and all TX802 A/B presets  
- Builds a conversion table from the closest **TOP 3** candidates  
- User patches (inst=0) are also matched to the nearest TX802 preset

#### GM
GM program numbers are selected **based on the TX802 result**:

- The GM instrument is chosen by referencing the TX802 voice selected under  
  `--target=tx802 --melody_mode=default`  
- GM mapping follows the timbral category implied by the TX802 default mapping

### **name**
Name‑based mapping:

- Each OPLL instrument number is mapped directly to the corresponding GM program  
- Follows GM naming conventions; does not use TX802 timbral characteristics

---

## --rhythm_mode {gm,rx21}

Select rhythm mapping.

### **gm**
Maps OPLL rhythm to GM drum notes.  
TOM / HH / TC vary depending on OPLL `scale`.

### **rx21**
Maps OPLL rhythm to Yamaha RX21 drum layout.  
Pitch varies depending on `scale`.

---

## Output Filename Format

```
<stem>_<postfix>.mid
```

- `<stem>` — base name of the input file  
- `<postfix>` — determined by `target`, `melody_mode`, and `rhythm_mode`

### Postfix Table

| target | melody_mode | rhythm_mode | postfix |
|--------|-------------|-------------|---------|
| tx802 | default | gm | `_default_gm` |
| tx802 | default | rx21 | `_default_rx21` |
| tx802 | name | gm | `_name_gm` |
| tx802 | name | rx21 | `_name_rx21` |
| gm | default | gm | `_default_gm` |
| gm | default | rx21 | `_default_rx21` |
| gm | name | gm | `_name_gm` |
| gm | name | rx21 | `_name_rx21` |

---

## Examples

### 1. Convert to GM (default)

```bash
python vgm2midi.py mysong.vgm
```

### 2. Convert for TX802 (default OPLL‑timbre mapping)

```bash
python vgm2midi.py --target=tx802 mysong.vgm
```

### 3. Convert using name‑based mapping

```bash
python vgm2midi.py --melody_mode=name mysong.vgm
```

### 4. Use RX21 rhythm mapping

```bash
python vgm2midi.py --rhythm_mode=rx21 mysong.vgm
```

### 5. Specify output directory

```bash
python vgm2midi.py --outdir=./out mysong.vgm
```

---

## User Patches (inst=0)

When inst=0 is detected,  
`<stem>.user_voice.json` is created.

- In **GM mode**: specify GM Program numbers  
- In **TX802 mode**: specify Bank (A/B) and Voice numbers  

Editing the JSON and re‑running the conversion applies your custom mapping.  
Existing JSON files are never overwritten.

With `--target=tx802`, the converter also generates or updates `csv/<stem>_voice.csv`.

- The first 20 rows come directly from `csv/OPLL_OP2_MB14.csv` (I1-I20)
- Detected user patches are appended after that (I21 onward only)
- TX802 labels are 1-based (I1, I2, ...), while the CSV `voice` column uses zero-based vnum values (0, 1, ...)
- For example: I1→`voice=0`, I20→`voice=19`, I21→`voice=20`
- Inst=0 patches mapped to non-user slots such as I1 (vnum=0) are skipped for CSV append
- If `<stem>.user_voice_tx802.json` already exists, its assignments are reused

### Example runs

```bash
# First run: create JSON and voice CSV
python vgm2midi.py --target=tx802 mysong.vgm

# Later runs: reuse existing JSON assignments and refresh the voice CSV
python vgm2midi.py --target=tx802 mysong.vgm
```

### How the voice CSV connects to syx generation

```bash
python3 py/convert_op2csv_to_op6csv_tx802.py csv/<stem>_voice.csv
python3 py/convert_tx802csv_to_wmem_bank_syx.py csv/<stem>_voice_tx802.csv
```

### Minimal verification

- Run `--target=tx802` with no existing JSON and confirm both `<stem>.user_voice_tx802.json` and `csv/<stem>_voice.csv` are created
- Run it again with the JSON left in place and confirm `csv/<stem>_voice.csv` is updated
- Confirm the first 20 rows of `csv/<stem>_voice.csv` match `csv/OPLL_OP2_MB14.csv`, with user voices appended from row 21 onward
- Confirm that TX802 label I21 appears as `voice=20` in the appended CSV rows

---

## License

MIT License
