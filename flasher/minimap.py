"""Detect / open the in-game minimap (semi-transparent map at the
upper-left of the Lineage client area).

Signal: when open, a small bright-red player arrow sits in the middle
of the minimap. Closed state has zero red pixels in that screen
region. Detection is just "count red pixels in the minimap zone".

Toggle: Ctrl+M opens/closes the minimap (per user spec).
"""
from __future__ import annotations

import time

import numpy as np
from PIL import Image

from board_client import BoardClient, jitter_sleep


# Minimap occupies upper-left of the 1280×960 client; frame coords
# include +1 px border + 31 px title bar at the top of the WGC capture.
MINIMAP_ZONE = (0, 30, 200, 160)  # frame coords (x0, y0, x1, y1)
MINIMAP_RED_THRESHOLD = 20  # ≥ this many red px = minimap visible


def count_arrow_pixels(frame_img: Image.Image) -> int:
    """Number of bright-red pixels in the minimap zone — only the
    player-arrow icon hits this colour band, so it doubles as an
    'is the minimap on screen' signal."""
    arr = np.asarray(frame_img)
    x0, y0, x1, y1 = MINIMAP_ZONE
    sub = arr[y0:y1, x0:x1]
    R = sub[..., 0].astype(int)
    G = sub[..., 1].astype(int)
    B = sub[..., 2].astype(int)
    red = (R > 180) & (G < 80) & (B < 80) & (R - G > 100)
    return int(red.sum())


def is_minimap_open(frame_img: Image.Image) -> bool:
    return count_arrow_pixels(frame_img) >= MINIMAP_RED_THRESHOLD


def ensure_minimap_open(client: BoardClient, capture_fn,
                        *, focus_hwnd: int | None = None) -> bool:
    """Verify the minimap is open; if not, send a SINGLE Ctrl+M.

    **Important** (per user spec):
      * Ctrl+M toggles the small mini-map.
      * Pressing Ctrl+M twice in a row opens the *big map* — a
        completely different, mostly-fullscreen UI we don't want.
      * Therefore this function only sends Ctrl+M *once*, and
        if the small mini-map still isn't visible afterwards it
        gives up and returns False rather than spamming the key.
      * For closing, use ``close_minimap`` (sends ESC).

    ``capture_fn`` is a no-arg callable returning the current PIL frame
    (typically ``lambda: cap.grab_frame('Lineage')``). ``focus_hwnd``
    optionally focuses that window so the keyboard reaches Lineage.
    """
    if focus_hwnd is not None:
        import ctypes
        ctypes.windll.user32.SetForegroundWindow(focus_hwnd)
        jitter_sleep(0.2)

    img = capture_fn()
    if count_arrow_pixels(img) >= MINIMAP_RED_THRESHOLD:
        return True

    # key_combo holds Ctrl ~300 ms before tapping M (Lineage requires
    # this) and jitters every interval — see BoardClient.key_combo.
    client.key_combo("ctrl", "m")
    jitter_sleep(0.4)
    img = capture_fn()
    return count_arrow_pixels(img) >= MINIMAP_RED_THRESHOLD


def close_minimap(client: BoardClient,
                  *, focus_hwnd: int | None = None) -> None:
    """Close the small mini-map (or any modal it's overlaying) by
    sending ESC. Per user spec ESC is the safe close key — Ctrl+M would
    risk toggling into the big-map state if pressed when something
    else is open."""
    if focus_hwnd is not None:
        import ctypes
        ctypes.windll.user32.SetForegroundWindow(focus_hwnd)
        jitter_sleep(0.2)
    client.key_tap("esc")
