"""End-to-end shopping run:
  1. Speak scroll (P3-F6) → menu → 奇岩村 → 雜貨商人 → teleport
  2. Hover + OCR find merchant sprite → click → wait dialog
  3. cv2 template match Buy/Sell pair → click Buy → shop window
  4. Scroll-and-OCR shop list for 治癒藥水
  5. Click row, type "1", click bottom Buy → purchase

Reuses helpers imported from the per-phase test scripts so we don't
fork three copies of the same logic.
"""
from __future__ import annotations

import ctypes
import io
import sys
from pathlib import Path

import cv2
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

# Phase 1 helpers — speak scroll teleport.
from speak_to_merchant_test import (
    fire_speak_scroll, ocr_menu, find_target_in_menu,
    MENU_CENTRE_FRAME,
    SCROLL_STEP as MENU_SCROLL_STEP,
    MAX_SCROLL_ITERS as MAX_MENU_ITERS,
)
# Phase 2 helpers — open shop.
from open_shop_test import (
    MERCHANT_HOVER_CANDIDATES, find_merchant_label, find_buy_button,
)
# Phase 3 helpers — buy from shop list.
from buy_scrolls_test import (
    find_shop_buy, find_and_click_item, type_qty,
    LIST_CENTRE_FRAME,
)


# What we're buying. Single item, single quantity — easy to extend.
SHOPPING_LIST = [
    ("治癒藥水", 1),
]


def teleport_to_merchant(client, mouse, ocr_engine, hwnd,
                         border_w: int, title_h: int) -> bool:
    """Phase 1: fire speak scroll, navigate menu to 奇岩村's 雜貨商人,
    click. Returns True on click success (teleport not yet verified
    here — caller should sleep + sanity-check)."""
    print("=== phase 1: speak-scroll teleport ===")
    user32 = ctypes.windll.user32
    # The F3/F6 key_taps below are HID keyboard reports — they land
    # in whatever window has keyboard focus. Re-foreground Lineage
    # right before firing so the keys aren't swallowed by the
    # terminal or another window that crept up.
    user32.SetForegroundWindow(hwnd)
    jitter_sleep(0.15)
    fire_speak_scroll(client)
    jitter_sleep(0.9)
    cap.grab_frame("Lineage").save("samples/full_01_menu.png")
    menu_game = (MENU_CENTRE_FRAME[0] - border_w,
                 MENU_CENTRE_FRAME[1] - title_h)
    mouse.move_to_game(*menu_game)
    jitter_sleep(0.25)

    last_top: str | None = None
    stale = 0
    for it in range(MAX_MENU_ITERS):
        user32.SetForegroundWindow(hwnd)
        img = cap.grab_frame("Lineage")
        items = ocr_menu(ocr_engine, img)
        target = find_target_in_menu(items)
        if target is not None:
            cx, cy, text, conf = target
            print(f"  found 奇岩村→雜貨商人 at frame ({cx}, {cy}) "
                  f"conf={conf:.2f}")
            mouse.click_at_game(cx - border_w, cy - title_h)
            jitter_sleep(2.5)  # wait for teleport
            cap.grab_frame("Lineage").save("samples/full_02_teleported.png")
            return True

        # Bottom-of-list detector.
        if items:
            top_txt = items[0][2]
            if top_txt == last_top:
                stale += 1
                if stale >= 3:
                    print("  ✗ menu end reached without finding target")
                    return False
            else:
                stale = 0
                last_top = top_txt

        user32.SetForegroundWindow(hwnd)
        for _ in range(MENU_SCROLL_STEP):
            client.wheel(-1)
            jitter_sleep(0.05)
        jitter_sleep(0.15)
    print(f"  ✗ menu scroll exhausted after {MAX_MENU_ITERS} iters")
    return False


def open_shop(client, mouse, ocr_engine, hwnd,
              border_w: int, title_h: int) -> bool:
    """Phase 2: hover candidate positions to coax merchant label,
    click sprite, click Buy in dialog. Returns True when shop window
    is visible."""
    print("\n=== phase 2: open shop ===")
    user32 = ctypes.windll.user32

    # Hover until 雜貨商 label renders.
    hit = None
    for i, (gx, gy) in enumerate(MERCHANT_HOVER_CANDIDATES, 1):
        print(f"  [{i}/{len(MERCHANT_HOVER_CANDIDATES)}] hover game ({gx},{gy})")
        mouse.move_to_game(gx, gy)
        jitter_sleep(0.8)
        img = cap.grab_frame("Lineage")
        hit = find_merchant_label(ocr_engine, img)
        if hit:
            break
    if hit is None:
        print("  ✗ merchant label not found")
        return False
    text, lx, ly, conf = hit
    print(f"  label '{text}' at frame ({lx:.0f}, {ly:.0f}) conf={conf:.2f}")

    # Click merchant sprite (label-anchor + 30 px down).
    click_frame = (int(lx), int(ly + 30))
    click_game = (click_frame[0] - border_w, click_frame[1] - title_h)
    mouse.click_at_game(*click_game)
    jitter_sleep(1.5)

    # Find Buy in the dialog and click.
    img = cap.grab_frame("Lineage")
    img.save("samples/full_03_dialog.png")
    buy = find_buy_button(img)
    if buy is None:
        print("  ✗ Buy button not found in dialog")
        return False
    bx, by, score = buy
    print(f"  dialog Buy at frame ({bx}, {by}) score={score:.2f}")
    mouse.click_at_game(bx - border_w, by - title_h)
    jitter_sleep(1.2)

    # Confirm shop window opened.
    img = cap.grab_frame("Lineage")
    img.save("samples/full_04_shop_open.png")
    if find_shop_buy(img) is None:
        print("  ✗ shop window did not open after Buy click")
        return False
    print("  shop window open ✓")
    return True


def buy_items(client, mouse, ocr_engine, hwnd,
              border_w: int, title_h: int,
              items: list[tuple[str, int]]) -> bool:
    """Phase 3: with shop open, find each item, click + type qty,
    then one bottom-Buy click closes the transaction."""
    print(f"\n=== phase 3: buy {len(items)} item(s) ===")
    # Echo-before-action per the new memory rule. Note: unit prices
    # aren't OCR'd here so we can only echo the qty, not gold cost.
    for name, qty in items:
        print(f"  · {name} × {qty}")

    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)

    # Park cursor over the list, scroll to top.
    list_game = (LIST_CENTRE_FRAME[0] - border_w,
                 LIST_CENTRE_FRAME[1] - title_h)
    mouse.move_to_game(*list_game)
    jitter_sleep(0.2)
    print("  scrolling list to top…")
    for _ in range(20):
        client.wheel(1)
        jitter_sleep(0.04)
    jitter_sleep(0.3)

    for i, (name, qty) in enumerate(items, 1):
        print(f"\n  [{i}/{len(items)}] {name} × {qty}")
        row_y = find_and_click_item(name, mouse, client, ocr_engine,
                                    hwnd, border_w, title_h)
        if row_y is None:
            print(f"  ✗ couldn't find {name}")
            return False
        type_qty(client, qty, hwnd=hwnd)
        cap.grab_frame("Lineage").save(
            f"samples/full_05_typed_{i}_{name}.png")

    # Single bottom-Buy click finishes the transaction.
    print("\n  click bottom Buy…")
    img = cap.grab_frame("Lineage")
    buy = find_shop_buy(img)
    if buy is None:
        print("  ✗ bottom Buy bar lost")
        return False
    bx, by, score = buy
    print(f"  bottom Buy at frame ({bx}, {by}) score={score:.2f}")
    mouse.click_at_game(bx - border_w, by - title_h)
    jitter_sleep(0.9)
    cap.grab_frame("Lineage").save("samples/full_06_after_buy.png")
    print("  ✓ purchase complete (shop closes)")
    return True


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
        before.save("samples/full_00_start.png")
        fw, fh = before.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1
        print(f"frame {fw}x{fh}, client {cw}x{ch}")

        if not teleport_to_merchant(client, mouse, ocr_engine, hwnd,
                                    border_w, title_h):
            client.close(); return 1

        if not open_shop(client, mouse, ocr_engine, hwnd,
                         border_w, title_h):
            client.close(); return 1

        if not buy_items(client, mouse, ocr_engine, hwnd,
                         border_w, title_h, SHOPPING_LIST):
            client.close(); return 1

        # Park cursor.
        mouse.move_to_game(640, 700)

    client.close()
    print("\n✓ full shopping run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
