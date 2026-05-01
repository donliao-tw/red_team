"""Live demo / integration test for HumanMouse.

Connects to the hid_mouse Arduino, finds the Lineage window, and
sweeps the cursor through a few game-relative points along bezier
curves so you can eyeball the trajectory.

WARNING: this moves your cursor in real time. Make sure no critical
work is in progress before running.

Usage:
    python flasher/human_mouse_demo.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from human_mouse import HumanMouse
from mouse_client import MouseClient


def main() -> int:
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        print("Lineage window not found", file=sys.stderr)
        return 1
    size = cap.get_client_size(hwnd)
    print(f"Lineage hwnd={hwnd} client={size}")

    print("Connecting to hid_mouse Arduino...")
    try:
        client = MouseClient.auto_detect()
    except Exception as e:  # noqa: BLE001
        print(f"  FAILED: {e}", file=sys.stderr)
        return 1
    print(f"  on {client.port}")

    mouse = HumanMouse(client, hwnd)

    # Walk a small loop of game-coord targets so you can watch the
    # arcs and timing. Coordinates picked to be inside the 1280×960
    # client area — visible regions, not corners.
    targets = [
        (200, 200, "top-left area"),
        (1000, 200, "top-right area"),
        (1000, 760, "bottom-right area"),
        (200, 760, "bottom-left area"),
        (640, 480, "centre"),
    ]

    for gx, gy, label in targets:
        print(f"  → ({gx}, {gy})  [{label}]")
        t0 = time.perf_counter()
        mouse.move_to_game(gx, gy)
        dt = (time.perf_counter() - t0) * 1000
        print(f"     done in {dt:.0f} ms")
        time.sleep(0.3)

    # And a hover demo at the supposed gold-tooltip area (placeholder —
    # adjust to where the user opens the inventory).
    print("\nHover demo at (640, 480) for 1 s")
    mouse.hover_at_game(640, 480, hover_ms=1000)

    client.close()
    print("\nDone — eyeball the path. Was each arc smooth + slightly curved?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
