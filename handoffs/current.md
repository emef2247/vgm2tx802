# TX802 migration checkpoint — 2026-11-15

## Owner request

Create G:/repository/emef2247/msx_vgm2tx802 from current msx_vgm2mml, porting
I:/wsl/repositories/emef2247/vgm2tx802 as another independent musical-layer target.
Follow the same AGENTS/external field-note workflow and bilingual README style as MS2.

## Implementation

- Base MSX commit 95e6dbc; old TX802 commit 8816ed8; source edited files preserved.
- Local branch codex/tx802-musical-layer; no GitHub remote or push created.
- py/tx802_target.py directly consumes NativePerformance, preserving source samples.
- py/tx802_voices.py carries target tables/assignments; tx802_midi.py is pure SMF.
- scripts/export_tx802.py, vgm2tx802.py and src/vgm2midi.py provide batch/compat CLI.
- Production MIDI, source-native reference VGM, Blueprint MML/MIDI are independent.
- Initial production target scope is OPLL; force omissions remain explicit.
- Voice assignments require prepared hardware voices, not automatic six-op uploads.

## Validation and next action

30 TX802 target/SMF/batch checks and 18 inherited native-source checks pass.
All 19 public OPLL fixtures export MIDI, source-reference VGM and Blueprint.
295 notes / 1686 planned events; decoded channel events match each event CSV.
NativePerformance implementation and original source worktree hashes are unchanged.
Evidence: outputs/public_tx802_20261115/verification.json (generated, not committed).
A final architectural review was requested before this checkpoint.
Repeat-drum gates are shortened before the next same-key hit to retain attack timing.
No local_only regression or hardware audition has been performed.

The owner can run export_tx802 INPUT --outdir OUTPUT --force, optionally adding
--tx802-units 2 and matching pitch-bend Range/Step on actual voices. Verify MIDI
port routing, bank selection and the volume/timbre response by audition.

## Must not do

Do not modify old repositories, source timing or native units for MIDI convenience.
Do not upload malformed/unverified voice SysEx, assume RPN0 works on TX802, pretend
bank/program selection installs a voice, or claim all MIDI channels are TX802 parts.
Do not commit private fixtures or generated song data. Keep external notes separate.

## Voice CSV follow-up

Legacy-schema tables/<stem>_voice.csv is now exported and owned. Preset20 rows and
emitted I21+ custom assignments follow the original CSV generation rules. 36 focused
TX802 checks pass (including 5 audio-host checks). Public custom_voice export passed.
The exact old main8816ed8 entry was run unchanged: it emits CSV/JSON/MIDI, no .syx.
Owner recalls complete automation; requested original invocation to reconcile this.
Use TX802-named old tools only. Do not add a generic DX7II format or claim automatic
usable voice generation. See docs/tx802_voice_csv.md and external notes.

Audio comparison plumbing is under separate development: Texed21a92be is installed
next door and IKAOPLL RTL is built. Stock Texed and IKAOPLL smoke WAVs exist. The dry
host consumes actual SMF and reports its assumptions; matching-voice comparison is
not validated. Legacy TX802-tool bank render is silent, initialization control is
nonzero. Resolve voice serialization before interpreting that as TX802 accuracy.

## Automatic SysEx checkpoint

Original TX802-named converter tools are now connected automatically. Explicit I1..64
slots prevent row-order drift and bank truncation. Actual Texed acceptance is required
before publication; single/bank decoded145 parameter bytes must match excluding names.
The copied single writer was corrected to unpack128->155; its outer Format00 stays.
A real public custom case passed bank01/bank02 +15 single packet acceptance and slot
placement. Unit tests mock emulator I/O; the public integration uses real Texed.
Owner clarified calibration is of the parameters BEFORE SysEx, using DX7II as an
acceptable proxy. Texed is not treated as a full TX802 emulator. Next: explicit DX7II
parameter CSV and one reproducible diagnostic/preset calibration, legacy kept separate.
