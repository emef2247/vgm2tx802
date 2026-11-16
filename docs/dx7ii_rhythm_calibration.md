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

The published five-row candidate CSV was selected by rescoring an initial pool
of 82 candidates per family. The first objective preferred a BD candidate with
an excessive tail. The revised objective adds log-envelope and -40dB decay-time
differences, and excludes a candidate that is still sounding near the capture
end after the reference has already decayed. The initial pool and its results
are retained; this is a bounded reselection, not a new unrestricted search.

```sh
python3 scripts/calibrate_tx802_rhythm.py --outdir outputs/rhythm_reselected \
  --rescore-from outputs/dx7ii_rhythm_final_20261116
```

Rescoring requires the complete original experiment directory, including WAVs,
packets, jobs, configuration and trials. It verifies renderer/gain conditions
and byte-identical candidate parameters. Reserved references were already
generated in the first pass; their previous scores do not enter selection,
and these references are not described as newly collected validation data.
See [candidate metadata](../data/tx802/OPLL_DX7II_rhythm.json) and the
[reserved measurements](../data/tx802/OPLL_DX7II_rhythm_validation.csv).

The reselection lowers the composite score in 24 of the 25 reserved comparisons.
The 45ms BD case worsens from 1.9568 to 2.9317 (about 50%); other BD aggregate
improvements also trade away amplitude accuracy. No selected reserved render
clips or reaches the declared incomplete-tail condition. These are measurements
of the specified probes, not acceptance of the drum sounds.

Both 80ms and 300ms gates are training cases. Reserved cases use 45ms/190ms
gates, attenuation 4, a different pre-roll and a changed partner-channel pitch.
They are generated only after each family is selected. Failed reserved cases
remain failures; they are not silently added to the training set.

IKAOPLL writes floor(total source samples × 48000 / 44100) frames. The target
probe host rounds each scheduling interval separately. Each WAV is checked
against its own explicit contract; their common complete 5ms envelope bins are
compared. This does not permit arbitrary truncated renders.

## Scope and acceptance

To export an explicit rhythm-only FM audition from one VGM/VGZ file:

```sh
python3 scripts/export_tx802_rhythm.py INPUT.vgm --outdir outputs/rhythm_audition
```

Use a new or empty directory. The script writes native passes, a rhythm-context
CSV, MIDI, a hit/routing CSV, a projection report and validated voice SysEx.
`--presets` selects another complete five-family DX7II CSV. `--texed` selects
the emulator checkout used for acceptance. It does not modify the normal batch
exporter or combine the melody into this audition.

The five MIDI channels are 1–5 on port 0, not GM drum channel 10. Configure five
independent receiver parts and load the bundled voices at I16–I20. The required
pitch-bend range is 12 semitones with Step 0. No Performance SysEx is sent.
CC7=100 and CC11=127 match the calibration probe's common setup. Each hit uses
the inherited onset-attenuation velocity table; subsequent source-volume changes
remain in native evidence with an explicit loss report. Target pitches are fixed
to the CSV reference conditions, not inferred from noisy percussion spectra.

Repeated hits shorten the preceding same-family gate, ordering Note Off before
the next Note On. Minimum-tick displacements are reported. An unobserved source
stop uses an explicit target-only 5512-source-sample gate (about125ms), never a
fabricated native stop. Actual release tails and two-note TG voice stealing
still need listening checks.

The public `rhythm_only_test02` fixture produced all five FM parts and six
accepted SysEx packets. Its Texed audition WAV was non-silent with no clipping.
Focused TX802 and source-context checks pass (69+11 tests under WSL).

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
