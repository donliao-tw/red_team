"""One-shot: grab native + 4x crops of the debuffs / lawful zone +
a wide crop covering the area where the time icon lives (sun/moon).

Run while the character is visible in the game. We use these to:
  * compare the digit font with HP/MP templates
  * eyeball the '%' and '-' glyph shapes (new templates needed)
  * locate the time icon's bounding box for a sun/moon classifier
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap


def main() -> int:
    img = cap.grab_frame("Lineage")
    print(f"Frame: {img.size}")
    out = Path(__file__).resolve().parent.parent / "samples" / "status_zone"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()

    # 1280×960 ROIs — re-check; debuffs is a 2x2 stat icons grid.
    rois = {
        "debuffs": cap.ROI_1280x960["debuffs"],
        "lawful":  cap.ROI_1280x960["lawful"],
        # Wider crop spanning whole left-bottom pane to find time icon
        "left_pane_full": (0, 800, 320, 992),
    }

    for name, box in rois.items():
        crop = img.crop(box)
        crop.save(out / f"{name}_native.png")
        crop.resize((crop.width * 4, crop.height * 4)).save(
            out / f"{name}_4x.png")
        print(f"  {name:<16} box={box} size={crop.size}")

    # Also save the full frame for context
    img.save(out / "full_frame.png")
    print(f"Saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
