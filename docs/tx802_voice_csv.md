# TX802 voice CSV compatibility

The native target exports `tables/<stem>_voice.csv`, also retained in diagnostics.
It contains the original 20 rows from `data/opll/presets/OPLL_OP2_MB14.csv`, then
actually emitted custom patches assigned to Internal I21..I64. The `voice` column
is zero-based: I21 is 20. Rows are sorted by assignment; unused gaps remain gaps.
Preset-bank assignments such as A11/B4 are not appended as new Internal voices.
The full eight-byte native patch remains in the assignment JSON and native evidence.

This is the legacy **OPLL 2-operator interchange CSV**, not packed six-operator
voice memory. Its columns/parameter values follow old `build_user_voice_tx802_csv`.
The user-row name now identifies the stable patch bytes rather than a temporary @v ID.
Legacy FB/WS interpretation is retained here for compatibility; this port does not
recalibrate that interpretation or mutate NativePerformance.

## Existing TX802-named tool route

The owner requested the original TX802-specific tools. In the original repository:

1. `tools/convert_op2csv_to_op6csv_tx802.py` converts OP2 CSV to TX802 OP6 CSV.
2. `tools/convert_tx802csv_to_wmem_bank_syx.py` produces a 32-voice Format09 bank.
3. `tools/convert_tx802csv_to_dx7_single_voice_syx.py` produces Format00 single
   voices for rows I21 onward. The DX7 name is part of this existing TX802 tool.

The recorded receiver forms are the existing 4104-byte Format09 bank and the
163-byte Format00 single voice, not a newly invented DX7II envelope or bulk format.
Single-voice reception targets an edit buffer; it is not an automatic bank store.

The bank tool pads to 32 rows and truncates above 32. Do not silently truncate an
I33+ assignment or assume row order encodes sparse `voice` values correctly. Bank
splitting/padding must be explicit and its slot mapping inspected before use.
A valid header/size/checksum alone does not prove that operator parameters survive.

## Verified source flow and remaining discrepancy

Original local and remote main both resolve to 8816ed8. The tx802/syx branch
85aadb7 is already merged. Inspection of the complete `src/vgm2midi.py`, its
TX802 builder, `MidiBuilder.build` and actual execution on an authored public VGM
show MIDI, mapping JSON and OP2 CSV generation. In that checkout the voice-SysEx
helpers are imported but not invoked by that entry point. The separate tools above
can generate SysEx. The owner recalls a completely automated route; its invocation
was not found in that checkout; the owner approved the new automatic wiring below. Do not present that
recollection or an unused import as proof that a call exists in this checkout.

CSV publication uses the same source ownership and edited-output protection as MIDI.

## New automatic voice products

The new export entry now connects the original TX802-named tool stages automatically.
`voices/<stem>.bank01.syx` and bank02 when needed retain Format09. Actual I21+ slots
also produce `voices/<stem>.I21.syx` etc in Format00. `voices/<stem>.texed.csv` records
explicit file/slot locations for the offline reference host. All CSVs, commands and
slot/padding metadata remain in `_diagnostics/<stem>/voice_assets/`.

The vendored OP2->OP6 converter and the bank writer's legacy parameter branch retain
their original implementation. The single writer corrects packed128-to-VCED155
serialization rather than copying128 and padding. Both writers additionally accept
the explicit DX7II calibration schema described below; packet forms are unchanged.
`tools/legacy_tx802/provenance.json` records original/current hashes and this change.

SysEx is published only after actual Texed acceptance, bank placement and decoded
single-vs-bank equality (first145 VCED bytes, excluding names). Failed products stay
in diagnostics and have an explicit voice_assets_status; MIDI/source products remain
independent. No hardware upload or parameter/timbre equivalence is certified.
The existing parameter mapping remains a legacy baseline for DX7II-proxy calibration.

## Explicit DX7II calibration CSV

`data/tx802/OPLL_DX7II_presets.csv` is a separate 1-based, fully specified DX7II
parameter schema, identified by OP1_R1. The original TX802-named bank/single tools
pack it directly using tx802_sysex_codec.py. OP2 conversion is bypassed and all
calibrated slots emit singles, including I1..I15. Legacy OP2 behavior is preserved.
See [calibration details](dx7ii_preset_calibration.md). This measured experimental
profile does not silently replace production voice assignments or the old CSV.
