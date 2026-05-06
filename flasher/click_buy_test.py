"""Diagnostic: assume the merchant Buy/Sell dialog is already open.

Find the Buy button, print every coordinate hop, MOVE the cursor to
it (no click yet), pause 3 s so a human can eyeball whether the
cursor actually landed on Buy, then click and capture.

Used to isolate "did the move land?" from "did the click register?"
without the merchant-finding step adding noise.
"""
from __future__ import annotations

import ctypes
import io
import sys
import time
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import window_mapper  # noqa: F401  — sets DPI awareness on import
import capture as cap
from board_client import BoardClient, BoardClientError, jitter_sleep
from human_mouse import HumanMouse
from window_mapper import (
    MouseAccelerationOff,
    client_to_screen,
    get_cursor_screen_pos,
)
from open_shop_test import find_buy_button, DIALOG_BOX


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

    with MouseAccelerationOff():
        img = cap.grab_frame("Lineage")
        img.save("samples/clickbuy_before.png")
        cw, ch = cap.get_client_size(hwnd)
        fw, fh = img.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1
        print(f"frame {fw}x{fh}, client {cw}x{ch}, "
              f"border_w={border_w}, title_h={title_h}")
        print(f"DIALOG_BOX={DIALOG_BOX}")

        buy = find_buy_button(img)
        if buy is None:
            print("✗ Buy button not found — dialog open?")
            client.close()
            return 1
        bx, by, n = buy
        print(f"Buy frame coord: ({bx}, {by}), {n} blue px")

        click_game = (bx - border_w, by - title_h)
        target_screen = client_to_screen(hwnd, *click_game)
        print(f"  → game (client) coord: {click_game}")
        print(f"  → screen target:       {target_screen}")
        print(f"  cursor before move:    {get_cursor_screen_pos()}")

        # Move only — no click yet.
        mouse.move_to_game(*click_game)
        time.sleep(0.05)
        landed = get_cursor_screen_pos()
        print(f"  cursor after move:     {landed}  "
              f"(Δ from target: "
              f"{landed[0]-target_screen[0]:+d}, "
              f"{landed[1]-target_screen[1]:+d})")

        # Save a frame WHILE hovering so we can post-mortem the position
        # (WGC excludes cursor, but the dialog state will tell us).
        hover_img = cap.grab_frame("Lineage")
        hover_img.save("samples/clickbuy_hovering.png")

        # Pause so the user can see whether the cursor is on Buy.
        print("Hovering 3 s — eyeball whether cursor is on Buy…")
        time.sleep(3.0)

        # Now click.
        print("clicking…")
        client.click()
        jitter_sleep(0.4)
        after = cap.grab_frame("Lineage")
        after.save("samples/clickbuy_after.png")
        print("✓ saved samples/clickbuy_{before,hovering,after}.png")

        # Park.
        mouse.move_to_game(640, 700)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
