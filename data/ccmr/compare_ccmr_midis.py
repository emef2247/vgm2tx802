#!/usr/bin/env python3
"""Compare TX802 default/rx21 MIDI pairs against Domino CCMR outputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_BASE_SUFFIX = "_tx802_default_rx21.mid"
_DOMINO_SUFFIX = "_tx802_default_rx21.domino.mid"
_TARGET_CC = [0, 7, 10, 11, 32, 64, 121, 123]


@dataclass(frozen=True)
class MidiHeader:
    fmt: int
    ntrks: int
    division: int


@dataclass
class MidiEvent:
    track: int
    abs_tick: int
    delta: int
    status: int
    channel: int | None
    data: tuple[int, ...]
    kind: str
    meta_type: int | None = None
    running_status_used: bool = False


def _read_varlen(buf: bytes, pos: int) -> tuple[int, int]:
    value = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated variable-length quantity")
        b = buf[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if (b & 0x80) == 0:
            return value, pos


def _msg_data_len(status: int) -> int:
    hi = status & 0xF0
    if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
        return 2
    if hi in (0xC0, 0xD0):
        return 1
    raise ValueError(f"unsupported status 0x{status:02X}")


def parse_midi(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if data[:4] != b"MThd":
        raise ValueError(f"{path}: missing MThd")
    if len(data) < 14:
        raise ValueError(f"{path}: truncated MIDI header")
    header_len = int.from_bytes(data[4:8], "big")
    if header_len < 6:
        raise ValueError(f"{path}: invalid MThd length {header_len}")
    if len(data) < 8 + header_len:
        raise ValueError(f"{path}: truncated MThd payload")
    header = MidiHeader(
        fmt=int.from_bytes(data[8:10], "big"),
        ntrks=int.from_bytes(data[10:12], "big"),
        division=int.from_bytes(data[12:14], "big"),
    )

    pos = 8 + header_len
    tracks: list[list[MidiEvent]] = []
    track_running_status_used: list[bool] = []
    all_events: list[MidiEvent] = []

    for track_index in range(header.ntrks):
        if pos + 8 > len(data):
            raise ValueError(f"{path}: truncated track header {track_index}")
        if data[pos:pos + 4] != b"MTrk":
            raise ValueError(f"{path}: missing MTrk at track {track_index}")
        pos += 4
        track_len = int.from_bytes(data[pos:pos + 4], "big")
        pos += 4
        if pos + track_len > len(data):
            raise ValueError(f"{path}: truncated track payload {track_index}")
        trk = data[pos:pos + track_len]
        pos += track_len

        tpos = 0
        abs_tick = 0
        running_status: int | None = None
        running_used = False
        events: list[MidiEvent] = []

        while tpos < len(trk):
            delta, tpos = _read_varlen(trk, tpos)
            abs_tick += delta

            if tpos >= len(trk):
                raise ValueError(f"{path}: truncated event body after delta-time")
            first = trk[tpos]
            used_running = False
            if first < 0x80:
                if running_status is None or running_status >= 0xF0:
                    raise ValueError(f"{path}: running status without previous status")
                status = running_status
                used_running = True
                running_used = True
            else:
                status = first
                tpos += 1
                if status < 0xF0:
                    running_status = status
                else:
                    running_status = None

            if status == 0xFF:
                if tpos >= len(trk):
                    raise ValueError(f"{path}: truncated meta event")
                meta_type = trk[tpos]
                tpos += 1
                length, tpos = _read_varlen(trk, tpos)
                if tpos + length > len(trk):
                    raise ValueError(f"{path}: truncated meta payload")
                payload = tuple(trk[tpos:tpos + length])
                tpos += length
                ev = MidiEvent(
                    track=track_index,
                    abs_tick=abs_tick,
                    delta=delta,
                    status=status,
                    channel=None,
                    data=payload,
                    kind="meta",
                    meta_type=meta_type,
                    running_status_used=used_running,
                )
            elif status in (0xF0, 0xF7):
                length, tpos = _read_varlen(trk, tpos)
                if tpos + length > len(trk):
                    raise ValueError(f"{path}: truncated sysex payload")
                payload = tuple(trk[tpos:tpos + length])
                tpos += length
                ev = MidiEvent(
                    track=track_index,
                    abs_tick=abs_tick,
                    delta=delta,
                    status=status,
                    channel=None,
                    data=payload,
                    kind="sysex",
                    running_status_used=used_running,
                )
            else:
                length = _msg_data_len(status)
                if tpos + length > len(trk):
                    raise ValueError(f"{path}: truncated channel message")
                msg = tuple(trk[tpos:tpos + length])
                tpos += length
                hi = status & 0xF0
                ch = status & 0x0F
                kind = {
                    0x80: "note_off",
                    0x90: "note_on",
                    0xA0: "poly_aftertouch",
                    0xB0: "control_change",
                    0xC0: "program_change",
                    0xD0: "channel_aftertouch",
                    0xE0: "pitch_bend",
                }.get(hi, "channel")
                ev = MidiEvent(
                    track=track_index,
                    abs_tick=abs_tick,
                    delta=delta,
                    status=status,
                    channel=ch,
                    data=msg,
                    kind=kind,
                    running_status_used=used_running,
                )
            events.append(ev)
            all_events.append(ev)

        tracks.append(events)
        track_running_status_used.append(running_used)

    return {
        "path": str(path),
        "header": header,
        "tracks": tracks,
        "events": all_events,
        "running_status_any": any(track_running_status_used),
        "running_status_tracks": track_running_status_used,
    }


def _event_key_normalized(ev: MidiEvent) -> tuple[Any, ...]:
    if ev.kind == "meta":
        return ("meta", ev.abs_tick, ev.meta_type, ev.data)
    if ev.kind == "sysex":
        return ("sysex", ev.abs_tick, ev.status, ev.data)
    return ("ch", ev.abs_tick, ev.status, ev.channel, ev.data)


def _event_key_with_track(ev: MidiEvent) -> tuple[Any, ...]:
    return (ev.track,) + _event_key_normalized(ev)


def _channel_events(parsed: dict[str, Any]) -> list[MidiEvent]:
    return [ev for ev in parsed["events"] if ev.kind not in ("meta", "sysex")]


def _note_stats(events: list[MidiEvent]) -> dict[str, Any]:
    active: dict[tuple[int, int], deque[int]] = defaultdict(deque)
    lengths: list[int] = []
    onsets: set[int] = set()
    by_ch_count: Counter[int] = Counter()
    timeline: list[tuple[int, int, int]] = []

    for ev in events:
        if ev.channel is None:
            continue
        by_ch_count[ev.channel] += 1
        hi = ev.status & 0xF0
        if hi == 0x90 and len(ev.data) >= 2 and ev.data[1] > 0:
            note = ev.data[0]
            active[(ev.channel, note)].append(ev.abs_tick)
            onsets.add(ev.abs_tick)
            timeline.append((ev.abs_tick, 1, ev.channel))
        elif hi == 0x80 or (hi == 0x90 and len(ev.data) >= 2 and ev.data[1] == 0):
            note = ev.data[0]
            stack = active.get((ev.channel, note))
            if stack:
                start = stack.popleft()
                lengths.append(ev.abs_tick - start)
            timeline.append((ev.abs_tick, 0, ev.channel))

    max_poly_by_ch: dict[int, int] = defaultdict(int)
    cur_poly_by_ch: dict[int, int] = defaultdict(int)
    for tick, is_on, ch in sorted(timeline, key=lambda x: (x[0], x[1])):
        if is_on:
            cur_poly_by_ch[ch] += 1
            max_poly_by_ch[ch] = max(max_poly_by_ch[ch], cur_poly_by_ch[ch])
        else:
            cur_poly_by_ch[ch] = max(0, cur_poly_by_ch[ch] - 1)

    return {
        "note_count": sum(1 for ev in events if (ev.status & 0xF0) == 0x90 and len(ev.data) >= 2 and ev.data[1] > 0),
        "note_lengths": {
            "count": len(lengths),
            "min": min(lengths) if lengths else None,
            "max": max(lengths) if lengths else None,
            "avg": (sum(lengths) / len(lengths)) if lengths else None,
        },
        "onset_count": len(onsets),
        "max_polyphony_by_channel": {str(k): v for k, v in sorted(max_poly_by_ch.items())},
        "event_density_by_channel": {str(k): v for k, v in sorted(by_ch_count.items())},
    }


def _cc_counter(events: list[MidiEvent]) -> Counter[tuple[int, int, int]]:
    c: Counter[tuple[int, int, int]] = Counter()
    for ev in events:
        if ev.kind == "control_change" and ev.channel is not None and len(ev.data) >= 2:
            c[(ev.channel, ev.data[0], ev.data[1])] += 1
    return c


def _target_cc_summary(counter: Counter[tuple[int, int, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ch, cc, val in sorted(counter):
        if cc in _TARGET_CC:
            out[f"ch{ch:02d}.cc{cc:03d}.v{val:03d}"] = counter[(ch, cc, val)]
    return out


def compare_pair(
    base_path: Path,
    domino_path: Path,
    rhythm_channels: set[int] | None = None,
) -> dict[str, Any]:
    base = parse_midi(base_path)
    dom = parse_midi(domino_path)

    base_events = base["events"]
    dom_events = dom["events"]
    base_ch_events = _channel_events(base)
    dom_ch_events = _channel_events(dom)

    base_norm = Counter(_event_key_normalized(ev) for ev in base_events)
    dom_norm = Counter(_event_key_normalized(ev) for ev in dom_events)
    base_ch_norm = Counter(_event_key_normalized(ev) for ev in base_ch_events)
    dom_ch_norm = Counter(_event_key_normalized(ev) for ev in dom_ch_events)
    base_track = Counter(_event_key_with_track(ev) for ev in base_events)
    dom_track = Counter(_event_key_with_track(ev) for ev in dom_events)

    added_norm = dom_norm - base_norm
    removed_norm = base_norm - dom_norm
    added_ch_norm = dom_ch_norm - base_ch_norm
    removed_ch_norm = base_ch_norm - dom_ch_norm
    added_track = dom_track - base_track
    removed_track = base_track - dom_track

    base_tracks_by_norm: dict[tuple[Any, ...], Counter[int]] = defaultdict(Counter)
    dom_tracks_by_norm: dict[tuple[Any, ...], Counter[int]] = defaultdict(Counter)
    for ev in base_events:
        base_tracks_by_norm[_event_key_normalized(ev)][ev.track] += 1
    for ev in dom_events:
        dom_tracks_by_norm[_event_key_normalized(ev)][ev.track] += 1

    move_count = 0
    for key in set(base_norm.keys()) & set(dom_norm.keys()):
        expected = min(base_norm[key], dom_norm[key])
        if expected == 0:
            continue
        base_track_dist = base_tracks_by_norm[key]
        dom_track_dist = dom_tracks_by_norm[key]
        stable = sum((base_track_dist & dom_track_dist).values())
        move_count += max(0, expected - stable)

    base_cc = _cc_counter(base_ch_events)
    dom_cc = _cc_counter(dom_ch_events)

    if rhythm_channels is None:
        rhythm_channels = {9}
    all_channels = {
        ev.channel
        for ev in (base_ch_events + dom_ch_events)
        if ev.channel is not None
    }
    rhythm_chs = set(rhythm_channels) & all_channels
    melody_chs = all_channels - rhythm_chs

    def _group_counter(counter: Counter[tuple[int, int, int]], channels: set[int]) -> Counter[tuple[int, int, int]]:
        out: Counter[tuple[int, int, int]] = Counter()
        for (ch, cc, val), n in counter.items():
            if ch in channels:
                out[(ch, cc, val)] = n
        return out

    return {
        "base_file": str(base_path),
        "domino_file": str(domino_path),
        "header": {
            "base": base["header"].__dict__,
            "domino": dom["header"].__dict__,
            "equal": base["header"] == dom["header"],
        },
        "running_status": {
            "base_any": base["running_status_any"],
            "domino_any": dom["running_status_any"],
            "base_tracks": base["running_status_tracks"],
            "domino_tracks": dom["running_status_tracks"],
        },
        "event_counts": {
            "base_total": len(base_events),
            "domino_total": len(dom_events),
            "base_channel": len(base_ch_events),
            "domino_channel": len(dom_ch_events),
            "base_meta": sum(1 for ev in base_events if ev.kind == "meta"),
            "domino_meta": sum(1 for ev in dom_events if ev.kind == "meta"),
        },
        "normalized_comparison": {
            "equal_ignoring_track_delta": not added_norm and not removed_norm,
            "added_events": int(sum(added_norm.values())),
            "removed_events": int(sum(removed_norm.values())),
            "moved_track_only_events": int(move_count),
        },
        "channel_normalized_comparison": {
            "equal_ignoring_track_delta": not added_ch_norm and not removed_ch_norm,
            "added_events": int(sum(added_ch_norm.values())),
            "removed_events": int(sum(removed_ch_norm.values())),
        },
        "track_sensitive_comparison": {
            "added_events": int(sum(added_track.values())),
            "removed_events": int(sum(removed_track.values())),
        },
        "cc_differences": {
            "added": _target_cc_summary(dom_cc - base_cc),
            "removed": _target_cc_summary(base_cc - dom_cc),
            "base_target_cc": _target_cc_summary(base_cc),
            "domino_target_cc": _target_cc_summary(dom_cc),
            "melody_added": _target_cc_summary(_group_counter(dom_cc, melody_chs) - _group_counter(base_cc, melody_chs)),
            "melody_removed": _target_cc_summary(_group_counter(base_cc, melody_chs) - _group_counter(dom_cc, melody_chs)),
            "rhythm_added": _target_cc_summary(_group_counter(dom_cc, rhythm_chs) - _group_counter(base_cc, rhythm_chs)),
            "rhythm_removed": _target_cc_summary(_group_counter(base_cc, rhythm_chs) - _group_counter(dom_cc, rhythm_chs)),
        },
        "analysis_channels": {
            "rhythm_channels": sorted(rhythm_chs),
            "melody_channels": sorted(melody_chs),
        },
        "note_stats": {
            "base": _note_stats(base_ch_events),
            "domino": _note_stats(dom_ch_events),
        },
    }


def discover_pairs(root: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for p in sorted(root.rglob(f"*{_BASE_SUFFIX}")):
        if str(p).endswith(_DOMINO_SUFFIX):
            continue
        domino = p.with_name(p.name.replace(_BASE_SUFFIX, _DOMINO_SUFFIX))
        if domino.exists():
            pairs.append((p, domino))
    return pairs


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pair_count": len(results),
        "all_normalized_equal": all(r["normalized_comparison"]["equal_ignoring_track_delta"] for r in results),
        "headers_equal_count": sum(1 for r in results if r["header"]["equal"]),
        "running_status_changed_pairs": sum(
            1
            for r in results
            if r["running_status"]["base_any"] != r["running_status"]["domino_any"]
        ),
    }


def _write_markdown(output: Path, root: Path, pairs: list[tuple[Path, Path]], results: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    lines.append("# CCMR MIDI Difference Analysis")
    lines.append("")
    lines.append(f"- Root: `{root}`")
    lines.append(f"- Pair count: **{len(pairs)}**")
    lines.append("")
    lines.append("## Pair list")
    lines.append("")
    for base, dom in pairs:
        lines.append(f"- `{base.relative_to(root)}` ↔ `{dom.relative_to(root)}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    agg = summarize(results)
    lines.append(f"- all_normalized_equal: **{agg['all_normalized_equal']}**")
    lines.append(f"- headers_equal_count: **{agg['headers_equal_count']} / {agg['pair_count']}**")
    lines.append(f"- running_status_changed_pairs: **{agg['running_status_changed_pairs']}**")
    lines.append("")
    lines.append("## Per-pair highlights")
    lines.append("")
    for r in results:
        lines.append(f"### {Path(r['base_file']).name}")
        lines.append("")
        h0 = r["header"]["base"]
        h1 = r["header"]["domino"]
        lines.append(f"- Header: base fmt={h0['fmt']},ntrks={h0['ntrks']},div={h0['division']} / "
                     f"domino fmt={h1['fmt']},ntrks={h1['ntrks']},div={h1['division']}")
        lines.append(f"- Normalized equal (ignore track+delta): **{r['normalized_comparison']['equal_ignoring_track_delta']}**")
        lines.append(f"- Moved-track-only events: **{r['normalized_comparison']['moved_track_only_events']}**")
        lines.append(f"- Rhythm CC added: `{r['cc_differences']['rhythm_added']}`")
        lines.append(f"- Rhythm CC removed: `{r['cc_differences']['rhythm_removed']}`")
        lines.append("")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare *_tx802_default_rx21.mid and *.domino.mid pairs")
    parser.add_argument("root", nargs="?", default=".", help="Search root directory")
    parser.add_argument(
        "--rhythm-channels",
        default="9",
        help="Comma-separated rhythm-channel list used for melody/rhythm split (default: 9)",
    )
    parser.add_argument("--json-out", default=None, help="Write full result JSON to file")
    parser.add_argument("--md-out", default=None, help="Write short markdown summary to file")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rhythm_channels = {
        int(ch)
        for ch in args.rhythm_channels.split(",")
        if ch.strip() != ""
    }
    pairs = discover_pairs(root)
    results = [compare_pair(base, dom, rhythm_channels=rhythm_channels) for base, dom in pairs]
    payload = {
        "root": str(root),
        "rhythm_channels": sorted(rhythm_channels),
        "pairs": results,
        "summary": summarize(results),
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.json_out:
        out = Path(args.json_out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.md_out:
        _write_markdown(Path(args.md_out).resolve(), root, pairs, results)


if __name__ == "__main__":
    main()
