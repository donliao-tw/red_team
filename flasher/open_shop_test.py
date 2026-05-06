"""End-to-end open-shop primitive test.

Pipeline:
  1. Smooth-move cursor to upper-right where the merchant lives.
  2. Hover ~0.8 s for the in-game [雜貨商] label to render.
  3. OCR the upper-right zone; pick the merchant by label match.
  4. Click slightly below the label (the NPC sprite).
  5. Wait for the merchant dialog to render on the left side.
  6. Find the RED Buy button (per user spec — Buy is red, Sell blue)
     by colour mask in the left half of the screen.
  7. Click Buy.
  8. Capture the shop window for inspection. Stop here.
"""
from __future__ import annotations

import ctypes
import io
import sys
import time
from pathlib import Path

# Force stdout/stderr to UTF-8 so ✓/✗ glyphs don't crash on cp950 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import cv2
import numpy as np
from PIL import Image

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_BTN_TEMPLATE_PATH = _TEMPLATES_DIR / "btn_buy_sell.png"
_btn_template_cache: np.ndarray | None = None


def _load_btn_template() -> np.ndarray:
    global _btn_template_cache
    if _btn_template_cache is None:
        tpl = cv2.imread(str(_BTN_TEMPLATE_PATH), cv2.IMREAD_COLOR)
        if tpl is None:
            raise FileNotFoundError(f"template missing: {_BTN_TEMPLATE_PATH}")
        _btn_template_cache = tpl
    return _btn_template_cache

sys.path.insert(0, str(Path(__file__).resolve().parent))

import window_mapper
import capture as cap
from board_client import BoardClient, BoardClientError, jitter_sleep
from human_mouse import HumanMouse
from window_mapper import MouseAccelerationOff


MERCHANT_HOVER_CANDIDATES = [
    # The 雜貨商 sprite is narrow and the label only renders while the
    # cursor sits on the sprite. (1000, 80) and (1020, 80) both work
    # most of the time but landed just off the sprite once when the
    # corrected mouse landing got pixel-precise. Order from
    # most-reliable to least, so the happy path is one move.
    (1000,  80),
    (1020,  80),
    (1010,  90),
    (990,   80),
    (1000,  60),
]
SEARCH_BOX = (800, 30, 1284, 220)   # frame coords for upper-right
DIALOG_BOX = (0, 200, 340, 750)     # frame coords for the merchant
                                    # dialog (upper-left). x1 capped at
                                    # 340 so blue pixels in the game
                                    # world don't pull the cluster
                                    # centroid; the dialog itself ends
                                    # around x=320.


def find_merchant_label(ocr_engine, frame_img):
    crop = frame_img.crop(SEARCH_BOX)
    result, _ = ocr_engine(np.array(crop))
    if not result:
        return None
    for box, text, conf in result:
        if any(k in text for k in ("雜貨商", "邁爾")):
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            cx = (min(xs) + max(xs)) / 2 + SEARCH_BOX[0]
            cy = (min(ys) + max(ys)) / 2 + SEARCH_BOX[1]
            return (text, cx, cy, conf)
    return None


_BTN_MATCH_THRESHOLD = 0.85


def find_buy_sell_buttons(frame_img):
    """Locate the merchant-dialog Buy + Sell button pair via template match.

    The dialog only ever appears in the left half of the screen, so
    we restrict NCC search to x ∈ [0, frame_w // 2). The template is
    the full Buy + Sell compound (blue button + red button + side
    ornaments) — much more distinctive than either alone, so a high
    NCC score doubles as a "dialog open?" check.

    Returns ``(buy_xy, sell_xy, score)`` in frame coords, or
    ``None`` if no match clears the threshold.
    """
    tpl = _load_btn_template()
    th, tw = tpl.shape[:2]
    arr = np.asarray(frame_img)
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[..., :3]
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    search = bgr[:, : w // 2]
    res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < _BTN_MATCH_THRESHOLD:
        return None
    x0, y0 = max_loc
    # Buy occupies the left ~half of the template, Sell the right ~half.
    # Centre Buy at x0 + tw*0.27 (icon + "Buy" text), Sell at x0 + tw*0.73.
    buy_xy = (int(x0 + tw * 0.27), int(y0 + th * 0.5))
    sell_xy = (int(x0 + tw * 0.73), int(y0 + th * 0.5))
    return (buy_xy, sell_xy, float(max_val))


def find_buy_button(frame_img):
    """Compatibility shim — return only the Buy centre + score."""
    res = find_buy_sell_buttons(frame_img)
    if res is None:
        return None
    (bx, by), _, score = res
    return (bx, by, score)


# Backward-compat alias for older callers / tests.
find_red_buy_button = find_buy_button


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
        # Pre-check: maybe the merchant dialog is already up from a
        # previous run. If so, skip the merchant-finding step.
        cw, ch = cap.get_client_size(hwnd)
        img = cap.grab_frame("Lineage")
        fw, fh = img.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1
        early_buy = find_buy_button(img)
        if early_buy is not None:
            print(f"  dialog already open: Buy at frame {early_buy[:2]}")
            img.save("samples/shop_step2_dialog.png")
        else:
            # Step 1-3: hover + OCR to find merchant label. The label
            # only renders while the cursor is on the NPC sprite, so
            # we sweep a few candidate hover positions until OCR
            # catches the text.
            hit = None
            for i, hp in enumerate(MERCHANT_HOVER_CANDIDATES, 1):
                print(f"[{i}/{len(MERCHANT_HOVER_CANDIDATES)}] hover at game {hp}…")
                mouse.move_to_game(*hp)
                jitter_sleep(0.8)
                img = cap.grab_frame("Lineage")
                img.save(f"samples/shop_step1_hover_{i:02d}.png")
                hit = find_merchant_label(ocr_engine, img)
                if hit:
                    break
            if hit is None:
                print("✗ merchant label not found in any candidate hover.")
                mouse.move_to_game(640, 700)
                client.close()
                return 1
            text, lx, ly, conf = hit
            print(f"  label {text!r} at frame ({lx:.0f}, {ly:.0f}) conf={conf:.2f}")

            # Step 4: click merchant — body is a few px below the label.
            click_frame = (int(lx), int(ly + 30))
            click_game = (click_frame[0] - border_w, click_frame[1] - title_h)
            print(f"  click merchant at frame {click_frame} = game {click_game}")
            mouse.click_at_game(*click_game)

            # Step 5: wait for dialog.
            print("waiting for dialog…")
            jitter_sleep(1.5)
            img = cap.grab_frame("Lineage")
            img.save("samples/shop_step2_dialog.png")

        # Step 6: find Buy button (red) on left side.
        buy = find_red_buy_button(img)
        if buy is None:
            print("✗ Buy button not found in dialog area.")
            mouse.move_to_game(640, 700)
            client.close()
            return 1
        bx, by, cnt = buy
        print(f"  Buy button at frame ({bx}, {by}) (red px count {cnt})")

        # Step 7: click Buy.
        click_game = (bx - border_w, by - title_h)
        print(f"  click Buy at game {click_game}")
        mouse.click_at_game(*click_game)

        # Step 8: capture shop window.
        jitter_sleep(1.2)
        img = cap.grab_frame("Lineage")
        img.save("samples/shop_step3_window.png")
        print("✓ shop window captured to samples/shop_step3_window.png")

        # Park cursor.
        mouse.move_to_game(640, 700)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
