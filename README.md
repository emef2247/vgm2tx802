# msx_vgm2tx802

VGMの演奏を解析し、Yamaha TX802向けのMIDI（SMF Format 1）に変換します。
現行 `msx_vgm2mml` と同じmusical layerを使い、MMLや旧来の60Hzトレースを経由せずに出力します。
初期の本番MIDI出力は **OPLLのメロディ、ユーザー音色の割当、外部GM／RX21用リズム** に対応します。

## 一括変換

```bash
python scripts/export_tx802.py INPUT --outdir OUTPUT --force
```

INPUTはVGM/VGZファイル、またはフォルダです。フォルダ内は再帰的に変換し、入力以下のフォルダ構成を保持します。
`--outdir` を省略すると、それぞれの入力と同じ場所に出力します。

```text
OUTPUT/<入力以下のフォルダ>/
  tracks/<stem>.mid
  tables/<stem>_voice.csv
  tracks/<stem>.vgm
  tracks/<stem>.user_voice_tx802.json  # ユーザー音色がある場合
  blueprint/<stem>.mml
  blueprint/<stem>.midi
  _diagnostics/<stem>/
  _diagnostics/results.csv
  listening_manifest.json
```

`.mid` がTX802向けの演奏データです。`.vgm` は元音源の参照用で、TX802の再生音ではありません。
blueprintはアレンジ用の下書きです。本番MIDIを生成できない場合も、参照VGMとblueprintは独立して生成を試みます。

## 試聴前の準備

音色は旧 `vgm2tx802` の割当を引き継いでいます。必要なInternal音色と受信チャンネルは、実機側で用意してください。
このツールは実機への音色送信を行いません。ユーザー音色の割当JSONは編集・再利用できます。
従来形式の音色CSVを `tables/<stem>_voice.csv` に生成します。既存のTX802用CSV→SysExツールへ渡す中間データです。
[CSV生成と既存SysEx経路](docs/tx802_voice_csv.md) を参照してください。
旧Bank Select方式も継承していますが、実機でのバンク選択の確認はこれからです。

保持音の音程変化にはPitch Bendを使います。使用音色のRangeを出力設定（既定12半音）に、Stepを0に合わせてください。
リズムは外部GM／RX21向けのMIDI ch10です。TX802自体のFMドラムとして鳴らす処理ではありません。

1台あたり8パートです。2台へ割り当てる場合は `--tx802-units 2` を指定し、再生ソフト側でMIDIポート0／1を割り当ててください。
`--force` は所有する生成物の更新と、診断付きの部分変換を許可します。手で編集したファイルは保護します。

全オプションは `python scripts/export_tx802.py --help`、詳細は [docs/tx802_projection.md](docs/tx802_projection.md) を参照してください。

## 開発

Python 3とWSLが主な環境です。

```bash
python -m unittest discover -s tests/script -p 'test_tx802*.py' -v
```

公開素材と人工パターンで構造とイベントを検証します。local_onlyのリグレッション、DAW経由の試聴と実機確認は別途行います。

---

# msx_vgm2tx802 — English

Reconstruct VGM performances and export Yamaha TX802-oriented MIDI (SMF Format 1).
Source analysis and the musical layer follow the current msx_vgm2mml baseline.
The output does not go through generated MML or the old 60 Hz trace clock.
The initial production MIDI route supports **OPLL melody, custom voice assignments,
and external GM/RX21 rhythm**.

## Batch conversion

```bash
python scripts/export_tx802.py INPUT --outdir OUTPUT --force
```

INPUT accepts a VGM/VGZ file or a recursively searched directory. Relative input
folders are preserved under OUTPUT. Without `--outdir`, outputs are placed beside
each source.

```text
OUTPUT/<relative-input-folder>/
  tracks/<stem>.mid
  tables/<stem>_voice.csv
  tracks/<stem>.vgm
  tracks/<stem>.user_voice_tx802.json  # when custom patches occur
  blueprint/<stem>.mml
  blueprint/<stem>.midi
  _diagnostics/<stem>/
  _diagnostics/results.csv
  listening_manifest.json
```

The `.mid` is the TX802 performance. The `.vgm` is a source-native reference,
not a rendering of the TX802 MIDI. Editable Blueprint MML/MIDI and reference VGM
remain independent products when production MIDI cannot be generated.

## Preparing for audition

Voice assignments come from the original vgm2tx802 project. Prepare the matching
Internal voices and receive-channel configuration on the hardware. This converter
does not transmit voice banks. A legacy-schema voice CSV is written to
`tables/<stem>_voice.csv` for the existing TX802 CSV-to-SysEx tools; see
[the voice CSV route](docs/tx802_voice_csv.md). Custom patch assignment JSON remains editable and is
reused on subsequent conversions. Legacy Bank Select emission is retained, but
hardware bank selection still needs validation.

Held pitch changes use Pitch Bend. Match each hardware voice's Range to the output
setting (default: 12 semitones) and set Step to 0. Rhythm is sent to MIDI channel 10
for an external GM/RX21 instrument; it is not synthesized as TX802 FM drums.

One unit provides eight melodic parts. Use `--tx802-units 2` for two units and map
SMF MIDI ports 0 and 1 in the playback application. `--force` updates owned outputs
and permits explicitly reported partial projection; user-edited files are protected.

Run `python scripts/export_tx802.py --help` for options, and see
[docs/tx802_projection.md](docs/tx802_projection.md) for technical scope and diagnostics.

## Development

Python 3 and WSL are the primary environment.

```bash
python -m unittest discover -s tests/script -p 'test_tx802*.py' -v
```

Authored public fixtures and synthetic checks validate file structure and events.
Private regression, DAW playback and real-hardware audition are separate checks.
