"""Calibrate walk for all four cardinal directions.

Single-fire each, with a long settle between, so we can clearly see
each direction's tile pitch without click-stacking interference.

Sequence: N → wait 5 → S → wait 5 → E → wait 5 → W → wait 5.

Captures one frame per step + an annotated start frame for reference.
After each direction the player will have walked ~5-6 tiles in that
direction; the next direction is fired from the *new* player screen
position (which is unchanged — player stays at game (640, 380)).
"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw

import capture as cap
from board_client import BoardClient, BoardClientError
from human_mouse import HumanMouse
from window_mapper import MouseAccelerationOff


PLAYER_XY = (640, 380)
STEP_PX = 100
WAIT_S = 5.0


SEQ = [
    ("N", (0, -STEP_PX)),
    ("S", (0, +STEP_PX)),
    ("E", (+STEP_PX, 0)),
    ("W", (-STEP_PX, 0)),
]


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

    img0 = cap.grab_frame("Lineage")
    img0.save("samples/walk4_00_start.png")

    with MouseAccelerationOff():
        for i, (label, (dx, dy)) in enumerate(SEQ, 1):
            tgt = (PLAYER_XY[0] + dx, PLAYER_XY[1] + dy)
            print(f"[{i}/4] {label}: click game {tgt}")
            mouse.click_at_game(*tgt)
            print(f"  waiting {WAIT_S}s…")
            time.sleep(WAIT_S)
            cap.grab_frame("Lineage").save(f"samples/walk4_{i:02d}_{label}.png")

        mouse.move_to_game(640, 700)

    client.close()

    # Annotate start with the four click targets
    bw = img0.copy()
    d = ImageDraw.Draw(bw)
    px_pl = (PLAYER_XY[0] + 1, PLAYER_XY[1] + 31)
    d.ellipse((px_pl[0]-7, px_pl[1]-7, px_pl[0]+7, px_pl[1]+7),
              outline="cyan", width=3)
    d.text((px_pl[0]+10, px_pl[1]-8), "PLAYER", fill="cyan")
    for label, (dx, dy) in SEQ:
        tx, ty = PLAYER_XY[0] + dx + 1, PLAYER_XY[1] + dy + 31
        d.ellipse((tx-6, ty-6, tx+6, ty+6), outline="yellow", width=3)
        d.text((tx+10, ty-8), label, fill="yellow")
    bw.save("samples/walk4_00_start_annotated.png")

    print("\nDone — frames in samples/walk4_*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
