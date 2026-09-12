# vgm2tx802

**日本語**: `vgm2tx802` は、YM2413/OPLL を含む VGM を TX802 指向の MIDI（SMF Format 0）へ変換するツールです。  
**English**: `vgm2tx802` converts YM2413/OPLL VGM data into TX802-oriented MIDI (SMF Format 0).

## Overview / 概要

- **日本語**: VGM の YM2413/OPLL イベントを解析し、メロディ（FM）とリズム（OPLL Rhythm）を MIDI 化します。出力先は General MIDI と Yamaha TX802 に対応しています。  
- **English**: The converter parses YM2413/OPLL events in VGM and emits MIDI for melody (FM) and rhythm (OPLL rhythm), targeting both General MIDI and Yamaha TX802 workflows.

## Key features / 主な機能

- **日本語**
  - YM2413/OPLL のメロディ／リズムを MIDI に変換
  - `--target {gm,tx802}` による出力ターゲット切替
  - `--melody_mode {default,name}` / `--rhythm_mode {gm,rx21}` を選択可能
  - TX802 向け Domino 互換初期化（メロディ ch 対象、既定 ON）
  - user patch（inst=0）検出時に user voice JSON を生成・再利用
- **English**
  - Converts YM2413/OPLL melody and rhythm streams into MIDI
  - Selects output target with `--target {gm,tx802}`
  - Supports `--melody_mode {default,name}` and `--rhythm_mode {gm,rx21}`
  - TX802 Domino-compatible init for melody channels (enabled by default)
  - Generates/reuses user-voice JSON when user patches (inst=0) are detected

## Repository guide / リポジトリ案内

- `src/vgm2midi.py`: main converter entry point / メイン変換スクリプト
- `docs/project_knowledge.md`: conversion behavior and design context / 変換挙動と設計背景
- `handoffs/current.md`: current work state and restart context / 現在の作業状態・再開ポイント
- `mistaken.md`: repeated failure patterns to avoid / 再発防止メモ
- `field_notes/`: one-off discoveries / 単発の調査メモ
- `tests/fixtures/README.md`: public fixture layout and profiles / 公開 fixture 構成とプロファイル

## Prerequisites / 前提

- Python 3.10+
- Run from repository root. / リポジトリルートで実行

## Install / インストール

```bash
git clone https://github.com/emef2247/vgm2tx802.git
cd vgm2tx802
```

## Basic usage / 基本的な使い方

```bash
python3 src/vgm2midi.py [options] <input.vgm>
```

Examples / 実行例:

```bash
# GM (default)
python3 src/vgm2midi.py song.vgm

# TX802 target
python3 src/vgm2midi.py --target=tx802 song.vgm

# Name-based melody mapping
python3 src/vgm2midi.py --melody_mode=name song.vgm

# RX21 rhythm mapping
python3 src/vgm2midi.py --rhythm_mode=rx21 song.vgm
```

## Main options / 主なオプション

| Option | 日本語 | English |
|---|---|---|
| `--target {gm,tx802}` | 出力ターゲット | Output target |
| `--melody_mode {default,name}` | メロディ音色マッピング方式 | Melody voice mapping mode |
| `--rhythm_mode {gm,rx21}` | リズムマッピング方式 | Rhythm mapping mode |
| `--tx802-domino-init / --no-tx802-domino-init` | TX802 向け Domino 互換初期化の ON/OFF | Enable/disable TX802 Domino-compatible init |
| `--outdir DIR` | 出力先ディレクトリ | Output directory |
| `--ppq N` | MIDI PPQ | MIDI PPQ |
| `--debug` | 詳細ログと中間 CSV 保持 | Verbose logging + keep intermediate CSV |

## Output files / 出力ファイル

| File | 日本語 | English |
|---|---|---|
| `<stem>_<postfix>.mid` | 変換された MIDI（`target`/`melody_mode`/`rhythm_mode` に応じた接尾辞付き） | Converted MIDI with postfix based on `target`/`melody_mode`/`rhythm_mode` |
| `<stem>.user_voice.json` | inst=0 検出時（`--target=gm`）の user voice 定義 | User-voice definition for inst=0 (`--target=gm`) |
| `<stem>.user_voice_tx802.json` | inst=0 検出時（`--target=tx802`）の TX802 割り当て定義 | TX802 assignment definition for inst=0 (`--target=tx802`) |
| `csv/<stem>_voice.csv` | TX802 用 user voice CSV（該当時のみ） | TX802 user-voice CSV (when applicable) |

- **日本語**: user patch（inst=0）検出時は、`--target` に応じた user voice ファイルが生成・再利用されます。  
- **English**: When user patches (inst=0) are detected, user-voice files are generated/reused according to the selected `--target`.

Postfix mapping (current implementation) / postfix 対応表（現行実装）:

| target | melody_mode | rhythm_mode | postfix |
|---|---|---|---|
| tx802 | default | gm | `_tx802_default_gm` |
| tx802 | default | rx21 | `_tx802_default_rx21` |
| tx802 | name | gm | `_gm_name_gm` |
| tx802 | name | rx21 | `_gm_name_rx21` |
| gm | default | gm | `_gm_default_gm` |
| gm | default | rx21 | `_gm_default_rx21` |
| gm | name | gm | `_gm_name_gm` |
| gm | name | rx21 | `_gm_name_rx21` |

- **日本語**: `--target=tx802 --melody_mode=name` の postfix は現状 `_gm_name_*` です（互換維持のための既存命名）。  
- **English**: For `--target=tx802 --melody_mode=name`, the current postfix remains `_gm_name_*` (legacy naming kept for compatibility).

## TX802 mode notes / TX802 モード注意事項

- **日本語**: 現在、TX802 向け最適化はメロディパスが中心です。リズムは `rhythm_mode` の設定に従ってマッピングされます。  
- **English**: TX802-specific optimization is currently focused on the melody path. Rhythm follows the selected `rhythm_mode` mapping.
- **日本語**: Domino 互換初期化ブロックはメロディチャンネル向けです（既定 ON）。  
- **English**: The Domino-compatible init block targets melody channels (enabled by default).

## Fixtures and testing / fixture とテスト

- **日本語**: 公開 fixture の配置規則と期待ファイルは `tests/fixtures/README.md` を参照してください。  
- **English**: See `tests/fixtures/README.md` for public fixture layout and expected-file conventions.
- **日本語**: 現行 OPLL プロファイル名は `tx802_default_rx21` です。  
- **English**: The current OPLL fixture profile is `tx802_default_rx21`.
- **日本語**: private fixture は Git 管理外です（詳細は fixture README のポリシーを参照）。  
- **English**: Private fixtures remain outside git (see fixture README policy details).

## License / ライセンス

MIT License
