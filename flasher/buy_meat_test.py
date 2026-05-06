"""Full meat purchase flow:
  1. Verify shop window open via bottom Total/Buy/Cancel template match.
  2. Click on 肉 row (top of item list).
  3. Type "19" via keyboard (BoardClient digit key_tap).
  4. Click the bottom Buy button (anchored from template top-left).
  5. Capture each phase.

Assumes shop is already open. Run open_shop_test.py first if not.
"""
from __future__ import annotations

import ctypes
import io
import sys
import time
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


_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
SHOP_BAR_TPL_PATH = _TEMPLATES_DIR / "shop_buy_cancel.png"

# Click offsets inside the bottom-bar template (which is 410×36).
# Verified by colour-cross sweep: Buy text centre at (300, 8), Cancel
# at (360, 8). Earlier guess (290, 18) landed in the dark below Buy.
SHOP_BUY_OFFSET = (300, 8)
SHOP_CANCEL_OFFSET = (360, 8)

# Frame coords for the 肉 row click point — top of the item list,
# left of the quantity controls.
MEAT_ROW_FRAME = (90, 70)

QTY = "19"
MATCH_THRESHOLD = 0.80


def find_shop_buy(frame_img):
    """NCC-locate the shop's bottom Buy button. Returns (cx, cy, score)
    in frame coords or None if score < threshold."""
    tpl = cv2.imread(str(SHOP_BAR_TPL_PATH), cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(f"missing template: {SHOP_BAR_TPL_PATH}")
    arr = np.asarray(frame_img)
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[..., :3]
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    # Bottom bar is in lower-left of frame.
    search = bgr[h // 2 :, : w // 2]
    res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, max_loc = cv2.minMaxLoc(res)
    if score < MATCH_THRESHOLD:
        return None
    tx, ty = max_loc
    # Adjust to full-frame coords (bar lives in lower-left search slice).
    tx += 0
    ty += h // 2
    cx = tx + SHOP_BUY_OFFSET[0]
    cy = ty + SHOP_BUY_OFFSET[1]
    return (cx, cy, float(score))


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
        cw, ch = cap.get_client_size(hwnd)
        before = cap.grab_frame("Lineage")
        before.save("samples/buymeat_01_before.png")
        fw, fh = before.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1
        print(f"frame {fw}x{fh}, client {cw}x{ch}, "
              f"border_w={border_w}, title_h={title_h}")

        # Step 1: shop open check.
        buy_btn = find_shop_buy(before)
        if buy_btn is None:
            print("✗ shop window not open (bottom Buy bar not detected).")
            client.close()
            return 1
        bx, by, score = buy_btn
        print(f"shop open ✓ — bottom Buy at frame ({bx}, {by}) score={score:.3f}")

        # Step 2: click 肉 row.
        meat_game = (MEAT_ROW_FRAME[0] - border_w,
                     MEAT_ROW_FRAME[1] - title_h)
        print(f"click 肉 at frame {MEAT_ROW_FRAME} = game {meat_game}")
        mouse.click_at_game(*meat_game)
        jitter_sleep(0.5)
        cap.grab_frame("Lineage").save("samples/buymeat_02_clicked_meat.png")

        # Step 3: type 19. Each digit gets its own key tap with a small
        # gap so the game's input field has time to register.
        print(f"typing '{QTY}'…")
        for digit in QTY:
            client.key_tap(digit)
            jitter_sleep(0.08)
        jitter_sleep(0.3)
        cap.grab_frame("Lineage").save("samples/buymeat_03_typed.png")

        # Step 4: click bottom Buy. Re-detect — the bar may have shifted
        # vertically by a row when the qty highlighted.
        live = cap.grab_frame("Lineage")
        buy_btn = find_shop_buy(live)
        if buy_btn is None:
            print("✗ bottom Buy bar lost after type — aborting.")
            client.close()
            return 1
        bx, by, score = buy_btn
        print(f"  bottom Buy at frame ({bx}, {by}) score={score:.3f}")
        buy_game = (bx - border_w, by - title_h)
        print(f"click bottom Buy at game {buy_game}")
        mouse.click_at_game(*buy_game)

        jitter_sleep(0.8)
        cap.grab_frame("Lineage").save("samples/buymeat_04_after_buy.png")
        print("✓ saved samples/buymeat_0[1-4]_*.png")

        # Park.
        mouse.move_to_game(640, 700)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
