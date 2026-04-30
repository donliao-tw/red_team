"""Extract per-glyph binary templates from captured HP/MP samples.

Output: flasher/templates/glyph_<name>.png — 10×10 binary masks of each
character's text-band region (y=9..18 of the native HP/MP crop).

Sources determined empirically from samples/glyphs/ frames:
  '0' ← any HP frame, cell 190 (max '0')
  '1' ← any HP frame, cell 140 (cur first digit, always '1' in this run)
  '2' ← cap_21 (HP:125), cell 150
  '3' ← any HP frame, cell 180 (max first digit '3')
  '4' ← cap_05 (HP:114), cell 160
  '5' ← cap_21 (HP:125), cell 160
  '6' ← any MP frame (MP:116), cell 160
  '7' ← cap_27 (HP:127), cell 160
  '8' ← any HP frame, cell 200 (max last digit '8')
  '9' ← cap_16 (HP:119), cell 160
  '/' ← any HP frame, cell 170
  ':' ← any HP frame, cell 130
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image


CELL_W = 10
TEXT_BAND = (9, 19)   # y range
START_X = 110         # first char cell
DIR = Path(__file__).resolve().parent.parent / "samples" / "glyphs"
OUT = Path(__file__).resolve().parent / "templates"


def hp_mask(img_arr: np.ndarray) -> np.ndarray:
    R, G, B = img_arr[..., 0], img_arr[..., 1], img_arr[..., 2]
    return (R > 240) & (G > 200) & (B > 200)


def mp_mask(img_arr: np.ndarray) -> np.ndarray:
    """MP text is blue-tinted white on purple. Tight B>240 to match
    only the bright core (so stroke widths match HP templates)."""
    R, G, B = img_arr[..., 0], img_arr[..., 1], img_arr[..., 2]
    return (B > 240) & (R > 150) & (G > 150)


def extract(file_name: str, cell_idx: int, *,
            start_x: int = START_X,
            mask_fn=hp_mask) -> np.ndarray:
    """Extract the binary mask for one cell from one frame."""
    img = Image.open(DIR / file_name)
    arr = np.asarray(img)
    mask = mask_fn(arr)
    x0 = start_x + cell_idx * CELL_W
    y0, y1 = TEXT_BAND
    return mask[y0:y1, x0:x0 + CELL_W]


def save_template(name: str, mask: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    img.save(OUT / f"glyph_{name}.png")
    print(f"  glyph_{name}: {mask.sum()} px set, {mask.shape}")


def main() -> int:
    # (name, source_file, cell_index, start_x, mask_fn)
    sources = [
        ("0",     "cap_01_hp_native.png", 8, 110, hp_mask),
        ("1",     "cap_01_hp_native.png", 3, 110, hp_mask),
        ("2",     "cap_21_hp_native.png", 4, 110, hp_mask),
        ("3",     "cap_01_hp_native.png", 7, 110, hp_mask),
        ("4",     "cap_05_hp_native.png", 5, 110, hp_mask),
        ("5",     "cap_21_hp_native.png", 5, 110, hp_mask),
        # '6' from MP "MP:116/116", cell 5 (third digit in "116"). MP grid
        # starts at x=8 and uses a tighter B-channel mask.
        ("6",     "cap_01_mp_native.png", 5,   8, mp_mask),
        ("7",     "cap_27_hp_native.png", 5, 110, hp_mask),
        ("8",     "cap_01_hp_native.png", 9, 110, hp_mask),
        ("9",     "cap_16_hp_native.png", 5, 110, hp_mask),
        ("slash", "cap_01_hp_native.png", 6, 110, hp_mask),
        ("colon", "cap_01_hp_native.png", 2, 110, hp_mask),
    ]
    print(f"Output dir: {OUT}")
    for name, src, idx, sx, mf in sources:
        m = extract(src, idx, start_x=sx, mask_fn=mf)
        save_template(name, m)
        # ascii preview
        for row in m:
            print("    " + ''.join('#' if v else '.' for v in row))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
