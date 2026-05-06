"""Move cursor over the upper-right area where the 雜貨商 (general
goods merchant) lives, hover to trigger the in-game name tooltip,
capture the frame, then OCR the upper-right corner to find the
merchant's label.

Doesn't click — only positions the cursor and reads back. Used to
verify we can locate the merchant before wiring the open_shop()
primitive.
"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import window_mapper  # set DPI awareness
import capture as cap
from board_client import BoardClient, BoardClientError, jitter_sleep
from human_mouse import HumanMouse
from window_mapper import MouseAccelerationOff


# Where to put the cursor while looking for the merchant. The label
# only appears on hover, so we have to be roughly on top of the NPC
# sprite first. Estimated from user's earlier screenshot of the shop
# building (frame x=~1000, y=~75 in the 1280×960 client area).
HOVER_TARGETS = [
    (1000,  60),
    (1000, 100),
    (1020,  80),
    (980,   80),
]

# OCR window for the upper-right merchant zone. Frame coords.
SEARCH_BOX = (800, 30, 1284, 220)


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

    found = None
    with MouseAccelerationOff():
        for i, (gx, gy) in enumerate(HOVER_TARGETS, 1):
            print(f"[{i}/{len(HOVER_TARGETS)}] hover at game ({gx}, {gy})…")
            mouse.move_to_game(gx, gy)
            jitter_sleep(0.8)  # wait for in-game name label to render
            img = cap.grab_frame("Lineage")
            crop = img.crop(SEARCH_BOX)
            crop.save(f"samples/merchant_hover_{i:02d}.png")

            result, _ = ocr_engine(np.array(crop))
            hits = []
            if result:
                for box, text, conf in result:
                    if any(k in text for k in ("雜貨商", "邁爾", "雜貨", "商")):
                        xs = [p[0] for p in box]
                        ys = [p[1] for p in box]
                        cx = (min(xs) + max(xs)) / 2 + SEARCH_BOX[0]
                        cy = (min(ys) + max(ys)) / 2 + SEARCH_BOX[1]
                        hits.append((text, cx, cy, conf))
            for text, cx, cy, conf in hits:
                print(f"     match {text!r} at frame ({cx:.0f}, {cy:.0f}) conf={conf:.2f}")
            if hits:
                found = (gx, gy, hits)
                break
        # Park cursor away
        mouse.move_to_game(640, 700)

    client.close()

    if found is None:
        print("\n✗ NOT FOUND — try a different hover target or check screenshot.")
        return 1
    gx, gy, hits = found
    print(f"\n✓ FOUND merchant via hover at game ({gx}, {gy}); label hits:")
    for h in hits:
        print(f"  {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
