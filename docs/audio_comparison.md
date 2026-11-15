# Offline audio reference environment

Run in WSL. This is comparison/development tooling, separate from production MIDI.
It does not send anything to MIDI hardware or install voices in the TX802.

## Prepared environment

- Adjacent `../IKAOPLL-verilator`: existing setup_env.sh fetched RTL and built
  build/obj_dir/ikaopll_sim. An authored public fixture renders to 48000 Hz WAV.
- Adjacent `../texed`: https://github.com/WouterVanNifterick/texed,
  revision 21a92be6b5531e8fce18ba93e0bd84057b87552b, GPL-3.0, not vendored here.
- Node24 was obtained via npm exec; the system Node20 was not replaced.
  Runtime version recorded in this run: v24.22.3. pnpm10.12.4 is used for dependencies.

Reproduce the Texed dependency setup after cloning that revision:

```bash
cd ../texed/texed-ts
npm exec --yes --package=node@24 --package=pnpm@10.12.4 --   pnpm install --frozen-lockfile --filter @texed/cli... --ignore-scripts
```

The stock Texed CLI is a useful smoke host but not the comparison reference: its
part/bank routing and initial engine/function settings differ from this converter.

## Explicit reference host

```bash
python scripts/render_tx802.py INPUT.mid --out OUTPUT.wav --voices voices.csv
```

The voice-location CSV is separate from the generated OPLL parameter CSV:

```csv
bank,voice,syx,library_bank,program
I,1,bank01.tx802_wmem32.syx,internalA,0
I,33,bank02.tx802_wmem32.syx,internalA,0
```

`voice` is the intended TX802 I/C/A/B slot, 1-based. `library_bank`/`program` select
an explicitly populated Texed SysEx-file slot, program 0..31. Relative paths resolve
beside the CSV. Missing slots fail; no factory/init substitution is implicit.
The existing TX802-named scripts from the original project generate the supplied
files. See tx802_voice_csv.md. This host does not invent a new outgoing SysEx format.

An explicit routing/scheduling smoke can instead use `--init-voice`. This option is
NOT a musical comparison. RX21/GM drums require a separate renderer; they fail here
unless `--omit-drums` explicitly records their omission.

- Actual SMF channel events are decoded using our stdlib encoder/inspector.
- Rational tempo integration and SMF port metadata preserve independent ports.
- Host rendering splits at rounded event-sample positions. Texed itself buffers
  64-sample synthesis blocks; control response is not sample-perfect hardware timing.
- The host uses the Texed Modern/Mark-II core with its hardware accuracy setting.
- Dry Parts bypass rack FX/compression. Fixed gain defaults .25; no peak normalization.
- Bend Range defaults12/Step0. FC2/CC11 volume range is explicitly set99 in the
  reference setup. These are declared host settings, not validation of hardware setup.
- Tail defaults1second. Original event/EOT silence is retained. Align the converter's
  initialization lead when comparing to original VGM, and distinguish release tails.
- JSON job/report retain events, MIDI/voice hashes, revision, settings, clipping and RMS.

## Current measurements and limits

The IKAOPLL and stock Texed WAV smoke succeeded. The dry host also renders audible
initialization-voice controls. For the public custom_voice fixture, using the
unchanged original TX802-named conversion tools generated35 OP6 rows. The old bank
tool truncates at32; the final3 were explicitly passed as a second32-voice bank using
the same tool. Both banks load, with explicit I33..I35 mapping to second-bank0..2.
The resulting Texed reference WAV is silent (peak0), while the same MIDI with an
explicit initialization voice has peak .017507. This was a legacy voice-data /
serialization observation, not evidence that TX802 hardware is silent or inaccurate.
The later explicit DX7II parameter profile renders nonzero; the legacy parameter
branch remains a comparison baseline, not a calibrated preset set.
A valid4104-byte packet/checksum does not establish usable operator data.

That smoke used no private corpus or hardware audition. Later focused calibration
validation includes the owner-designated MSLND01; see the checkpoint below.
Source products and production conversion have not been changed to make Texed pass.

## Calibrated profile checkpoint

The experimental 15-preset parameter CSV, fixed shared gain anchor, 16 accepted
SysEx packets and three public plus MSLND01 source/target WAV comparisons are now
available. See [dx7ii_preset_calibration.md](dx7ii_preset_calibration.md) for exact
scope, objective, limitations and reproduction. Texed remains a DX7II proxy. No
hardware or perceptual match is claimed; normal export keeps its legacy assignments.
