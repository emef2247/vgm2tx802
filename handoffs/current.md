# TX802 calibration checkpoint — 2026-11-15

## Owner scope and state

Branch codex/tx802-musical-layer in G:/repository/emef2247/msx_vgm2tx802.
MSX base95e6dbc; original TX source8816ed8. Owner now authorizes push to old emef2247/vgm2tx802 as codex/dx7ii-preset-calibration.
Use an explicit branch ref; do not update main.
The owner's deliverable is a DX7II-compliant CSV approximating OPLL melodic presets.
Texed is an accepted DX7II proxy, not complete TX802 emulation. Melody first.

## Completed

- NativePerformance -> TX802 SMF with independent source VGM and Blueprint products.
- Legacy20-preset/custom OP2 CSV retained; TX802-named tools connected automatically.
- Explicit I1..64 placement and split banks; packed128 -> VCED155 correction.
- Actual Texed acceptance, bank/single145 parameter equality and placement checks.
- Dry Modern-core reference host; actual SMF timing, ports and declared voice setup.
- data/tx802/OPLL_DX7II_presets.csv: 15 rows,150 explicit DX7II columns,1-based slots.
- Calibration schema packs directly through the existing TX802-named tools.
- Bounded A3/A4 fitting; failed A5 checks reclassified as training for7/10/12.
- Fresh E5/0.75s validation unused for selection:13 lower composite scores,2 ties.
- Initial checkpoint retained7/10 seeds; initial CSV/metadata are preserved separately.
- Broader search now changes7 by17 parameters;all4 reserved composites improve.
-10 changes3 release rates;all4 reserved composites slightly regress;experimental only.
-162 candidates per preset; component scores and parameter changes are retained.
- Fixed common sine-control gain anchor; no per-song/voice normalization.
- Public scale/volume/range and designated MSLND01 rendered in both engines.
-16 profile packets accepted;4 nonzero target WAVs;zero clipping. MSLND01:640 notes.

See docs/dx7ii_preset_calibration.md and data/tx802/OPLL_DX7II_calibration.json.
Generated evidence lives in outputs/dx7ii_preset_calibration_20261115/ and
outputs/dx7ii_preset_validation_final_20261115/. No song material is committed.

## Verification and limits

50 focused TX802 tests pass, including audio-input guards and octave-screen vectors. All30
stored fresh E5 seed/fit scores were recomputed unchanged under the strict checks.
18 inherited native-source checks passed earlier; native code remains unchanged.
Fresh validation supports only the stated composite score, not verified pitch or
perceptual fidelity. OPLL AM/vibrato, key scaling and full velocity response are not
fitted. Public fixture PSG/SCC initialization is explicitly omitted in OPLL comparison.
No hardware audition or complete local_only regression has been run.

## Next allowed action

Broader7/10 exploration completed. Owner can inspect current and `_initial` CSVs
on the separate GitHub branch. Further work should prioritize10; do not claim the
small changed candidate is an improvement.
Further fitting should prioritize7/10 and retain unused pitches/durations. Production
preset mapping is unchanged; opt-in validation uses preset_voice_map. Legacy CSV and
calibrated target parameters must not be silently conflated.

## Must not do

Do not mutate native time/units to make MIDI or a synth pass. Do not assume packet
acceptance proves usable musical parameters. Do not claim a full TX802 emulator or
hardware equivalence. Preserve original source worktree changes, independent output
products, candidate evidence and separate private field notes. Push is authorized only for the old TX802 separate branch in this task; private
notes remain separately committed without an implied push.

Final broader-profile16 SysEx packets also passed real Texed acceptance, parameter
equality and placement; selected reserved synthetic cases have no clipping.
