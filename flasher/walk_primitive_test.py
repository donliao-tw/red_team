"""Test the walk() primitive: walk 3 tiles each cardinal direction +
return, capturing each step so the user can verify accuracy.

Sequence:  N(3) → S(3) → E(3) → W(3)
The N/S and E/W pairs should land back near the start (since each
direction's "back" is the opposite direction's same-distance click).

If any direction over- or under-walks, the calibration constants in
``lineage_walk.py`` (PLAYER_XY, TILE_X, TILE_Y) need adjusting.
"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from board_client import BoardClient, BoardClientError
from human_mouse import HumanMouse
from lineage_walk import PLAYER_XY, TILE_X, TILE_Y, walk
from window_mapper import MouseAccelerationOff


N_TILES = 3
SEQ = ["N", "S", "E", "W"]


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

    print(f"Player @ {PLAYER_XY}, tile pitch X={TILE_X} Y={TILE_Y}")

    mouse = HumanMouse(client, hwnd)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    cap.grab_frame("Lineage").save("samples/wp_00_start.png")

    with MouseAccelerationOff():
        for i, direction in enumerate(SEQ, 1):
            print(f"[{i}/{len(SEQ)}] walk({direction}, {N_TILES})")
            walk(mouse, direction, N_TILES)
            cap.grab_frame("Lineage").save(
                f"samples/wp_{i:02d}_{direction}.png"
            )
        mouse.move_to_game(640, 700)

    client.close()
    print("\nDone — frames at samples/wp_*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
