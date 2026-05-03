"""Test minimap detection + auto-open via Ctrl+M.

Reads current frame, reports red-arrow pixel count, and if the
minimap is closed, sends Ctrl+M to open it. Re-checks and reports.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from board_client import BoardClient, BoardClientError
from minimap import (
    MINIMAP_RED_THRESHOLD, count_arrow_pixels, ensure_minimap_open,
    is_minimap_open,
)


def main() -> int:
    import ctypes
    import time
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

    img = cap.grab_frame("Lineage")
    cnt = count_arrow_pixels(img)
    print(f"Initial: red-arrow px = {cnt}, "
          f"minimap {'OPEN' if cnt >= MINIMAP_RED_THRESHOLD else 'CLOSED'}")

    print("Will focus Lineage in 2 s, then send Ctrl+M, then wait, then capture.")
    print("Watch the screen for the mini-map to open.")
    time.sleep(2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    print("→ Sending Ctrl+M now")
    client.key_combo("ctrl", "m")
    print("→ Waiting 2 s for render…")
    time.sleep(2)

    img = cap.grab_frame("Lineage")
    cnt = count_arrow_pixels(img)
    print(f"After: red-arrow px = {cnt}, "
          f"minimap {'OPEN' if is_minimap_open(img) else 'CLOSED'}")
    img.save("samples/mm_after_ctrlm.png")

    client.close()
    return 0 if cnt >= 20 else 1


if __name__ == "__main__":
    sys.exit(main())
