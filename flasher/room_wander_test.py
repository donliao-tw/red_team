"""Wander a small room without hitting walls, using minimap-driven
walkability detection.

Each loop iteration:
  1. capture a frame
  2. find the player arrow on the minimap
  3. compute 8-direction walkability (floor brightness ≥ threshold)
  4. pick a random walkable direction (avoiding immediate backtrack)
  5. walk 2 tiles that direction
  6. settle, repeat

Stops when no direction is walkable (truly stuck) or after N steps.
"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from board_client import BoardClient, BoardClientError, jitter_sleep
from human_mouse import HumanMouse
from lineage_walk import walk_hold
from minimap_nav import find_arrow, pick_random_walkable, walkability_8
from window_mapper import MouseAccelerationOff


N_STEPS = 10
HOLD_RANGE = (0.8, 2.5)  # uniform random per step


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

    print(f"Board: {client.port}, {client.version()}")
    mouse = HumanMouse(client, hwnd)
    user32.SetForegroundWindow(hwnd)
    jitter_sleep(0.3)

    last_dir: str | None = None
    with MouseAccelerationOff():
        for i in range(1, N_STEPS + 1):
            img = cap.grab_frame("Lineage")
            arrow = find_arrow(img)
            if arrow is None:
                print(f"[{i:02d}] no arrow — minimap closed?")
                break
            walkable = walkability_8(img)
            walk_str = " ".join(d for d, ok in walkable.items() if ok)
            chosen = pick_random_walkable(walkable, avoid=last_dir)
            actual = walk_hold(mouse, chosen, HOLD_RANGE) if chosen else 0
            print(f"[{i:02d}] arrow={arrow}  walkable=[{walk_str}]  → {chosen}  hold={actual:.2f}s")
            if chosen is None:
                print("  stuck (no walkable direction)")
                break
            last_dir = chosen
            # Save a snapshot of the run for review
            img.save(f"samples/wander_{i:02d}.png")

        # Park cursor away
        mouse.move_to_game(640, 700)

    client.close()
    print("\nDone — frames at samples/wander_*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
