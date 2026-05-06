"""Scroll through the open shop and OCR every visible row, so we can
see exactly what items the merchant has + what the OCR reads them as.

Run with the shop window open.
"""
from __future__ import annotations

import ctypes
import io
import sys
from pathlib import Path

import numpy as np

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
    find_shop_buy, ocr_list, LIST_CENTRE_FRAME,
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
        img = cap.grab_frame("Lineage")
        fw, fh = img.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1

        if find_shop_buy(img) is None:
            print("✗ shop not open")
            client.close()
            return 1

        # Park cursor on list, scroll to top.
        mouse.move_to_game(LIST_CENTRE_FRAME[0] - border_w,
                           LIST_CENTRE_FRAME[1] - title_h)
        jitter_sleep(0.2)
        for _ in range(25):
            client.wheel(1)
            jitter_sleep(0.04)
        jitter_sleep(0.3)

        seen: set[str] = set()
        last_top = None
        stale = 0
        for it in range(20):
            user32.SetForegroundWindow(hwnd)
            img = cap.grab_frame("Lineage")
            rows = ocr_list(ocr_engine, img)
            print(f"\n[iter {it}] {len(rows)} rows visible:")
            for cy, text, conf in rows:
                marker = " " if text in seen else "*"
                print(f"  {marker} y={cy} conf={conf:.2f}  '{text}'")
                seen.add(text)

            if rows:
                top = rows[0][1]
                if top == last_top:
                    stale += 1
                    if stale >= 2:
                        print("\n--- end of list ---")
                        break
                else:
                    stale = 0
                    last_top = top

            user32.SetForegroundWindow(hwnd)
            for _ in range(5):
                client.wheel(-1)
                jitter_sleep(0.05)
            jitter_sleep(0.15)

        print("\n=== ALL UNIQUE ITEMS ===")
        for s in sorted(seen):
            print(f"  {s}")

        mouse.move_to_game(640, 700)
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
