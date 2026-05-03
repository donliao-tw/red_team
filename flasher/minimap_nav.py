"""Minimap-based navigation hints for Lineage.

The minimap (upper-left semi-transparent overlay) is colour-coded:
  * light grey / white → walkable floor
  * black              → wall / out-of-room
  * red triangle       → player arrow (centre)
  * blue / coloured    → other characters / items

We can use this to answer "is direction X clear for the next few
tiles?" without running into walls. Doors / holes / stairs would need
separate colour markers (sample-driven, deferred).
"""
from __future__ import annotations

import random

import numpy as np
from PIL import Image


# Minimap region in WGC frame coordinates (1280×960 client, 1282×992
# frame including 1-px border + 31-px title bar).
MINIMAP_BOX = (0, 30, 200, 160)

# Per-direction unit vector. y axis grows DOWN in screen space.
DIR_UNIT: dict[str, tuple[float, float]] = {
    "N":  (0, -1),
    "NE": (+0.71, -0.71),
    "E":  (+1, 0),
    "SE": (+0.71, +0.71),
    "S":  (0, +1),
    "SW": (-0.71, +0.71),
    "W":  (-1, 0),
    "NW": (-0.71, -0.71),
}

OPPOSITE: dict[str, str] = {
    "N": "S", "NE": "SW", "E": "W", "SE": "NW",
    "S": "N", "SW": "NE", "W": "E", "NW": "SE",
}

# Brightness threshold separating "floor" (light) from "wall" (dark).
WALL_THRESHOLD = 80


def find_arrow(frame_img: Image.Image) -> tuple[int, int] | None:
    """Locate the bright-red player arrow in the minimap zone.

    Returns (x, y) in **frame** coordinates, or None if no arrow found
    (e.g. minimap closed)."""
    arr = np.asarray(frame_img)
    x0, y0, x1, y1 = MINIMAP_BOX
    sub = arr[y0:y1, x0:x1]
    R = sub[..., 0].astype(int)
    G = sub[..., 1].astype(int)
    B = sub[..., 2].astype(int)
    red = (R > 180) & (G < 80) & (B < 80) & (R - G > 100)
    ys, xs = np.where(red)
    if len(xs) < 5:
        return None
    return int(xs.mean()) + x0, int(ys.mean()) + y0


def _sample_brightness(arr: np.ndarray, fx: int, fy: int) -> int:
    """Mean brightness of a 3×3 patch centred at (fx, fy) in frame
    coords. Returns 0 if out of bounds."""
    h, w = arr.shape[:2]
    if not (1 <= fx < w - 1 and 1 <= fy < h - 1):
        return 0
    patch = arr[fy - 1:fy + 2, fx - 1:fx + 2]
    return int(patch.mean())


def walkability_8(frame_img: Image.Image,
                  *, max_radius_px: int = 18,
                  step_px: int = 3) -> dict[str, bool]:
    """For each of 8 directions, return True if the minimap row of
    pixels along that ray averages above the wall threshold.

    A few black pixels mid-ray (anti-aliasing, NPC dots) don't kill
    walkability — we average a 3-px-wide stripe and require the mean
    to clear the threshold.
    """
    arrow = find_arrow(frame_img)
    if arrow is None:
        return {d: False for d in DIR_UNIT}

    arr = np.asarray(frame_img)
    ax, ay = arrow
    out: dict[str, bool] = {}
    for direction, (dx, dy) in DIR_UNIT.items():
        samples = []
        for r in range(step_px, max_radius_px + 1, step_px):
            fx = int(round(ax + dx * r))
            fy = int(round(ay + dy * r))
            samples.append(_sample_brightness(arr, fx, fy))
        if not samples:
            out[direction] = False
            continue
        # Two requirements:
        #   * mean brightness clears the threshold (mostly floor)
        #   * no single sample is *very* dark (no wall blocking the path)
        out[direction] = (
            sum(samples) / len(samples) >= WALL_THRESHOLD
            and min(samples) >= 30
        )
    return out


def pick_random_walkable(walkable: dict[str, bool],
                         *, avoid: str | None = None) -> str | None:
    """Choose a random walkable direction. Avoids the direction we
    came from to prevent immediate backtracking."""
    forbidden = OPPOSITE.get(avoid) if avoid else None
    cands = [d for d, ok in walkable.items()
             if ok and d != forbidden]
    if not cands:
        # Fallback: include backtrack direction so we don't deadlock
        cands = [d for d, ok in walkable.items() if ok]
    if not cands:
        return None
    return random.choice(cands)
