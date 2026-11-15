# TX802 calibration checkpoint — 2026-11-15

## Owner scope and state

Branch codex/tx802-musical-layer in G:/repository/emef2247/msx_vgm2tx802.
MSX base95e6dbc; original TX source8816ed8. No GitHub remote or push created.
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
- Trumpet7/Synthesizer10 retain seeds; not proven optimal, further search is possible.
- Fixed common sine-control gain anchor; no per-song/voice normalization.
- Public scale/volume/range and designated MSLND01 rendered in both engines.
-16 profile packets accepted;4 nonzero target WAVs;zero clipping. MSLND01:640 notes.

See docs/dx7ii_preset_calibration.md and data/tx802/OPLL_DX7II_calibration.json.
Generated evidence lives in outputs/dx7ii_preset_calibration_20261115/ and
outputs/dx7ii_preset_validation_final_20261115/. No song material is committed.

## Verification and limits

47 focused TX802 tests pass, including format/duration/nonfinite rejection. All30
stored fresh E5 seed/fit scores were recomputed unchanged under the strict checks.
18 inherited native-source checks passed earlier; native code remains unchanged.
Fresh validation supports only the stated composite score, not verified pitch or
perceptual fidelity. OPLL AM/vibrato, key scaling and full velocity response are not
fitted. Public fixture PSG/SCC initialization is explicitly omitted in OPLL comparison.
No hardware audition or complete local_only regression has been run.

## Next allowed action

Owner explicitly requested further new-parameter exploration for7/10; widen ratio
and modulator-envelope search, keeping this checkpoint for comparison.
Further fitting should prioritize7/10 and retain unused pitches/durations. Production
preset mapping is unchanged; opt-in validation uses preset_voice_map. Legacy CSV and
calibrated target parameters must not be silently conflated.

## Must not do

Do not mutate native time/units to make MIDI or a synth pass. Do not assume packet
acceptance proves usable musical parameters. Do not claim a full TX802 emulator or
hardware equivalence. Preserve original source worktree changes, independent output
products, candidate evidence and separate private field notes. Do not push implicitly.
