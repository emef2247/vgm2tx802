# TX802 projection of NativePerformance

## Boundary and provenance

`VGM -> native State / Segments -> NativePerformance -> TX802 MIDI events -> SMF`

Source analysis and musical information follow the pinned MSX baseline unchanged.
MIDI consumes unit pitch/volume/voice curves, percussion events and source sample
positions directly. It does not reparse MML, Blueprint, reference VGM, or old OPLL
frame traces. The reference VGM retains original chip identities; it is not a TX802
render. Source products remain available after target failure.

`migration/source_baselines.json` records the MSX and original vgm2tx802 revisions.
The original repository's edited knowledge, batch script and fixture documentation
are preserved, not reset or copied over. Private song/expected-output assets are
not imported. The initial production target is TX802; the legacy GM production
backend is not ported. General score MIDI remains available under Blueprint.

## Voice assignment is not voice generation

`tx802_voices.py` carries the original preset tables and deterministic velocity law.
`default` retains Internal assignments, including their existing table choices.
`name` uses the existing A/B named-preset table; `gm` and `opll` select the other
inherited TX802 mapping tables. These are TX802 table modes, not alternate MIDI
hardware targets. The prior CLI accepted name but its helper silently fell back;
this output resolves the requested table explicitly.

User patch keys are complete eight-byte hexadecimal content, not transient @v IDs.
Existing `bank/voice/label` JSON assignments win. Only emitted settling voices reserve
slots, in stable source lane/time order; zero-width or quantized-away setup snapshots
remain native evidence without consuming a hardware user slot. New nonzero patches receive free
I21..I64 slots. All-zero patches map A11 without consuming an Internal user slot.
Invalid assignments and slot exhaustion fail instead of clamping or replacing them.
Unknown native reset fields may be assumed zero with explicit diagnostics.

An existing edited `tracks/<stem>.user_voice_tx802.json` is consumed but not rewritten.
The complete proposed mapping remains in diagnostics when new assignments are needed.
`--voice-map` can supply an external existing mapping; malformed or missing explicit
files fail the target rather than silently falling back. Assignment JSON does not
install six-operator voices. No unverified bulk-voice SysEx is generated.

Legacy bank emission is CC0/CC32 followed by PC. A change of bank alone reissues PC;
controller/program caches are keyed by (port,channel). The exact legacy bank-select
mapping is not established by the Yamaha manual, so it remains a compatibility
assumption requiring hardware validation and suitable performance/receive setup.
Program Change on a performance-select channel can change the entire Performance;
configure instrument receive channels accordingly.

## Timing and source evidence

Source time is integer VGM samples at 44100 Hz. MIDI tempo/PPQ are target encoding:

`ticks_per_sample = ppq * 1000000 / (44100 * encoded_tempo_us)`

The ratio uses the actual encoded integer tempo, not a requested float approximation.
All source channels share the source origin. Absolute positions are projected with
Fractions; no 1/60 second source clock is introduced. Leading/trailing silence is
retained. The optional initialization lead applies to both melody and percussion,
unlike the old melody-only offset.

Each positive native gate has one Note On and one Note Off. Held pitch changes use
Pitch Bend; volume changes use CC11. Same-channel target gates use a joint cursor
so sub-tick gates remain positive and ordered. Off precedes setup and the next On
when ticks meet. Gate-local controls receive the same displacement. Quantized
internal collisions retain the final settling state and record approximation.

Event CSVs retain original source ID/device/channel/sample, target port/channel/track,
MIDI tick, bytes, event kind and displacement. Reports also retain gate starts/stops,
peak attenuation, attack velocity, delayed gate count, cumulative shift and duration
change. Original NativePerformance is not mutated. Source loops produce loopStart /
loopEnd markers; SMF has no universally executed repeat command, so the performance
is one traversal.

## Volume and pitch interpretation

The inherited nonlinear velocity table assumes TX802 velocity sensitivity 7 and is
an existing calibration, not newly proven physical equivalence. The old active
compute_cc11 function had the opposite direction from raw OPLL attenuation and made
VOL=0 silent. That bug is not inherited.

For each native gate, the loudest observed level selects the inherited velocity.
CC11 is normalized relative to that peak using the old inverse expression helper:
`round(127 * expression(current) / expression(peak))`, `expression(v)=127-8*v`.
Flat gates retain the calibrated onset velocity with CC11=127. Curved gates may have
a different attack velocity from the old sliced exporter; this avoids double
attenuation and expression saturation. This is a documented target approximation;
combined hardware loudness and timbre response still require audition.

Pitch uses native Hz, with A440=MIDI69. A single MIDI anchor and Pitch Bend preserve
the observed gate. Voice changes inside a gate emit bank/program updates without an
invented source attack, and are reported as hardware-dependent: the synth may
restart/change its envelope. Bend overflow fails in strict mode and clips with
explicit diagnostics under --force; the source curve remains intact.

The Yamaha TX802 Owner's Manual documents Range 0..12 semitones and Step 0 for
continuous bend (printed p.22; MIDI chart p.32). This implementation requires 1..12
and defaults to 12. The actual hardware voice must match. The manual does not
establish RPN0 setup or the old alleged 24-semitone parameter SysEx, so neither is
emitted as automatic setup. MIDI retains 14-bit bend data; hardware resolution may
be coarser. Primary document (Yamaha manual scan):
https://synthfool.com/docs/Yamaha/Yamaha%20TX-802%20Owners%20Manual.pdf

## Parts, ports and percussion

A source melodic lane maps to one TX802 tone generator, eight per unit. The default
is one unit. `--tx802-units 2` allocates the next eight lanes to SMF port 1, reusing
channels 1..8 there. Every channel track has port metadata before its channel events;
port numbers must be assigned to actual MIDI outputs in the player/DAW. The routing
CSV identifies device/channel, output port/channel/track and TG. Port metadata does
not itself select a Windows MIDI device or prove hardware routing.

More source lanes than the selected capacity fail unless --force permits reported
omission. No native source lane is discarded from the shared layer or Blueprint.
Other active source chips similarly require explicit partial projection. Silent
header declarations alone do not block OPLL output.

Rhythm families BD/SD/TOM/CYM/HH map by name to external RX21 or GM notes on port 0,
MIDI channel 10. GM/RX21 are distinct drum destinations, not TX802 FM drum patches.
Simultaneous instruments keep separate note events. Repeated identical drum keys shorten
the preceding gate at the next hit to keep its attack position and prevent a late
Note Off cutting it off. Only sub-tick collisions need a minimum-tick displacement. A missing observed
stop gets a short target gate and loss record. Internal drum volume curves remain
in native information; they do not send shared CC11 that would alter other drums.

## Publication and verification

`export_tx802.py` follows the export_mgs-style recursive layout with flat tracks per
input-relative folder. Its publication/ownership journal is adapted from the tested
MS2 exporter at 48bab9c. Edited artifacts and mappings are preserved. Owned stale
products are removed only for that exact input on forced regeneration. Output files
are excluded from beside-source recursive reruns. Source-product outcomes remain
separate in CSV/JSON and console warnings.

SMF encoding is self-contained Python. Full-status channel messages, tempo, track
names, port metadata, End of Track and SysEx framing are validated. A raw F0 packet
requires the SMF length field; it must not be copied as bare wire bytes. The generic
encoder supports correct framing, but the TX802 projection does not upload patches.

Synthetic tests cover gate/curve semantics, note-off ordering, subtick density,
port independence, bank-only changes, custom assignments, edited-template reuse and
source/target failure isolation. Public OPLL fixtures exercise the common parser.
File validation and plan equality do not establish TX802 playback or timbre accuracy.
The owner performs local_only regression and hardware audition. MIDI DIN bandwidth
and hardware processing delays are not modeled by the SMF event schedule.

## Opt-in calibration profile

The Python projection API accepts `preset_voice_map` to replace source-preset
assignments explicitly; missing entries fail rather than falling back silently.
`scripts/validate_tx802_calibration.py` uses it with the experimental 15-preset
DX7II CSV and emits independent source/target WAV evidence. The normal export CLI,
legacy preset assignments and NativePerformance are unchanged. See
[dx7ii_preset_calibration.md](dx7ii_preset_calibration.md).
