"""Reproduce the typing failure in isolation.

Sequence:
  1. Verify shop open.
  2. Find 治癒藥水 row via scroll-and-OCR.
  3. Click row (HumanMouse — bezier + settle).
  4. Wait LONG (1.5 s, much longer than the default 120 ms).
  5. key_tap("1").
  6. Wait, capture.

If qty=1 after this, the click_at_game's post-sleep was too short.
If qty stays 0, our HID click itself does something different from
a physical mouse click that destroys qty-input focus.
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
from human_mouse import HumanMouse
from window_mapper import MouseAccelerationOff
from buy_scrolls_test import (
    find_shop_buy, find_and_click_item, LIST_CENTRE_FRAME,
)


def main() -> int:
    user32 = ctypes.windll.user32
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        return 1
    client = BoardClient.auto_detect()
    print(f"Board: {client.port}, {client.version()}")

    mouse = HumanMouse(client, hwnd)
    user32.SetForegroundWindow(hwnd)
    jitter_sleep(0.3)
    ocr_engine = cap._get_ocr()

    with MouseAccelerationOff():
        cw, ch = cap.get_client_size(hwnd)
        before = cap.grab_frame("Lineage")
        fw, fh = before.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1

        if find_shop_buy(before) is None:
            print("✗ shop not open")
            client.close()
            return 1

        list_game = (LIST_CENTRE_FRAME[0] - border_w,
                     LIST_CENTRE_FRAME[1] - title_h)
        mouse.move_to_game(*list_game)
        jitter_sleep(0.2)
        for _ in range(20):
            client.wheel(1)
            jitter_sleep(0.04)
        jitter_sleep(0.3)

        print("\nfind+click 治癒藥水 row…")
        row_y = find_and_click_item("治癒藥水", mouse, client, ocr_engine,
                                    hwnd, border_w, title_h)
        if row_y is None:
            print("✗ not found")
            client.close()
            return 1

        # LONG sleep — the goal is to test if the issue is just timing.
        print("waiting 1.5 s before typing…")
        time.sleep(1.5)
        cap.grab_frame("Lineage").save("samples/clickpotion_after_click.png")

        print("→ key_tap('1')")
        client.key_tap("1")
        jitter_sleep(0.4)
        cap.grab_frame("Lineage").save("samples/clickpotion_after_type.png")

        mouse.move_to_game(640, 700)
    client.close()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
