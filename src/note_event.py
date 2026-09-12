from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

try:
    from .midi_utils import _segment_to_midi_note, _vgm_tick_to_midi_tick
except ImportError:
    from midi_utils import _segment_to_midi_note, _vgm_tick_to_midi_tick


@dataclass(frozen=True)
class NoteEvent:
    ch: int
    start_tick: int
    end_tick: int
    note: int | None
    inst: int
    at_token: str
    is_portamento: int
    is_drum: bool
    drum_name: str | None
    drum_on: int
    scale: int | str  # raw scale value from segment (semitone int or legacy token)
    velocity_source: int
    segment: object


def build_melody_note_events(segments, ch, bpm, ppq) -> list[NoteEvent]:
    events: list[NoteEvent] = []

    for seg in segments:
        inst = int(getattr(seg, "inst", 0))
        keyon = int(getattr(seg, "keyon", 0))

        # --- VoiceChange: inst=0 & keyon=0 をイベントとして残す ---
        if inst == 0 and keyon == 0:
            events.append(
                NoteEvent(
                    ch=ch,
                    start_tick=_vgm_tick_to_midi_tick(getattr(seg, "tick_start", 0), bpm, ppq),
                    end_tick=_vgm_tick_to_midi_tick(getattr(seg, "tick_end", 0), bpm, ppq),
                    note=None,
                    inst=inst,
                    at_token=(getattr(seg, "at_token", "") or ""),
                    is_portamento=0,
                    is_drum=False,
                    drum_name=None,
                    drum_on=0,
                    scale=getattr(seg, "scale", 0),
                    velocity_source=int(getattr(seg, "vol", 15)),
                    segment=seg,
                )
            )
            continue

        # --- ここからは keyon=1 のノートだけ ---
        if keyon != 1:
            continue

        start_tick = _vgm_tick_to_midi_tick(getattr(seg, "tick_start", 0), bpm, ppq)
        end_tick = _vgm_tick_to_midi_tick(getattr(seg, "tick_end", 0), bpm, ppq)
        if end_tick <= start_tick:
            continue

        events.append(
            NoteEvent(
                ch=ch,
                start_tick=start_tick,
                end_tick=end_tick,
                note=_segment_to_midi_note(seg),
                inst=inst,
                at_token=(getattr(seg, "at_token", "") or ""),
                is_portamento=int(getattr(seg, "is_portamento", 0)),
                is_drum=False,
                drum_name=None,
                drum_on=0,
                scale=getattr(seg, "scale", 0),
                velocity_source=int(getattr(seg, "vol", 15)),
                segment=seg,
            )
        )

    return events


def build_drum_note_events(
    segments: Iterable[Any],
    ch: int,
    bpm: int,
    ppq: int,
    drum_note_mapper: Callable[[str, Any], int],
    use_channel_drum: bool = False,
) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    drum_name_by_ch = {
        9: "bd",
        10: "sd",
        11: "tom",
        12: "tc",
        13: "hh",
        14: "cym",
    }

    for seg in segments:
        if int(getattr(seg, "keyon", 0)) != 1:
            continue

        start_tick = _vgm_tick_to_midi_tick(getattr(seg, "tick_start", 0), bpm, ppq)
        end_tick = _vgm_tick_to_midi_tick(getattr(seg, "tick_end", 0), bpm, ppq)
        if end_tick <= start_tick:
            continue

        scale = getattr(seg, "scale", 0)
        drum_names: list[str]
        if use_channel_drum:
            seg_ch = int(getattr(seg, "ch", ch))
            drum_name = drum_name_by_ch.get(seg_ch)
            if drum_name is None:
                continue
            if int(getattr(seg, drum_name, 0)) != 1:
                continue
            drum_names = [drum_name]
        else:
            drum_names = [
                drum_name
                for drum_name in ("bd", "sd", "tom", "tc", "hh", "cym")
                if int(getattr(seg, drum_name, 0)) == 1
            ]

        for drum_name in drum_names:
            events.append(
                NoteEvent(
                    ch=ch,
                    start_tick=start_tick,
                    end_tick=end_tick,
                    note=drum_note_mapper(drum_name, scale),
                    inst=int(getattr(seg, "inst", 0)),
                    at_token=(getattr(seg, "at_token", "") or ""),
                    is_portamento=0,
                    is_drum=True,
                    drum_name=drum_name,
                    drum_on=1,
                    scale=scale,
                    velocity_source=int(getattr(seg, "vol", 15)),
                    segment=seg,
                )
            )

    return events
