"""Use the speak-scroll (paged hotkey P3-F6) to teleport to the
雜貨商人 in 奇岩村.

Flow:
  1. Press F3 (page switch to skill page 3), then F6 (fire slot 6 =
     speak scroll). Game pops the village/merchant selection menu on
     the left side of the screen.
  2. Wait for the menu to render.
  3. Park cursor over the menu so wheel events route to it.
  4. Scroll-and-OCR until 「奇岩村」 header is visible.
  5. From the OCR result, locate the 「雜貨商人」 entry that sits
     **below 奇岩村 and above the next 【XXX村】 header** (so we don't
     pick another village's 雜貨商人 by accident).
  6. Click that entry — game starts the teleport.
  7. Wait, capture before/after.
"""
from __future__ import annotations

import ctypes
import io
import re
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


# Speak scroll hotkey (paged): page F3, slot F6.
HOTKEY_PAGE = "f3"
HOTKEY_SLOT = "f6"

# OCR ROI for the left-side menu. Wide vertical band that covers
# header + merchant entries; x capped narrow because the menu lives
# in the leftmost column.
MENU_OCR_ROI = (10, 40, 260, 900)

# Park cursor over the menu so wheel events scroll the menu (not
# something else).
MENU_CENTRE_FRAME = (130, 400)

VILLAGE_HEADER_RE = re.compile(r"【.*村】")
TARGET_VILLAGE = "奇岩村"
TARGET_MERCHANT = "雜貨商人"

SCROLL_STEP = 5
MAX_SCROLL_ITERS = 25


def fire_speak_scroll(client) -> None:
    """Trigger the speak scroll via the paged hotkey. F-keys: page
    switch (F3) then slot fire (F6). Memory note:
    F1-F3 = page switch, F4 = pickup, F5-F12 = skill slots."""
    print(f"firing speak scroll: page {HOTKEY_PAGE} → slot {HOTKEY_SLOT}")
    client.key_tap(HOTKEY_PAGE)
    jitter_sleep(0.18)
    client.key_tap(HOTKEY_SLOT)


def ocr_menu(ocr_engine, frame_img):
    """Return list of (cx, cy, text, conf) for each detected item in
    the left-side menu, sorted top→bottom."""
    crop = frame_img.crop(MENU_OCR_ROI)
    res, _ = ocr_engine(np.array(crop))
    if not res:
        return []
    items = []
    for box, text, conf in res:
        cx = sum(p[0] for p in box) / 4 + MENU_OCR_ROI[0]
        cy = sum(p[1] for p in box) / 4 + MENU_OCR_ROI[1]
        items.append((round(cx), round(cy), text.strip(), float(conf)))
    items.sort(key=lambda it: it[1])
    return items


def find_target_in_menu(items):
    """Walk the OCR rows top→bottom. After we see 奇岩村, we're
    inside that village's section; the next village header ends it.
    Inside the section, click the first row matching 雜貨商人."""
    in_target_section = False
    for cx, cy, text, conf in items:
        is_header = bool(VILLAGE_HEADER_RE.search(text))
        if TARGET_VILLAGE in text and is_header:
            in_target_section = True
            continue
        if in_target_section:
            # If we hit another village header, the target section
            # ended without a 雜貨商人 (shouldn't happen for 奇岩村,
            # but stops a runaway match into a different village).
            if is_header:
                return None
            if TARGET_MERCHANT in text or text.startswith("雜貨商"):
                return (cx, cy, text, conf)
    return None


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
        before.save("samples/teleport_01_before.png")
        fw, fh = before.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1

        # Step 1: fire the speak scroll.
        fire_speak_scroll(client)
        jitter_sleep(0.9)
        menu_img = cap.grab_frame("Lineage")
        menu_img.save("samples/teleport_02_menu.png")

        # Step 2: park cursor over menu.
        menu_game = (MENU_CENTRE_FRAME[0] - border_w,
                     MENU_CENTRE_FRAME[1] - title_h)
        mouse.move_to_game(*menu_game)
        jitter_sleep(0.25)

        # Step 3: scroll-and-OCR until 奇岩村 section + 雜貨商人 visible.
        clicked = None
        for it in range(MAX_SCROLL_ITERS):
            # Make sure Lineage has focus — cap.grab_frame opens a
            # fresh WGC session each call which has been observed to
            # steal foreground briefly, causing subsequent wheel events
            # to land in a different window. Re-asserting per iter is
            # cheap insurance.
            user32.SetForegroundWindow(hwnd)
            img = cap.grab_frame("Lineage")
            img.save(f"samples/teleport_03_iter_{it:02d}.png")
            items = ocr_menu(ocr_engine, img)
            print(f"[iter {it}] OCR sees {len(items)} rows")
            for cx, cy, text, conf in items[:8]:
                print(f"  y={cy} x={cx} conf={conf:.2f}  {text}")

            target = find_target_in_menu(items)
            if target is not None:
                cx, cy, text, conf = target
                print(f"\n✓ click 雜貨商人 at frame ({cx}, {cy}) "
                      f"text='{text}' conf={conf:.2f}")
                click_game = (cx - border_w, cy - title_h)
                mouse.click_at_game(*click_game)
                clicked = (cx, cy)
                break

            # Re-foreground + scroll one tick at a time, with a tiny
            # gap between, so each HID wheel report is processed
            # individually rather than coalesced.
            user32.SetForegroundWindow(hwnd)
            for _ in range(SCROLL_STEP):
                client.wheel(-1)
                jitter_sleep(0.05)
            jitter_sleep(0.15)

        if clicked is None:
            print("✗ failed to locate 奇岩村 → 雜貨商人 in menu")
            client.close()
            return 1

        # Wait for teleport effect, then capture.
        print("waiting for teleport…")
        jitter_sleep(2.5)
        cap.grab_frame("Lineage").save("samples/teleport_04_after.png")
        print("✓ saved samples/teleport_*.png")

        mouse.move_to_game(640, 700)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
