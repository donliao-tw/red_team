"""Probe Ctrl+M timing.

The key_combo wrapper does KD-K-KU which firmware-side processes the K
(press+release) atomically — total Ctrl+M may finish in <2 ms, which
some games miss. This script does manual KD/KU with explicit holds so
the OS sees Ctrl held for ~150 ms while M presses + releases inside.
"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from board_client import BoardClient, BoardClientError
from minimap import count_arrow_pixels


def main() -> int:
    user32 = ctypes.windll.user32
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        print("ERROR: Lineage window not found", file=sys.stderr)
        return 1
    try:
        client = BoardClient.auto_detect()
    except BoardClientError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)

    print("Initial red-arrow px:", count_arrow_pixels(cap.grab_frame("Lineage")))

    print("Sending Ctrl+M with 300 ms Ctrl pre-hold (per user's habit)…")
    client.key_down("ctrl")
    time.sleep(0.35)               # let Ctrl settle for >0.3 s
    client.key_down("m")
    time.sleep(0.08)
    client.key_up("m")
    time.sleep(0.08)
    client.key_up("ctrl")
    print("Sent. Waiting 2 s for render…")
    time.sleep(2)

    cnt = count_arrow_pixels(cap.grab_frame("Lineage"))
    print(f"After: red-arrow px = {cnt}")

    client.close()
    return 0 if cnt > 20 else 1


if __name__ == "__main__":
    sys.exit(main())
