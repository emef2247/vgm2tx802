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
is being reconciled before adding new automatic wiring. Do not present that
recollection or an unused import as proof that a call exists in this checkout.

CSV publication uses the same source ownership and edited-output protection as MIDI.
