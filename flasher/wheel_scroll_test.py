"""Test wheel scroll in the open shop window.

Moves the cursor over the item list, captures the BEFORE state,
scrolls down 1 tick (= 7 rows per user's spec), captures AFTER, and
runs OCR on the top of the list both times so we can see the shift.

Assumes shop is already open. Run open_shop_test.py first if not.
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


# Frame coords for the centre of the shop's item list — far from the
# scrollbar / qty controls, so wheel events scroll the list rather than
# something else.
LIST_CENTRE_FRAME = (150, 200)

# OCR ROI for top-of-list (first 4 visible rows).
LIST_OCR_ROI = (50, 55, 220, 280)


def ocr_list(ocr_engine, img):
    crop = img.crop(LIST_OCR_ROI)
    res, _ = ocr_engine(np.array(crop))
    if not res:
        return []
    items = []
    for box, text, conf in res:
        cy = sum(p[1] for p in box) / 4 + LIST_OCR_ROI[1]
        items.append((round(cy), text.strip(), float(conf)))
    items.sort()
    return items


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
    ocr_engine = cap._get_ocr()

    with MouseAccelerationOff():
        cw, ch = cap.get_client_size(hwnd)
        before = cap.grab_frame("Lineage")
        before.save("samples/wheel_01_before.png")
        fw, fh = before.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1
        print(f"frame {fw}x{fh}, client {cw}x{ch}")

        items_before = ocr_list(ocr_engine, before)
        print("BEFORE list (top items):")
        for cy, text, conf in items_before:
            print(f"  y={cy:3d} conf={conf:.2f}  {text}")

        # Position cursor over the item list.
        list_game = (LIST_CENTRE_FRAME[0] - border_w,
                     LIST_CENTRE_FRAME[1] - title_h)
        print(f"\nmoving cursor to list centre frame {LIST_CENTRE_FRAME} "
              f"= game {list_game}")
        mouse.move_to_game(*list_game)
        jitter_sleep(0.3)

        # Scroll down 1 tick.
        print("scrolling down 1 tick (-1)…")
        client.wheel(-1)
        jitter_sleep(0.4)

        after = cap.grab_frame("Lineage")
        after.save("samples/wheel_02_after_down1.png")
        items_after = ocr_list(ocr_engine, after)
        print("AFTER -1 scroll, list (top items):")
        for cy, text, conf in items_after:
            print(f"  y={cy:3d} conf={conf:.2f}  {text}")

        # Scroll back up 1 tick.
        print("\nscrolling up 1 tick (+1) to restore…")
        client.wheel(1)
        jitter_sleep(0.4)
        restored = cap.grab_frame("Lineage")
        restored.save("samples/wheel_03_after_up1.png")
        items_rest = ocr_list(ocr_engine, restored)
        print("AFTER +1 scroll, list (top items):")
        for cy, text, conf in items_rest:
            print(f"  y={cy:3d} conf={conf:.2f}  {text}")

        # Park cursor.
        mouse.move_to_game(640, 700)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
