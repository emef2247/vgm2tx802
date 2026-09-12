import sys
from mido import MidiFile

mid = MidiFile(sys.argv[1])
abs_tick = 0
for i, tr in enumerate(mid.tracks):
    abs_tick = 0
    for msg in tr:
        abs_tick += msg.time
        if msg.type in ("program_change", "note_on", "note_off", "pitchwheel", "control_change"):
            ch = getattr(msg, "channel", None)
            if msg.type == "control_change" and msg.control not in (0, 32, 6, 38, 64, 100, 101, 121, 123, 11):
                continue
            print(f"track={i}\ttick={abs_tick}\ttype={msg.type}\tch={ch}\t{msg}")

