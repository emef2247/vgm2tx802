# DX7II / TX802 rhythm candidates

This experimental path searches **DX7II/TX802 parameters that approximate OPLL
percussion audio**. It uses IKAOPLL output as the reference; it does not extract
OPLL instrument ROM parameters. Existing melodic profiles and the production
GM/RX21 percussion mapping remain unchanged.

## Reproduce the search

With the existing IKAOPLL and Texed checkouts prepared as described in
[the melodic calibration guide](dx7ii_preset_calibration.md), run under WSL:

```sh
python3 scripts/calibrate_tx802_rhythm.py --outdir outputs/dx7ii_rhythm
```

`--families BD TOM` restricts a run. Each output directory is an experiment;
use a new directory to retain previous trials and failures.

The source probes are authored VGM streams containing performance-register
writes and exact integer 44100-Hz waits. They explicitly initialize the rhythm
mask, channels 6–8 FNUM/BLOCK and all five attenuation fields. Each hit starts
in a fresh simulator process. Register context is an oscillator input, not an
assertion that every drum has a melodic MIDI pitch.

`py/opll_rhythm_context.py` additionally extracts observed context from a
NativePerformance. Its CSV retains the pre-trigger state, changes during the
hit, partner channels, register provenance, observed stop and an optional
observation window after that stop. Unknown registers remain unknown. It does
not modify native events or infer an audible-decay endpoint.

## Parameter and audio artifacts

- `OPLL_DX7II_rhythm.csv`: five explicit six-operator rows, with 1-based voice
  slots 16–20. `rhythm_family`, `reference_note` and `reference_hz` identify the
  family and the exact target probe pitch. Do not interpret these as a universal
  source-to-drum pitch mapping.
- `configuration.json`, `selection.json`, `trials.csv`: experiment conditions,
  candidate parameters and choices frozen before reserved evaluation.
- `training_metrics.csv`, `validation_metrics.csv`, `summary.json`: separate
  amplitude, envelope, spectrum, flatness and concentrated-partial penalties,
  clipping and end-of-capture energy.
- `source/`, `packets/`, `waves/`: authored VGM, reference WAV, single/bank SysEx,
  rendered candidate WAV and actual Texed packet-acceptance reports.

The target host uses Texed Modern with hardware accuracy, dry output, the same
fixed gain anchor as melodic calibration, and no per-voice normalization. The
search begins with an authored decaying FM palette and explores ratios,
feedback, multiple operator pairs, envelopes and levels. It does not assume
that copying a Y8950 rhythm register set will create a DX7II drum.

The objective compares onset-aligned 5ms RMS envelopes and frequency-band
distributions in 0–15, 15–40, 40–100, 100–250 and 250–500ms windows. Spectral
flatness and concentration expose tonal ringing that an overall decay score
could hide. This is still a bounded experimental objective, not proof that a
noise-like instrument is perceptually equivalent.

Both 80ms and 300ms gates are training cases. Reserved cases use 45ms/190ms
gates, attenuation 4, a different pre-roll and a changed partner-channel pitch.
They are generated only after each family is selected. Failed reserved cases
remain failures; they are not silently added to the training set.

IKAOPLL writes floor(total source samples × 48000 / 44100) frames. The target
probe host rounds each scheduling interval separately. Each WAV is checked
against its own explicit contract; their common complete 5ms envelope bins are
compared. This does not permit arbitrary truncated renders.

## Scope and acceptance

The owner has deferred mixed melody/drum channel allocation and has two TX802s
available. This experiment therefore uses five separate rhythm voices. It does
not drop voices to fit one unit or introduce performance/kit SysEx.

Known validation limits include rapid retriggers, overlapping release tails,
rhythm-mode transitions, arbitrary source pitch states and song-level listening.
Reserved context tests measure sensitivity; they do not establish an automatic
pitch-control mapping. Texed packet acceptance and parameter readback prove
representation, not acoustic fidelity or hardware acceptance.

An FM snare may match an overall envelope while retaining an unwanted narrow
high-frequency partial. Inspect the individual windows and isolated sound before
accepting a candidate; adding noise around a defective body does not cure it.
