"""Diagnostic — move the cursor to several game coordinates and
print the Δ between target and actual landing for each. Doesn't
need any specific game UI state. Quickly tells us whether the
bezier+settle pipeline lands within ±1 px under the user's current
mouse / monitor setup.
"""
from __future__ import annotations

import ctypes
import io
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import window_mapper  # noqa: F401
import capture as cap
from board_client import BoardClient, BoardClientError, jitter_sleep
from human_mouse import HumanMouse, BEZIER_AIM_FRACTION
from window_mapper import (
    MouseAccelerationOff, client_to_screen, get_cursor_screen_pos,
)

TARGETS = [
    (640, 480),     # screen centre-ish
    (100, 100),     # top-left
    (1100, 100),    # top-right
    (100, 800),     # bottom-left
    (1100, 800),    # bottom-right
    (640, 480),     # back to centre
    (90, 70),       # 肉 row position
    (90, 530),      # bottom-of-shop-list row
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
    print(f"Board: {client.port}, {client.version()}")
    print(f"BEZIER_AIM_FRACTION = {BEZIER_AIM_FRACTION}")

    mouse = HumanMouse(client, hwnd)
    user32.SetForegroundWindow(hwnd)
    jitter_sleep(0.3)

    miss_total = 0
    miss_count = 0

    with MouseAccelerationOff():
        for i, (gx, gy) in enumerate(TARGETS, 1):
            target_screen = client_to_screen(hwnd, gx, gy)
            before = get_cursor_screen_pos()
            mouse.move_to_game(gx, gy)
            time.sleep(0.08)  # let any pending HID drain
            after = get_cursor_screen_pos()
            dx = after[0] - target_screen[0]
            dy = after[1] - target_screen[1]
            miss = abs(dx) + abs(dy)
            miss_total += miss
            miss_count += 1
            tag = "✓" if miss <= 2 else "✗"
            print(f"[{i}/{len(TARGETS)}] target game ({gx:>4d},{gy:>4d}) "
                  f"= screen {target_screen}")
            print(f"      before {before} → after {after}  "
                  f"Δ=({dx:+d},{dy:+d}) {tag}")

    avg = miss_total / max(1, miss_count)
    print(f"\naverage |Δ| = {avg:.2f} px over {miss_count} moves")
    if avg > 3:
        print("  ⚠ settle is missing target by >3 px on average — bezier "
              "scale + ratio mismatch")
    else:
        print("  cursor lands within tolerance — typing failure is "
              "elsewhere")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
