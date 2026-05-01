"""End-to-end gold-read test.

Convention (per user's design): the gold pile must be in the
top-left inventory slot. We detect "gold visible" by counting
yellow-gold pixels in slot 1's screen-space zone. If gold isn't
visible we tap Tab once (toggles inventory) and re-check; if still
not visible we bail rather than spam Tab.

Pipeline:
  1. Focus Lineage window (SetForegroundWindow)
  2. Capture frame, count gold pixels in slot 1 zone
  3. If absent → key_tap('tab') → wait → recapture → recount
  4. Smooth-move cursor to slot 1 centre (relative-delta firmware
     v0.4+, so Lineage's hover-tooltip system reacts)
  5. Wait for tooltip render, capture, OCR
  6. Parse "金幣 (NNNN)" → integer
  7. Park cursor away (so tooltip vanishes); leave inventory state
     as-is (don't auto-close — user's preference)
"""
from __future__ import annotations

import ctypes
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from board_client import BoardClient, BoardClientError
from human_mouse import HumanMouse
from window_mapper import MouseAccelerationOff, get_mouse_acceleration_settings


# Gold slot 1 (top-left of inventory) — measured from samples/inventory_gold.png:
#   yellow-gold pixel centroid: frame (1006, 98) = game (1005, 67)
#   bbox: frame x=984..1029, y=83..119  (slot is ~46×37 px)
# These are FRAME coords (the WGC capture includes 1-px border + 31-px title bar).
SLOT1_GAME_XY = (1005, 67)
SLOT1_GOLD_ZONE = (950, 60, 1030, 130)   # frame-space; where to count yellow
GOLD_TOOLTIP_ROI = (965, 130, 1085, 165)  # frame-space; tooltip OCR area
PARK_GAME_XY = (640, 480)

GOLD_PIXEL_THRESHOLD = 100  # >100 yellow px in slot zone = gold visible


def count_gold_pixels(frame_img: Image.Image) -> int:
    """Count yellow-gold pixels in slot 1's frame-space zone. Closed
    inventory yields 0; open inventory with gold yields ~700+."""
    arr = np.asarray(frame_img)
    x0, y0, x1, y1 = SLOT1_GOLD_ZONE
    sub = arr[y0:y1, x0:x1]
    R, G, B = sub[..., 0].astype(int), sub[..., 1].astype(int), sub[..., 2].astype(int)
    gold = (R > 150) & (G > 130) & (B < 50) & (R > B + 100)
    return int(gold.sum())


def is_gold_visible(frame_img: Image.Image) -> bool:
    return count_gold_pixels(frame_img) >= GOLD_PIXEL_THRESHOLD


def ensure_gold_visible(client: BoardClient, hwnd: int,
                        *, max_attempts: int = 2) -> bool:
    """Capture frames in a Tab-and-recheck loop. Returns True once gold
    is visible, False if `max_attempts` Tab toggles fail. Always focuses
    Lineage first so Tab actually reaches the game."""
    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    img = cap.grab_frame("Lineage")
    px = count_gold_pixels(img)
    print(f"  gold-pixel count (initial): {px}")
    if px >= GOLD_PIXEL_THRESHOLD:
        return True

    for attempt in range(1, max_attempts + 1):
        print(f"  inventory not showing gold; tap Tab (attempt {attempt})…")
        client.key_tap("tab")
        time.sleep(0.5)  # render delay
        img = cap.grab_frame("Lineage")
        px = count_gold_pixels(img)
        print(f"  gold-pixel count: {px}")
        if px >= GOLD_PIXEL_THRESHOLD:
            return True

    return False


def parse_gold(text: str) -> int | None:
    """Pull the integer from OCR results like '金幣 (4,681)' or '金 4,681'."""
    m = re.search(r"\(?([\d,]{1,15})\)?", text)
    if m is None:
        return None
    raw = m.group(1).replace(",", "")
    if not raw.isdigit():
        return None
    v = int(raw)
    return v if 0 <= v <= 2_000_000_000 else None


def main() -> int:
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        print("ERROR: Lineage window not found", file=sys.stderr)
        return 1
    print(f"Lineage hwnd={hwnd}, client={cap.get_client_size(hwnd)}")

    try:
        client = BoardClient.auto_detect()
    except BoardClientError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"Board: {client.port}, {client.version()}")

    mouse = HumanMouse(client, hwnd)

    print("Warming OCR…")
    cap._get_ocr()

    orig_accel = get_mouse_acceleration_settings()
    print(f"Mouse settings (orig): thresh={orig_accel[:2]} accel={orig_accel[2]}")

    # Acceleration off → linear deltas → no overshoot. Restored at exit.
    with MouseAccelerationOff():
        print("Ensuring inventory is open with gold visible…")
        if not ensure_gold_visible(client, hwnd):
            print("FAIL: couldn't get gold visible after Tab retries",
                  file=sys.stderr)
            client.close()
            return 1
        print("  gold visible ✓")

        print(f"Smooth-move to gold slot at game {SLOT1_GAME_XY}…")
        t0 = time.perf_counter()
        mouse.hover_at_game(*SLOT1_GAME_XY, hover_ms=800)
        print(f"  arrived in {(time.perf_counter() - t0) * 1000:.0f} ms")

        print("Capturing tooltip…")
        img = cap.grab_frame("Lineage")
        img.save("samples/gold_read_full.png")
        crop = img.crop(GOLD_TOOLTIP_ROI)
        crop.resize((crop.width * 4, crop.height * 4)).save(
            "samples/gold_read_tooltip_4x.png"
        )

        ocr = cap.ocr_rois(img, {"gold": GOLD_TOOLTIP_ROI})
        text = " ".join(ocr.get("gold", []))
        print(f"  OCR raw: {ocr.get('gold')!r}")
        print(f"  joined:  {text!r}")

        value = parse_gold(text)
        if value is None:
            print("  parse FAILED")
        else:
            print(f"  GOLD = {value:,}")

        print(f"Parking cursor at {PARK_GAME_XY}…")
        mouse.move_to_game(*PARK_GAME_XY)

    print("Mouse acceleration restored.")
    client.close()
    print("\nDone.")
    return 0 if value is not None else 1


if __name__ == "__main__":
    sys.exit(main())
