# TX802 experimental profiles — 2026-11-16

## Branches and owner intent

Work in G:/repository/emef2247/msx_vgm2tx802, local branch codex/tx802-musical-layer.
Push is authorized to old emef2247/vgm2tx802, branch codex/dx7ii-preset-calibration;
never update that repository's main. External field/AI notes may be committed and
pushed to private my-external-intelligence/main. Preserve unrelated untracked outputs.
MSX base95e6dbc; original TX source8816ed8. Native code/original edits are preserved.

The deliverable is new DX7II-compliant OPLL melodic-preset parameters. Texed Modern
is a DX7II proxy, not complete TX802 emulation. Muse explores OPM with IKAOPM RTL;
keep evidence levels separate. The owner judges listening and hardware behavior.

## Profiles and checks

- OPLL_DX7II_presets.csv:15 rows/150 columns,1-based explicit DX7II schema.
- `_initial` CSV/metadata preserve the first checkpoint.
- Primary preset7 changes17 parameters, improving all4 reserved composites.
- Primary preset10 has a minor R4 change; reserved composites slightly worsen.
- OPLL_DX7II_presets_vibrato.csv is a SEPARATE comparison profile. Only preset10's
  LFO_SPEED38/PMD26/PMS1 differ. Primary CSV and production assignments are unchanged.
-56 focused checks pass. Final vibrato profile16 SysEx packets were accepted by
  actual Texed, with decoded parameter equality and placement verified.
- Production MIDI, source VGM and Blueprint remain independent products.

## Latest controlled findings

Code757a0d1: a KSR mismatch motivated16 RS/rate-offset conditions, but baseline wins.
This negative result remains documented. Do not call RS a demonstrated fix.
Event-aligned temporal CSVs show pitch-dependent source partial trajectories.

Muse's VIB-ablation suggestion was implemented. Actual external ROM10 -> custom
patch renders sample-identically. Removing VIB isolates a paired local-phase
standard deviation of6.319 cents, dominant frequency~6.075Hz. AM was already off.
The fitter preserves AM when clearing VIB. Local phase is timbre-dependent and
source-relative; it does not certify absolute pitch.

The fine LFO fit uses47 candidates and A4/2.4s training. New E4/D6 x0.27/1.05s
were reserved before selection. Only long gates measure vibrato frequency/depth:
E4 source6.232 cents vs target6.192; D6 source7.039 vs target6.212 (about12% shallow).
Frequency is~6.05Hz source vs6.10 target. Old composite improves3/4; E4 short gate
slightly worsens. Starting LFO phase is not fitted. No overall timbre/hardware claim.
All four reserved outputs have zero clipping and pass the octave screen.

Artifacts: outputs/dx7ii_vibrato_fine_20261116/ and
outputs/dx7ii_vibrato_voice_acceptance_20261116/.
See docs/dx7ii_control_experiment.md, docs/dx7ii_vibrato_experiment.md and the adjacent
JSON metadata. Initial public3+MSLND01 song WAVs use the initial CSV, not this new
profile. No complete private-corpus regression has been run.

## Next allowed work

Owner audition of baseline/vibrato profiles. Investigate residual spectral evolution
and pitch-dependent modulation depth before expanding topology. Muse's reply8779c41
and Codex's responsea808282 are in private AI_NOTES.md -> the TX802 contact thread.
The fixed-three-basis versus free-partial lower-bound question remains open.
SD-noise structure is a separate pending task; do not edit that route implicitly.

## Must not do

Do not reshape native timing/units, conflate0-based OP2 with1-based DX7II CSV, or
claim packet loading proves timbre. Preserve integer44100-Hz source time, fixed gain,
failed candidates and reserved-data provenance. Do not call known validation fresh.
