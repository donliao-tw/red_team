"""Calibrate walk for the four diagonal directions: NE, NW, SE, SW.

Now uses the proper isometric NE-axis (1 tile NE = +TILE_X/2 right,
-TILE_Y/2 up, i.e. -27.5° from horizontal in 2:1 diamond) rather than
a 45° screen diagonal. The previous attempt clicked at +71/-71 from a
body-centre anchor, which fell between the NE-axis and N-axis and
made the character walk "north 2 then up-left" (game resolves the
ambiguous click as nearest-axis-then-correct).

Walks 5 tiles each diagonal so the displacement is large enough to
read on the silver-arrow reference object.
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
from lineage_walk import PLAYER_XY, walk
from window_mapper import MouseAccelerationOff


N_TILES = 5
WAIT_S = 6.0

DIAGS = ["NE", "NW", "SE", "SW"]


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

    mouse = HumanMouse(client, hwnd)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    cap.grab_frame("Lineage").save("samples/diag_00_start.png")

    with MouseAccelerationOff():
        for i, direction in enumerate(DIAGS, 1):
            print(f"[{i}/4] walk({direction}, {N_TILES})")
            walk(mouse, direction, N_TILES, settle_s=1.0)
            cap.grab_frame("Lineage").save(
                f"samples/diag_{i:02d}_{direction}.png"
            )
        mouse.move_to_game(640, 700)

    client.close()
    print("\nDone — frames at samples/diag_*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
