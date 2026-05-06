"""Minimal test — assume the shop is already open (user opens it).
Find 治癒藥水, click row, type "1", click bottom Buy. Purely the
shop-side flow, no teleport / merchant click. Mirrors the working
buy_meat_test / buy_scrolls_test pattern exactly.
"""
from __future__ import annotations

import ctypes
import io
import sys
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
    find_shop_buy, find_and_click_item, type_qty,
    LIST_CENTRE_FRAME,
)


TARGET = "治癒藥水"
QTY = 1


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
        before.save("samples/potion_01_before.png")
        fw, fh = before.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1

        if find_shop_buy(before) is None:
            print("✗ shop not open — open it first.")
            client.close()
            return 1
        print("shop ✓")

        # Park cursor on list, scroll to top.
        list_game = (LIST_CENTRE_FRAME[0] - border_w,
                     LIST_CENTRE_FRAME[1] - title_h)
        mouse.move_to_game(*list_game)
        jitter_sleep(0.2)
        for _ in range(20):
            client.wheel(1)
            jitter_sleep(0.04)
        jitter_sleep(0.3)

        print(f"\nbuying {TARGET} × {QTY}")
        row_y = find_and_click_item(TARGET, mouse, client, ocr_engine,
                                    hwnd, border_w, title_h)
        if row_y is None:
            print(f"✗ couldn't find {TARGET}")
            client.close()
            return 1
        type_qty(client, QTY, hwnd=hwnd)
        cap.grab_frame("Lineage").save("samples/potion_02_typed.png")

        live = cap.grab_frame("Lineage")
        buy = find_shop_buy(live)
        if buy is None:
            print("✗ bottom Buy bar lost")
            client.close()
            return 1
        bx, by, score = buy
        print(f"bottom Buy at frame ({bx}, {by}) score={score:.2f}")
        mouse.click_at_game(bx - border_w, by - title_h)
        jitter_sleep(0.9)
        cap.grab_frame("Lineage").save("samples/potion_03_after.png")

        mouse.move_to_game(640, 700)
    client.close()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
