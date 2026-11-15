# OPLL melodic presets: experimental DX7II parameter set

## Deliverables and scope

- [OPLL_DX7II_presets.csv](../data/tx802/OPLL_DX7II_presets.csv): 15 melodic presets, 150 explicit DX7II-oriented columns.
- [Initial metrics](../data/tx802/OPLL_DX7II_calibration_metrics.csv): first-checkpoint seed and selected scores.
- [Broader-search metrics](../data/tx802/OPLL_DX7II_exploration_metrics.csv): current7/10 training and reserved-case component scores.
- [Manifest](../data/tx802/OPLL_DX7II_calibration.json): revisions, clock, gain anchor and limitations.

IKAOPLL RTL provides the measured source; Texed Modern is the DX7II proxy. This is
an experimental parameter set, without TX802 hardware audition or a claim of exact
OPLL reproduction. Rhythm and custom OPLL voices are outside this calibration.
The legacy OP2 CSV and production preset assignments remain available and unchanged.

## CSV schema

`voice` and `source_preset` are both **1-based**, 1..15. The `OP1_R1` column identifies
this explicit schema; the legacy OP2 schema instead has zero-based voice values.
`name` is descriptive; the wire name is limited to ten ASCII characters.

| Columns | Meaning / stored range |
| --- | --- |
| ALG, FB, SYNC | zero-based algorithm 0..31, feedback 0..7, oscillator sync 0..1 |
| LFO_SPEED/DELAY/PMD/AMD | 0..99 |
| LFO_SYNC/WAVE/PMS | 0..1, 0..5, 0..7 |
| TRANSPOSE | 0..48; 24 is neutral |
| PEG_R1..4 / PEG_L1..4 | pitch envelope rates / levels, 0..99 |
| OP1..6_R1..4 / L1..4 | operator envelope rates / levels, 0..99 |
| OP1..6_BP/LD/RD/LC/RC | scaling breakpoint/depths 0..99; curves 0..3 |
| OP1..6_RS/AMS/KVS | rate scaling 0..7, amplitude sensitivity 0..3, velocity sensitivity 0..7 |
| OP1..6_OL | output level 0..99 |
| OP1..6_MODE/COARSE/FINE/DT | mode 0..1, coarse 0..31, fine 0..99, detune 0..14 (7 neutral) |
| PB_RANGE/PB_STEP | receiver/reference setup; **not** extra bytes in Format00/09 |

All delivered rows use ALG=4 (display algorithm 5), three parallel FM pairs.
The carrier half-wave approximation uses their relative ratios and levels. Standard
VMEM operator order is 6..1; tests check independent packed-field vectors.
The existing TX802-named bank/single tools recognize this schema directly, bypassing
the legacy OP2-to-OP6 mapping. They retain Format09 bank and Format00 single framing.
Actual Texed loading, checksum, placement and bank/single parameter equality gate
publication. Successful loading does not establish musical fidelity.

## Initial checkpoint measurement and selection

Source time remains integer 44100-Hz VGM samples; OPLL clock is 3579545 Hz. Both
renderers produce 48000-Hz PCM. Probes have 100 ms lead, the declared gate and a
400 ms release tail. Source-only analysis chooses a fixed 120 ms window for all
candidates of a case. Features use raw RMS, 16 normalized partial samples on a
half-base-frequency grid, and a normalized 10 ms RMS envelope.

The composite objective is:

```text
0.5 * log2(target_RMS * gain_correction / source_RMS)^2
+ 16 * mean((target_partials - source_partials)^2)
+ mean((target_envelope/target_RMS - source_envelope/source_RMS)^2)
```

A single, authored sine-carrier control sets the gain correction 0.7507560838399435
for the raw target gain 0.25. The effective mono gain is 0.1876890209599859. This
same anchor applies to all voices and songs; there is no per-voice/song normalization.
Measured output-level probes choose level adjustments rather than assuming OL is linear.
Audio checks reject incompatible formats, incomplete durations and nonfinite features.

The legacy OP2 table supplies an explicit, valid DX7II **initial seed**, not an
assumption of exact ROM identity. Initial training uses A3/A4, each held 0.6 s.
Candidate sweeps vary modulator OL (+/-10), feedback (+/-2), carrier attack/release
(+/-12), then measured output-level fits (+/-2). These are bounded local searches.

The first A5/0.9 s check found regressions on presets 7, 10 and 12. It was therefore
reclassified as additional training for those three; it is not claimed as independent
validation after selection. A5 non-regression constrained their reselection. Presets
7 (Trumpet) and 10 (Synthesizer) retained the seed; preset 12 selected another candidate.

A fresh E5/0.75 s case, unused for selection, gives **13 lower composite scores and
2 ties**, with no composite regressions against the valid initial seed. This is
not a claim of independent improvement in pitch, every spectral/envelope feature,
or perceptual quality. Computed base-band peak cents is diagnostic only and is not
part of the objective; it is not reliable as a preset's musical fundamental.

Trumpet and Synthesizer remain priority candidates for further work. Keeping the
seed means no better candidate met this search's constraint, not that the seed is
optimal. Frequency ratios, operator topology, key scaling and wider envelope search
remain possible. New fitting must retain unused pitches/durations for validation.
OPLL AM/vibrato, key scaling and full velocity response have not been fitted.

## Reproduction (WSL)

Prepare the adjacent IKAOPLL build and pinned Texed dependencies as described in
[audio_comparison.md](audio_comparison.md). Only calibration/analysis needs NumPy;
normal MIDI export does not depend on it.

```bash
python scripts/calibrate_tx802_presets.py --outdir outputs/preset_calibration
python scripts/refine_tx802_presets.py outputs/preset_calibration
python scripts/validate_tx802_calibration.py INPUT.vgm \
  --presets data/tx802/OPLL_DX7II_presets.csv \
  --outdir outputs/preset_validation --gain 0.1876890209599859
```

The first two commands retain candidate CSVs, synthetic sources, packet pairs,
render jobs, WAVs and scores in outputs. The validation command explicitly uses the
calibrated preset map; normal export defaults do not change. Active rhythm and custom
voices outside the supplied profile are rejected. Non-OPLL omissions remain reported.

## Initial checkpoint integration

Three authored public patterns (scale ROM1, volume sweep, high/low range) and the
owner-designated MSLND01 rendered through both actual engines. Sixteen final packets
(one bank and fifteen singles) were accepted, with parameter readback and placement
checks. All four target WAVs are nonzero with zero clipped samples.

| Case | Notes | Target/source RMS difference | 10 ms envelope correlation |
| --- | ---: | ---: | ---: |
| scale ROM1 | 15 | +0.299 dB | 0.692 |
| volume sweep | 15 | +0.313 dB | 0.935 |
| high/low range | 21 | +0.025 dB | 0.703 |
| MSLND01 | 640 | +0.984 dB | 0.594 |

These are whole-render diagnostics, not timbre scores. Public fixtures contain
PSG/SCC initialization reported omitted; comparison is of the OPLL component only.
MSLND01 has no omitted devices. Song controls/quantization and Texed's 64-sample
internal buffer still affect the comparison. Generated source/target WAVs, event
plans and JSON reports remain under outputs/dx7ii_preset_validation_final_20261115/;
private source and song-derived artifacts are not committed.

## Broader construction experiment for presets 7 and 10

The owner requested new parameters for the two retained seeds. Run:

```bash
python scripts/explore_tx802_presets.py \
  --presets data/tx802/OPLL_DX7II_presets_initial.csv \
  --outdir outputs/preset_exploration
```

This freezes its input hash and validation set before searching. Training uses
A3/A4/A5 at 0.25 and 0.9 seconds. C4/C5 at 0.4 and 0.7 seconds are reserved until
selection. The earlier E5 is known evidence, not a fresh validation case here.

The staged beam search retains three candidates: frequency ratios / feedback /
parallel-pair mix, then carrier and modulator envelopes, then operator levels.
The main carrier remains at 1:1, secondary carriers at integer harmonics, with
fixed fine tuning and detune. A source-relative spectral octave-contrast screen
rejects clear shifted-octave matches; it is a conservative screen, not proof of
absolute pitch accuracy. ALG4 remains an experiment scope, not a limitation of
possible OPLL-to-DX7II mapping.

Each candidate is evaluated on the same six training cases. The selection objective
is the mean composite score plus 0.25 times its worst case. No individual-note seed
floor is imposed. Component scores, worst-case regression, parameter differences,
packets and WAVs remain inspectable; changed parameters alone are not an improvement.
The reserved cases are reported without changing the selected candidate.

### Broader-search result and current CSV

Each preset evaluated162 unique candidates. Preset7 changes17 parameters, activating
three carrier pairs and changing modulator rates/levels. Preset10 changes the three
carrier release rates from59 to60. Initial data and metadata remain in `_initial`
files. The earlier metrics CSV describes that initial checkpoint; the current7/10
component scores are in OPLL_DX7II_exploration_metrics.csv.

| Preset | Training mean +0.25*worst, before -> after | Reserved-case composite result |
| --- | --- | --- |
| 7 Trumpet | 0.241238 -> 0.113380 | all4 improve; delta -0.161 to -0.071 |
| 10 Synthesizer | 0.058970 -> 0.058457 | all4 slightly regress; delta +0.000058 to +0.000635 |

The current CSV retains both selected **experimental** rows so the owner can compare
new constructions. Preset10 is not described as an improvement. Its small change
shows that this bounded ALG4 search did not find a materially better generalizing
construction. No candidate was reselected using reserved-case results. Further
structures, phase/waveform approximation and modulation remain open work.
All selected reserved cases have zero clipped samples and pass the octave screen; no perceptual match is claimed.
The whole-song WAV measurements above belong to the initial CSV hash recorded in
OPLL_DX7II_calibration_initial.json, not a rerender of the new rows.

The updated CSV also passed actual Texed acceptance for one bank plus15 singles,
with decoded parameter equality and slot placement verified.50 focused tests pass.

## Controlled follow-up

A separate preset10 vibrato profile now restores a previously absent behavior. See
[the control experiment](dx7ii_control_experiment.md) and [vibrato comparison](dx7ii_vibrato_experiment.md).
The primary CSV and earlier experiment histories remain unchanged.
