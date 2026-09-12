#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TX802 Init Performance Builder
--------------------------------
Generates a list of SysEx messages that reset the TX802 Performance Edit Buffer
to the exact "Init Perf" state using ONLY PCED Parameter Change (0x03).

Outputs:
- init_perf.syx  (raw concatenated SysEx messages)
"""

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

    # TG1–TG8 EG Forced Damp (0x48–0x4F) = 0
    for tg in range(8):
        syx.append(pc(0x48 + tg, 0x00))

    # Recv Channel (0x08) = OMNI (0x10)
    syx.append(pc(0x08, 0x10))

    # Performance Name (0x60–0x6F)
    name = "Init perf".ljust(16)
    for i, ch in enumerate(name.encode("ascii")):
        syx.append(pc(0x60 + i, ch))

    return syx


def save_syx_file(filename, syx_list):
    """
    Save a list of SysEx messages (bytes) into a .syx file.
    Messages are concatenated back-to-back.
    """
    with open(filename, "wb") as f:
        for msg in syx_list:
            f.write(msg)
    print(f"Saved {len(syx_list)} SysEx messages to {filename}")


if __name__ == "__main__":
    syx_list = build_init_perf_sysex()

    print("Generated", len(syx_list), "SysEx messages for Init Perf.\n")
    for i, msg in enumerate(syx_list):
        print(f"{i:03d}: " + " ".join(f"{b:02X}" for b in msg))

    save_syx_file("init_perf.syx", syx_list)

