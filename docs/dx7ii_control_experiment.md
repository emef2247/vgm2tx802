# Controlled residual diagnosis for preset10 — 2026-11-16

The goal is to explain remaining differences before expanding operator topology.
The production preset map and the published parameter CSV are unchanged by this probe.

```bash
python scripts/probe_tx802_controls.py --outdir outputs/control_probe
```

## Rate scaling: plausible mismatch, unsuccessful intervention

Temporal measurements show that the source partial balance evolves differently at
A3/A4/A5 while the present target is nearly pitch-independent. Source RTL
IKAOPLL_eg.v applies BLOCK[2:1] even with KSR=0. Texed's current operatorRS=0 adds
no keyboard rate contribution. This suggests an envelope-rate hypothesis, not proof
that rate scaling alone explains the audible difference.

The experiment freezes ALG4, ratios, levels and all other controls. Six identical
training cases cover A3/A4/A5 x0.25/0.9s. Sixteen candidates cross modulatorRS0..3
with offsets -8/-4/0/+4 to all four modulator rates. Baseline, RS-only, offset-only
and combined interventions are explicit. Selection uses the existing composite
mean+0.25*worst; new event-aligned temporal measurements are diagnostic only.
Raw level differences and normalized spectral shape are retained separately.

**Baseline wins (0.0584570435).** None of these16 interventions improves the stated
objective. This does not rule out finer rate offsets or level scaling. It does rule
out treating the observed KSR mismatch as a demonstrated fix. Reserved D4/Fsharp5
x0.18/1.2s were rendered after selection; since baseline was selected there is no
claimed improvement. All output tails end silent, with zero clipping.

[Aggregates](../data/tx802/experiments/2026-11-16_rate_scaling.csv) retain this negative
result. Full candidate parameters, musical-window rows, source references, WAVs and
per-case scores remain under outputs/dx7ii_control_probe_20261116/.

## VIB ablation: a separately observed missing behavior

Following Muse's suggestion, the script reads the actual external IKAOPLL ROM entry
at runtime and translates it to a user patch. The original ROM and exact custom
reference WAVs are sample-identical (relative error0). The two operator AM/VIB bits
are then cleared; AM was already0, so the intervention isolates VIB for this preset.
The external ROM contents are not copied into the repository's scripts/tables.

On an A4/2.4s probe, local fundamental-demodulation cents have standard deviation
6.3523 with VIB and0.5856 without. Subtracting the two tracks isolates a6.3191-cent
standard deviation, with a dominant sinusoidal fit near6.075Hz. This is a
source-relative phase diagnostic, not proof of absolute pitch. Timbre changes can
also affect local phase estimation; exact-patch control and paired subtraction make
the attribution stronger than a single waveform's estimate alone.

The current target has PMD=0/PMS=0, so this behavior is absent by construction.
A bounded LFO frequency/depth experiment is the next action. It will retain the
fixed common gain, keep topology unchanged and compare new source-relative paired
tracks, with fresh notes/durations reserved before fitting.

## Evidence levels and coordination

Muse is exploring OPM using IKAOPM RTL. This work targets DX7II using Texed as a
proxy; the two evidence levels must not be conflated. Share controlled ablation and
measurement methods, without assuming target parameters transfer between models.
