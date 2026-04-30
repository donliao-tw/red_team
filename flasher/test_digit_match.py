"""Validate the template-match digit reader against captured frames.

For each cap_NN_hp_native.png in samples/glyphs/, run the reader and
print: frame | parsed string | (cur, max) | per-cell hamming distances.

Anything where the OCR-truth disagrees, or any cell with hamming dist
>= some threshold, gets flagged so we can iterate on templates.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from digit_match import load_templates, read_hp, read_mp


GLYPH_DIR = Path(__file__).resolve().parent.parent / "samples" / "glyphs"


def main() -> int:
    templates = load_templates()
    print(f"Loaded {len(templates)} templates: {sorted(templates.keys())}")
    print()

    print("HP bars:")
    print(f"  {'frame':<10} {'(cur, max)':<14}")
    bad = 0
    files = sorted(GLYPH_DIR.glob("cap_*_hp_native.png"))
    for f in files:
        arr = np.asarray(Image.open(f))
        result = read_hp(arr, templates)
        flag = "" if result else " <<< FAIL"
        if not result:
            bad += 1
        print(f"  {f.stem[:10]:<10} {str(result):<14}{flag}")

    print()
    print("MP bars:")
    print(f"  {'frame':<10} {'(cur, max)':<14}")
    files = sorted(GLYPH_DIR.glob("cap_*_mp_native.png"))
    for f in files[:5]:  # MP is constant 116/116, sample first 5
        arr = np.asarray(Image.open(f))
        result = read_mp(arr, templates)
        flag = "" if result else " <<< FAIL"
        if not result:
            bad += 1
        print(f"  {f.stem[:10]:<10} {str(result):<14}{flag}")

    print()
    print(f"failures: {bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
