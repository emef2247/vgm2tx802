# Preset10: a separately fitted vibrato comparison profile

## Output and scope

[OPLL_DX7II_presets_vibrato.csv](../data/tx802/OPLL_DX7II_presets_vibrato.csv) is a
full15-preset comparison profile. It changes only preset10's LFO_SPEED=38, PMD=26,
PMS=1 from the published baseline. Wave0 (triangle), delay0 and sync0 remain fixed.
The primary CSV, native musical layer and normal MIDI assignments are unchanged.

[Metadata and all reserved-case results](../data/tx802/OPLL_DX7II_vibrato_experiment.json)
retain the source/model settings, input hash and limitations. This is a Texed Modern
DX7II-proxy result. No TX802 hardware or perceptual equivalence is claimed.

## Why this experiment

[The control experiment](dx7ii_control_experiment.md) did not improve preset10 with
simple rate-scaling offsets. An exact source-ROM-to-user-patch control rendered
sample-identically, allowing VIB to be removed without substituting a different
instrument. Source AM was already off; the fitter now clears only VIB and preserves
all other bits. Both operators have source VIB enabled for this preset, making a
common pitch LFO a plausible target approximation. Do not apply this conclusion
blindly to presets where only one operator enables VIB.

The previous objective omitted direct vibrato matching. We therefore fit the
**difference** between local phase tracks with/without modulation on each engine.
Source and target paired controls separate much of the timbre-dependent phase drift.
This estimates source-relative variation; it does not certify absolute pitch.

## Method and reserved cases

Training is A4 held2.4s. Local60ms fundamental demodulation, sampled every10ms,
provides a cents track. A2..12Hz sinusoidal scan at0.025Hz steps estimates the dominant
frequency. Four harmonic amplitudes and track standard deviation describe shape/depth.
Phase-invariant selection uses frequency error scaled by0.25Hz, log-depth error and
harmonic-amplitude error. There is no free depth rescaling and no audio normalization.
LFO starting phase is deliberately not part of this fit.

The coarse41-candidate run reserved G4/B5 x0.33/0.95s. It recovered frequency/depth
but worsened the old composite on3/4 cases. These are known diagnostics now.
Fine depth refinement uses only the same A4 training track; **new E4/D6 x0.27/1.05s**
were reserved before that47-candidate run and rendered after freezing selection.
Only the two long gates provide enough data for frequency/depth validation; short
gates receive old-composite, event-aligned level/spectrum, clipping and octave checks.
Invalid/clipped candidates are ineligible, and an all-invalid run fails explicitly.

| Case | Source frequency | Target frequency | Source phase-track std | Target phase-track std |
| --- | ---: | ---: | ---: | ---: |
| A4/2.4s training | 6.075Hz | 6.100Hz | 6.319cent | 6.243cent |
| E4/1.05s reserved | 6.050Hz | 6.100Hz | 6.232cent | 6.192cent |
| D6/1.05s reserved | 6.050Hz | 6.100Hz | 7.039cent | 6.212cent |

Values are descriptor estimates at the stated scan resolution, not hardware
measurement precision. D6 remains about12% shallower; a fixed global depth does not
fully reproduce the observed pitch-dependent source excursion. The result restores
an absent behavior without resolving all remaining timbre/level differences.

| Reserved case | Previous composite | Vibrato candidate composite |
| --- | ---: | ---: |
| E4/0.27s | 0.031462 | 0.031663 |
| E4/1.05s | 0.064070 | 0.063481 |
| D6/0.27s | 0.025886 | 0.022391 |
| D6/1.05s | 0.062180 | 0.058670 |

Three decrease; one slightly increases. Vibrato-descriptor quality and the older
composite are different evidence and are reported separately. All four selected
reserved WAVs have zero clipping and pass the source-relative octave screen. This
screen is not a complete pitch detector. The two short cases do not validate vibrato
rate/depth, and no claim of overall timbre improvement follows solely from the table.

## Reproduction and audition preparation (WSL)

```bash
python scripts/fit_tx802_vibrato.py \
  --presets data/tx802/OPLL_DX7II_presets.csv --fine-depth \
  --validation-notes 64 86 --validation-gates .27 1.05 \
  --outdir outputs/vibrato_fit
python scripts/validate_tx802_calibration.py INPUT.vgm \
  --presets data/tx802/OPLL_DX7II_presets_vibrato.csv \
  --outdir outputs/vibrato_audition --gain 0.1876890209599859
```

Use the adjacent pinned Texed/IKAOPLL setup from [audio_comparison.md](audio_comparison.md).
All synthetic sources, candidate rows, paired WAVs, phase tracks, JSON jobs, temporal
CSV diagnostics and selected packets remain under outputs/dx7ii_vibrato_fine_20261116/.
Only parameter data, numeric metadata, authored tooling and documentation are committed.
The profile is separate so the owner can compare it with the previous candidate.

The final comparison CSV passed actual Texed loading for16 packets (one bank and
fifteen singles), with decoded parameter equality and placement verified.56 focused
checks pass across the target/SMF/assets/audio/calibration tooling. Packet acceptance
does not certify the musical accuracy described above.
