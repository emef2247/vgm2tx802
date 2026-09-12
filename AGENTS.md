# Project AGENTS.md

## What this repo is
- Convert YM2413/OPLL VGM into MIDI and related formats for hardware such as the Yamaha TX802.
- Main language: Python 3
- Primary working environment: WSL
- Goal: preserve chip/register behavior where practical, not just make cleaner MIDI.

## How to run
- Main script: `python src/vgm2midi.py` from the repo root, unless a later note says otherwise.
- If a requested command is not documented here, inspect the repo and report the actual command. Do not invent a package manager workflow.

## Layout
- `inputs/`: source VGM and similar input material, grouped by chip then set. Do not commit private game-derived files.
- `data/`: canonical lookup data the converter reads. OPLL preset tables live in `data/opll/presets/`.
- `outputs/`: generated artifacts only. Do not store source VGM here.
- `docs/project_knowledge.md`: design context. Read before changing conversion behavior.
- `field_notes/`: reusable lessons. Read only when relevant.
- `handoffs/current.md`: current restart state.
- `mistaken.md`: do-not-repeat rules.

## Private fixtures
- Private VGM/MIDI/MS2/WAV stay outside git.
- If `fixtures.local.toml` exists, local checks may use that path.
- If it does not exist, skip private-data playback and say so.
- Never commit private fixtures or paste their contents into docs, logs, or PRs.

## Conventions
- Follow existing style in the nearest files.
- Keep changes small.
- Do not add comments that restate the code.
- Prefer existing utilities over new helpers.
- Keep input material, lookup data, and generated outputs in separate trees.

## Do not
- Do not rewrite the whole project to introduce this workflow.
- Do not put long documentation into this file.
- Do not start a new feature while a handoff says the previous task is unfinished, unless the user asks to switch.
- Do not move files between `inputs/`, `data/`, and `outputs/` without updating callers.
- Do not simplify the segment representation just to make MIDI cleaner.
- Do not promote experimental mappings to specifications.

## Done means
- The requested change is implemented.
- Relevant checks were run, or the blocker is reported.
- `handoffs/current.md` is updated with what changed, what is unfinished, the next allowed action, and what must not happen next.

## When you learn something useful
- One-off discovery: `field_notes/YYYY-MM-DD_topic.md`
- Repeated failure: `mistaken.md`
- Always-on rule: only then add a short bullet here.

## Project knowledge
- Before changing conversion, volume mapping, segments, retrigger/legato, or target synth behavior, read `docs/project_knowledge.md`.
- OPLL VOL 0 is loudest, 15 is quietest.
- Linear OPLL VOL → MIDI velocity is a rejected approach.