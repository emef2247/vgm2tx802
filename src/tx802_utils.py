
# py/tx802.py
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List, Tuple

from .opll import (
    RHYTHM_CH_MAP,
)

from .midi_utils import (
    RHYTHM_TO_GM_NOTE,
    MidiBuilder,
    _vgm_tick_to_midi_tick,
    _opll_vol_to_velocity,
    _segment_to_midi_note,
    _tempo_meta_event,
    _track_name_meta_event
)


# voice -> list of (tick_start, tick_end, ch)
VoiceUsageMap = Dict[int, List[Tuple[int, int, int]]]

def build_voice_time_axis_table(segments_by_ch: dict[int, list]) -> VoiceUsageMap:
    """
    VOICE視点の時間軸テーブルの構築

    入力:
        segments_by_ch:
            ch -> [Segment, ...]
            Segment は少なくとも:
                - inst        : int  (OPLL voice / user voice)
                - tick_start  : int
                - tick_end    : int
                - keyon       : int (1 のとき発音)
    出力:
        voice_usage:
            voice -> [(tick_start, tick_end, ch), ...]
    """

    voice_usage: VoiceUsageMap = defaultdict(list)

    for ch, seg_list in segments_by_ch.items():
        for seg in seg_list:
            # 発音していないセグメントは無視
            if int(getattr(seg, "keyon", 0)) != 1:
                continue

            voice = int(getattr(seg, "inst"))
            tick_start = int(getattr(seg, "tick_start", 0))
            tick_end   = int(getattr(seg, "tick_end", tick_start))

            # tick_end < tick_start のような異常値はスキップ or 補正
            if tick_end <= tick_start:
                continue

            voice_usage[voice].append((tick_start, tick_end, ch))

    # 各VOICEごとに時間順にソートしておくと後の解析が楽
    for v in voice_usage:
        voice_usage[v].sort(key=lambda x: x[0])

    return voice_usage

def build_tick_ch_voice_grid(voice_usage, max_tick=None):
    """
    VOICE視点の usage から、tick × CH の 2D マップを作製

    出力:
        grid[tick][ch] = voice番号 or None
    """

    # まず最大tickを推定
    if max_tick is None:
        max_tick = 0
        for voice, entries in voice_usage.items():
            for ts, te, _ in entries:
                max_tick = max(max_tick, te)

    # grid[tick][ch] を None で初期化
    grid = []
    for t in range(max_tick + 1):
        grid.append([None] * 16)  # CH0〜CH15（OPLLは0〜8だが余裕を持たせる）

    # usage を埋める
    for voice, entries in voice_usage.items():
        for ts, te, ch in entries:
            for t in range(ts, te):
                if 0 <= ch < 16:
                    grid[t][ch] = voice

    return grid

def extract_voice_change_points(grid, num_ch=16):
    """
    tick × CH の 2D マップから、VOICE が変化した tick だけを抽出

    出力:
        List of (tick, [voice_ch0, voice_ch1, ...])
    """

    results = []
    last_row = [None] * num_ch

    for tick, row in enumerate(grid):
        # row は CH0〜CH15 の voice
        current = row[:num_ch]

        if current != last_row:
            # 変化があった tick だけ記録
            results.append((tick, current.copy()))
            last_row = current.copy()

    return results

def render_voice_change_table(change_points, num_ch=16):
    """
    差分表示の結果をテキスト表に整形
    """

    lines = []
    header = "tick | " + " ".join(f"CH{ch:02d}" for ch in range(num_ch))
    lines.append(header)
    lines.append("-" * len(header))

    for tick, row in change_points:
        cells = []
        for v in row:
            cells.append(f"{v if v is not None else '-':>3}")
        line = f"{tick:5d} | " + " ".join(cells)
        lines.append(line)

    return "\n".join(lines)

def detect_ch_voice_changes(segments_by_ch):
    """
    CH 内で Voice の入れ替えがあるかどうかを検出

    出力:
        ch_voice_changes[ch] = [
            (tick_start, tick_end, voice),
            ...
        ]
        ※ voice が変わるたびに新しい区間として記録
    """

    ch_voice_changes = {}

    for ch, seg_list in segments_by_ch.items():
        # keyon=1 のセグメントだけを対象にする
        active = [
            (seg.tick_start, seg.tick_end, seg.inst)
            for seg in seg_list
            if getattr(seg, "keyon", 0) == 1
        ]

        if not active:
            continue

        # tick_start でソート
        active.sort(key=lambda x: x[0])

        merged = []
        last_voice = None
        last_start = None
        last_end = None

        for ts, te, voice in active:
            if last_voice is None:
                # 最初の区間
                last_voice = voice
                last_start = ts
                last_end = te
                continue

            if voice == last_voice and ts <= last_end:
                # 同じ voice で連続している → 区間を伸ばす
                last_end = max(last_end, te)
            else:
                # voice が変わった → ひとつの区間として確定
                merged.append((last_start, last_end, last_voice))
                last_voice = voice
                last_start = ts
                last_end = te

        # 最後の区間を追加
        merged.append((last_start, last_end, last_voice))

        ch_voice_changes[ch] = merged

    return ch_voice_changes

def build_ch_to_tg_assignment(ch_voice_changes):
    """
    CH 内で Voice の入れ替えがない前提で CH → TG の固定割り当てを作成

    出力:
        ch_to_tg[ch] = tg番号 (0〜7)
        tg_to_voice[tg] = voice番号
    """

    ch_to_tg = {}
    tg_to_voice = {}

    tg = 0

    for ch in sorted(ch_voice_changes.keys()):
        entries = ch_voice_changes[ch]
        voices = sorted({v for (_, _, v) in entries})

        if len(voices) != 1:
            # Voice 入れ替えがある CH は固定割り当てできない
            continue

        voice = voices[0]

        if tg >= 8:
            raise RuntimeError("TG が足りません（固定割り当てできる CH が多すぎます）")

        ch_to_tg[ch] = tg
        tg_to_voice[tg] = voice

        tg += 1

    return ch_to_tg, tg_to_voice

def build_final_performance_from_tg_to_voice(tg_to_voice, default_voice=138):
    """
    tg_to_voice: {tg: voice} の辞書から、
    TX802 Performance 用の 8 要素リストを構築

    default_voice: 未使用 TG に割り当てるダミー Voice 番号。
                   ここでは 138 (空パッチ or 汎用) を想定。
    戻り値:
        perf: 長さ 8 のリスト [vTG1, vTG2, ..., vTG8]
    """
    perf = [default_voice] * 8
    for tg, voice in tg_to_voice.items():
        if 0 <= tg < 8:
            perf[tg] = voice
    return perf



def build_init_perf_sysex(device=0):
    """
    Return a list of SysEx messages (bytes) that reset the TX802 Performance Edit Buffer
    to the exact Init Perf state using only PCED Parameter Change (0x03).
    """

    syx = []

    def pc(offset, value):
        # PCED Parameter Change: F0 43 1n 5E 03 aa bb F7
        return bytes([0xF0, 0x43, 0x10 | device, 0x5E, 0x03, offset, value, 0xF7])

    # TG1–TG8 Voice (0x00–0x07)
    for tg in range(8):
        syx.append(pc(0x00 + tg, tg))

    # TG1–TG8 Detune (0x18–0x1F) = 7
    for tg in range(8):
        syx.append(pc(0x18 + tg, 0x07))

    # TG1–TG8 Volume (0x20–0x27) = 0x5A
    for tg in range(8):
        syx.append(pc(0x20 + tg, 0x5A))

    # TG1–TG8 Output Assign (0x28–0x2F) = 3 (I+II)
    for tg in range(8):
        syx.append(pc(0x28 + tg, 0x03))

    # TG1–TG8 Note Low (0x30–0x37) = 0
    for tg in range(8):
        syx.append(pc(0x30 + tg, 0x00))

    # TG1–TG8 Note High (0x38–0x3F) = 127
    for tg in range(8):
        syx.append(pc(0x38 + tg, 0x7F))

    # TG1–TG8 Note Shift (0x40–0x47) = 0x18
    for tg in range(8):
        syx.append(pc(0x40 + tg, 0x18))

    # TG1–TG8 EG Damp (0x48–0x4F) = 0
    for tg in range(8):
        syx.append(pc(0x48 + tg, 0x00))

    # Recv Channel (0x08) = OMNI (0x10)
    syx.append(pc(0x08, 0x10))

    # Performance Name (0x60–0x6F)
    name = "Init perf".ljust(16)
    for i, ch in enumerate(name.encode("ascii")):
        syx.append(pc(0x60 + i, ch))

    return syx
