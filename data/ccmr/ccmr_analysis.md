# CCMR（Control Change Macro Restore）調査レポート

## 対象と前提

- 比較対象は `*_tx802_default_rx21.mid` と `*_tx802_default_rx21.domino.mid` のペア。
- リポジトリ調査結果:
  - `/home/runner/work/vgm2tx802/vgm2tx802/ccmr` 配下: **0 ペア**（ドキュメントのみ）
  - `/home/runner/work/vgm2tx802/vgm2tx802/domino_RestoreControlChangeMacros` 配下: **2 ペア**
    - `FMPAC01_tx802_default_rx21.mid` ↔ `FMPAC01_tx802_default_rx21.domino.mid`
    - `MSLND01_tx802_default_rx21.mid` ↔ `MSLND01_tx802_default_rx21.domino.mid`

## 再現手順

```bash
python tools/compare_ccmr_midis.py \
  . \
  --rhythm-channels 9 \
  --json-out /tmp/ccmr_repo_result.json
```

## 機械比較の要点

### 1) ヘッダ・トラック構造

| pair | before (`.mid`) | after (`.domino.mid`) |
|---|---|---|
| FMPAC01 | format=0, ntrks=1, division=480 | format=1, ntrks=18, division=480 |
| MSLND01 | format=0, ntrks=1, division=480 | format=1, ntrks=18, division=480 |

- `division` は不変、`format/ntrks` は変化。
- Running Status は両者とも未使用（2ペアとも `false`）。

### 2) イベント系列（構造 vs 機能）

- **トラック差分込み**では差分あり（Format0→1 変換とメタイベント再配置のため）。
- **チャンネルイベント正規化比較（track/delta 無視）**では 2/2 ペアで完全一致。
  - `added_events=0`
  - `removed_events=0`

=> Domino CCMR後の `.domino.mid` は、チャンネルイベント（Note/CC/PC/PB/AT）の実体は維持し、主にSMF構造を再編している。

### 3) メタイベント

- `.domino.mid` 側でメタイベント数が増加（track分割に伴う Track Name / EOT の再配置・増加）。
  - FMPAC01: meta 3 → 55
  - MSLND01: meta 3 → 55

### 4) CC差分（定量）

- 対象CC（CC0/7/10/11/32/64/121/123）で **追加・削除なし**（2ペアとも）。
- Bank Select/Expression の実測例:
  - FMPAC01: `CC0=0/1`, `CC32=0`, `CC11=0/16/25`
  - MSLND01: `CC0=0`, `CC32=0`, `CC11=25/33/42/59/67`

### 5) Melody vs Rhythm（`--rhythm-channels 9` 前提）

- rhythm(ch9) で CC の追加/削除は 0。
- note長・発音タイミング・同時発音数・ch別イベント密度は before/after 一致。
  - 例: FMPAC01 の ch9 最大同時発音数は両者とも 2。

## Domino側変換の分類

- **追加**: 主にメタイベント（Track Name/EOT など）
- **削除**: メタイベントの配置差由来（実質は再編）
- **移動**: チャンネルイベントが単一trackからch別trackへ移動
- **値変更**: チャンネルイベント値（CC/PC/Note/PB/AT）の変更は観測されず

## 現行実装との対応（`vgm2midi.py` / `py/tx802.py`）

### カバー済み

- TX802出力を SMF Format 1 で構築（Domino後の構造に寄せる方針）
  - `py/tx802.py:1220`
- melody/rhythm のトラック分離、rhythm(ch9)のCC非挿入（passthrough）
  - `py/tx802.py:1234-1267`
- melodyで CC0 / PC / CC11 をノート近傍に配置する処理
  - `py/tx802.py:1317-1336, 1376-1382`

### 未カバー（差分再現の観点）

- `py/tx802.py` はコメントで「CC32は常に0」としているが、実装上はCC32送出がない。
  - コメント: `py/tx802.py:1315`
  - 実測ペアでは melody 側に `CC32=0` が存在。

## 未再現差分を実装すべきか

- **結論**:
  - TX802動作上の実害は限定的（CC0+PCだけでも多くの環境で実用可能）。
  - ただし「`*_tx802_default_rx21.mid` と Domino後ファイルの一致」を要件にするなら、**CC32=0 の明示送出は実装価値が高い**。

## 最終結論（MIDI構造・機能面）

1. Domino CCMRで主要に起きているのは **SMF構造変換（Format0→1、track再編、delta再計算）**。
2. チャンネルイベントの機能的内容（ノート/CC/PC等）は比較ペア上で同一。
3. rhythm passthrough 方針（ch9にCCを入れない）は観測結果と矛盾しない。
4. 今後「イベント一致」を厳密化する場合の主対象は `CC32=0` の扱い。
