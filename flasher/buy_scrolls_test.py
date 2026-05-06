"""Buy 瞬間移動卷軸 ×10 + 返回卷軸 ×3 in one shop visit.

Flow:
  1. Verify shop open (bottom Buy/Cancel bar template match).
  2. Move cursor over the item list so wheel events route there.
  3. Scroll to top (wheel-up many ticks; idempotent).
  4. For each (item, qty):
       - scroll-and-OCR until item visible
       - click row
       - type qty
  5. Click the bottom Buy ONCE — both items purchased in a single
     transaction (each row keeps its own qty; Total sums them).

Assumes shop is open. Run open_shop_test.py first if not.
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


_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
SHOP_BAR_TPL_PATH = _TEMPLATES_DIR / "shop_buy_cancel.png"

# Buy click offset within the bottom-bar template. The template was
# re-cropped 2026-05-04 to *exclude* the "Total: N/M" text — that
# zone has variable numbers (qty × price changes Total, gold drops
# after each purchase) so an NCC match against it dropped below
# threshold the moment we put a digit in. New template covers just
# Buy + Cancel + their frame; Buy centre is at template (30, 10).
SHOP_BUY_OFFSET = (30, 10)

# Frame coords for an "anywhere over the item list" cursor anchor —
# wheel events fire wherever the cursor sits, so we park it over the
# list before scrolling.
LIST_CENTRE_FRAME = (150, 200)

# OCR ROI covering the whole 8-row visible list (left half = name only).
LIST_OCR_ROI = (50, 55, 220, 590)

# Row-select click: lands on the icon/name area (well clear of qty).
ROW_CLICK_X = 90

# Order matters here only for log readability — in a single shop
# transaction each row keeps its own qty regardless of click order.
SHOPPING_LIST = [
    ("瞬間移動卷軸", 10),
    ("返回卷軸",      3),
]

MATCH_THRESHOLD = 0.80
MAX_SCROLL_ITERS = 10
# Ticks per scroll iteration. The list shows 8 rows; stepping 7
# advances exactly one page minus 1 row of overlap — fastest possible
# without risking that a target gets skipped between consecutive OCR
# windows.
SCROLL_STEP = 7


def find_shop_buy(frame_img):
    tpl = cv2.imread(str(SHOP_BAR_TPL_PATH), cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(f"missing template: {SHOP_BAR_TPL_PATH}")
    arr = np.asarray(frame_img)
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[..., :3]
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    search = bgr[h // 2 :, : w // 2]
    res = cv2.matchTemplate(search, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, max_loc = cv2.minMaxLoc(res)
    if score < MATCH_THRESHOLD:
        return None
    tx, ty = max_loc
    ty += h // 2
    return (tx + SHOP_BUY_OFFSET[0], ty + SHOP_BUY_OFFSET[1], float(score))


def ocr_list(ocr_engine, img):
    """Return [(row_centre_y, text, conf)] sorted top→bottom."""
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


def name_matches(target: str, ocr_text: str) -> bool:
    """Loose item-name matcher. Handles three OCR pathologies:

      1. Prefix decoration: '+0 短統靴' for the bare '短統靴'.
      2. Simplified-character substitution: '短統靴' → '短统靴'.
      3. Single-char drop: '治癒藥水' → '治藥水' (OCR ate the 癒).

    Direct substring covers (1) and (2). For (3) we try removing each
    char of the target one at a time and re-checking — generic enough
    to handle whichever character OCR drops without a per-item alias
    table. False-positives possible if a longer item shares the
    truncated-target as a substring (e.g. '強力治癒藥水' also matches
    target '治癒藥水'), but the find loop iterates rows top→bottom and
    Lineage merchants list the basic item before its enhanced
    variants — so the first hit is the wanted one."""
    if not ocr_text:
        return False
    t = target.strip()
    o = ocr_text.strip()
    if t in o or o in t:
        return True
    # Drop-one-char fuzz.
    if len(t) >= 3:
        for i in range(len(t)):
            cand = t[:i] + t[i + 1:]
            if cand and cand in o:
                return True
    # Prefix-half fallback for very long names.
    head = t[: max(2, len(t) // 2)]
    return head in o


def scroll_to_top(client, ticks: int = 20) -> None:
    """Idempotent — overshoots upward; the list clamps at row 0."""
    for _ in range(ticks):
        client.wheel(1)
        jitter_sleep(0.04)
    jitter_sleep(0.25)


def find_and_click_item(target: str, mouse, client, ocr_engine, hwnd,
                        border_w: int, title_h: int) -> int | None:
    """Scroll the shop list until ``target`` becomes visible, then
    click that row. Returns the row's frame-y on success or None.

    Deliberately *no* SetForegroundWindow calls: in the working
    buy_scrolls_test (which typed 100 / 3 successfully) there were
    none, and adding them caused typing into the qty input to
    silently no-op afterwards. Theory: SetForegroundWindow re-asserts
    Lineage focus from the OS, which resets the shop's implicit
    qty-input focus, leaving keystrokes nowhere to go."""
    print(f"  finding item '{target}'…")
    list_game = (LIST_CENTRE_FRAME[0] - border_w,
                 LIST_CENTRE_FRAME[1] - title_h)
    mouse.move_to_game(*list_game)
    jitter_sleep(0.2)

    last_top_text: str | None = None
    stale_count = 0
    for it in range(MAX_SCROLL_ITERS):
        img = cap.grab_frame("Lineage")
        rows = ocr_list(ocr_engine, img)
        if rows:
            top_txt = rows[0][1]
            if top_txt == last_top_text:
                stale_count += 1
                if stale_count >= 2:
                    print(f"    ✗ list end reached at iter {it} "
                          f"(top stays '{top_txt}')")
                    return None
            else:
                stale_count = 0
                last_top_text = top_txt

            for row_y, text, conf in rows:
                if name_matches(target, text):
                    print(f"    ✓ found '{text}' at row y={row_y} "
                          f"(conf={conf:.2f}, after {it} iter(s) × "
                          f"{SCROLL_STEP} ticks)")
                    click_frame = (ROW_CLICK_X, row_y)
                    click_game = (click_frame[0] - border_w,
                                  click_frame[1] - title_h)
                    mouse.click_at_game(*click_game)
                    jitter_sleep(0.4)
                    return row_y
        # Per-tick wheel keeps OS-level coalescing from dropping ticks.
        for _ in range(SCROLL_STEP):
            client.wheel(-1)
            jitter_sleep(0.04)
        jitter_sleep(0.15)
    print(f"    ✗ '{target}' not found after {MAX_SCROLL_ITERS} iters")
    return None


def type_qty(client, qty: int, hwnd=None) -> None:
    """Type the digits of ``qty`` into the focused Lineage qty field.

    The 1.0 s pre-pause is load-bearing: after the row click, Lineage
    needs ~0.5-1 s to finalise the row selection and put the qty
    input into 'accepting keystrokes' state. Without this, key_tap
    fires too early and the digits go nowhere — the row is visibly
    highlighted but qty stays at 0. Verified by manual-click + script
    key_tap (worked) vs script-click + immediate key_tap (didn't)."""
    s = str(qty)
    print(f"    typing qty '{s}'")
    jitter_sleep(1.0)
    for digit in s:
        client.key_tap(digit)
        jitter_sleep(0.07)
    jitter_sleep(0.3)


def set_qty_via_increment(mouse, client, hwnd, row_y: int, qty: int,
                          border_w: int, title_h: int) -> None:
    """Set the row's qty by clicking ▲ ``qty`` times. Reliable
    workaround when key_tap into the qty input doesn't register
    (script-opened shop has a focus quirk we haven't fully diagnosed).
    Slow for big numbers — only use for small qty (≤ ~20).

    Each row in the shop list has icon + name on top, price + qty
    controls underneath: ``▲`` sits at row_y + ~25 px below the
    OCR-text centre."""
    print(f"    incrementing qty to {qty} via ▲ clicks")
    user32 = ctypes.windll.user32
    arrow_y = row_y + QTY_ARROW_Y_OFFSET
    arrow_game = (QTY_UP_ARROW_X - border_w, arrow_y - title_h)
    for i in range(qty):
        user32.SetForegroundWindow(hwnd)
        mouse.click_at_game(*arrow_game)
        jitter_sleep(0.12)
    jitter_sleep(0.3)


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
        before.save("samples/buyscrolls_01_before.png")
        fw, fh = before.size
        border_w = (fw - cw) // 2
        title_h = fh - ch - 1

        # Step 1: shop open?
        if find_shop_buy(before) is None:
            print("✗ shop window not detected — open it first.")
            client.close()
            return 1
        print("shop ✓")

        # Move cursor over list, then scroll to top.
        mouse.move_to_game(LIST_CENTRE_FRAME[0] - border_w,
                           LIST_CENTRE_FRAME[1] - title_h)
        jitter_sleep(0.2)
        print("scrolling to top…")
        scroll_to_top(client)

        # For each item: find + click + type qty.
        for i, (name, qty) in enumerate(SHOPPING_LIST, 1):
            print(f"\n[{i}/{len(SHOPPING_LIST)}] {name} × {qty}")
            row_y = find_and_click_item(name, mouse, client, ocr_engine,
                                        hwnd, border_w, title_h)
            if row_y is None:
                print(f"✗ aborting — couldn't find {name}")
                client.close()
                return 1
            type_qty(client, qty)
            cap.grab_frame("Lineage").save(
                f"samples/buyscrolls_0{i+1}_{name}_typed.png")

        # Step 5: click bottom Buy.
        print("\nclicking bottom Buy…")
        live = cap.grab_frame("Lineage")
        buy = find_shop_buy(live)
        if buy is None:
            print("✗ bottom Buy bar lost.")
            client.close()
            return 1
        bx, by, score = buy
        print(f"  bottom Buy at frame ({bx}, {by}) score={score:.3f}")
        mouse.click_at_game(bx - border_w, by - title_h)
        jitter_sleep(0.8)

        cap.grab_frame("Lineage").save("samples/buyscrolls_99_after.png")
        print("✓ saved samples/buyscrolls_*.png")

        mouse.move_to_game(640, 700)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
