"""Template-match digit reader for the Lineage HP/MP bar text.

Each character occupies a 10×10 binary cell at a fixed grid position
in the native crop. We match each cell against a small template library
(0-9, '/', ':') and pick the lowest Hamming distance.

The grid layout (HP, 1280×960 capture):
  cell 0 = x=110  → 'H'
  cell 1 = x=120  → 'P'
  cell 2 = x=130  → ':'
  cell 3 = x=140  → cur digit 1 (left)
  cell 4 = x=150  → cur digit 2 / blank
  cell 5 = x=160  → cur digit 3 / blank
  cell 6 = x=170  → '/'
  cell 7 = x=180  → max digit 1
  cell 8 = x=190  → max digit 2
  cell 9 = x=200  → max digit 3

Cur is right-justified inside cells 3-5 — when cur is 2 digits (e.g. "92")
the leftmost cell may be empty (or contain stray AA).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image


CELL_W = 10
TEXT_BAND = (9, 19)
START_X = 110
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def load_templates() -> dict[str, np.ndarray]:
    """HP/MP bar text templates (10×10 binary, fixed-grid)."""
    out = {}
    for f in sorted(TEMPLATE_DIR.glob("glyph_*.png")):
        name = f.stem.replace("glyph_", "")
        if name == "slash":
            name = "/"
        elif name == "colon":
            name = ":"
        arr = np.asarray(Image.open(f).convert("L")) > 127
        out[name] = arr
    return out




def hp_text_mask(arr: np.ndarray) -> np.ndarray:
    """White-on-red text mask for HP bar."""
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    return (R > 240) & (G > 200) & (B > 200)


def mp_text_mask(arr: np.ndarray) -> np.ndarray:
    """Blue-tinted-white text mask for MP bar (purple background).

    Tight B>240 — only the bright glyph core, so stroke widths line up
    with HP templates (the dim halo would inflate the strokes by 1 col
    per side and the templates wouldn't match).
    """
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    return (B > 240) & (R > 150) & (G > 150)


def extract_cell(mask: np.ndarray, cell_idx: int) -> np.ndarray:
    """Pull one cell's binary slice from a full crop's mask."""
    y0, y1 = TEXT_BAND
    x0 = START_X + cell_idx * CELL_W
    return mask[y0:y1, x0:x0 + CELL_W]


def match_cell(cell: np.ndarray, templates: dict[str, np.ndarray],
               *, candidates: str | None = None) -> tuple[str, int]:
    """Return (best_name, hamming_distance). If cell has no text, returns (' ', 0)."""
    if cell.sum() < 2:
        return (" ", 0)
    best_name = "?"
    best_dist = 10**9
    for name, tpl in templates.items():
        if candidates is not None and name not in candidates:
            continue
        d = int(np.logical_xor(cell, tpl).sum())
        if d < best_dist:
            best_dist = d
            best_name = name
    return (best_name, best_dist)


def read_bar_text(crop_arr: np.ndarray, templates: dict[str, np.ndarray],
                  *, mp: bool = False) -> tuple[int, int] | None:
    """Read (cur, max) from an HP or MP bar crop.

    Bar text uses a fixed 10-px char grid. HP and MP have different
    grid origins (HP: x=110, MP: x=8) and different text alignment
    (HP right-aligns the whole 'HP:CCC/MMM' string within the bar; MP
    left-aligns it). We sidestep both by *finding* the '/' cell via
    template match and reading digits on either side until we hit a
    non-digit (':' or empty).
    """
    if mp:
        mask = mp_text_mask(crop_arr)
        cells = [_extract_cell_at(mask, 8 + i * CELL_W) for i in range(10)]
    else:
        mask = hp_text_mask(crop_arr)
        cells = [_extract_cell_at(mask, 110 + i * CELL_W) for i in range(10)]

    # Find '/' cell. Try every position; pick the first that matches
    # cleanly. (The slash glyph is sparse so its hamming distance to a
    # digit cell is always > 10 — false positives don't happen.)
    slash_idx = -1
    for i in range(10):
        c, d = match_cell(cells[i], templates, candidates="/")
        if c == "/" and d <= 4:
            slash_idx = i
            break
    if slash_idx < 0:
        return None

    # Max: digits to the right of '/', stop at empty cell.
    max_digits = []
    for i in range(slash_idx + 1, 10):
        cell = cells[i]
        if cell.sum() < 2:
            break
        c, d = match_cell(cell, templates, candidates="0123456789")
        if d > 6:
            return None
        max_digits.append(c)
    if not max_digits:
        return None

    # Cur: digits to the left of '/', walking back to the colon.
    cur_digits = []
    for i in range(slash_idx - 1, -1, -1):
        cell = cells[i]
        if cell.sum() < 2:
            break
        c, d = match_cell(cell, templates, candidates="0123456789")
        if d > 6:
            break  # hit the colon (or 'P'/'M'/'H' prefix)
        cur_digits.append(c)
    if not cur_digits:
        return None

    return int("".join(reversed(cur_digits))), int("".join(max_digits))


def _extract_cell_at(mask: np.ndarray, x0: int) -> np.ndarray:
    y0, y1 = TEXT_BAND
    return mask[y0:y1, x0:x0 + CELL_W]


def read_hp(crop_arr: np.ndarray, templates: dict[str, np.ndarray]
            ) -> tuple[int, int] | None:
    return read_bar_text(crop_arr, templates, mp=False)


def read_mp(crop_arr: np.ndarray, templates: dict[str, np.ndarray]
            ) -> tuple[int, int] | None:
    return read_bar_text(crop_arr, templates, mp=True)


# Status-zone readers (defense / mdef / weight / hunger / lawful + time
# of day) live in flasher/status_reader.py — they use OCR + agreement
# validation + a bitmap-hash cache instead of the fixed-grid template
# match used here, because the status zone has variable-width digits,
# decorative borders and multiple sub-cells with different alignments
# that a single grid policy can't handle reliably.
