"""Capture native + 4x HP/MP text crops for template-match digit reader.

Run while in low-HP / mid-HP / max-HP states so we get every glyph 0-9
plus '/' and ':'. Output goes to samples/glyphs/:
    cap_NN_hp_native.png   (~210×37, used to extract templates)
    cap_NN_hp_4x.png       (~840×148, used for me to read coordinates)
    cap_NN_mp_native.png
    cap_NN_mp_4x.png

No OCR — pure capture, ~30 frames in ~15 seconds.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap


N_CAPTURES = 30
INTERVAL_S = 0.5


def main() -> int:
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        print("ERROR: Lineage window not found", file=sys.stderr)
        return 1

    size = cap.get_client_size(hwnd)
    print(f"Detected client size: {size[0]}x{size[1]}")
    if size == (1280, 960):
        rois = cap.ROI_1280x960
    elif size == (1920, 1032):
        rois = cap.ROI_1920x1032
    else:
        print(f"ERROR: unsupported size {size}", file=sys.stderr)
        return 1

    out_dir = Path(__file__).resolve().parent.parent / "samples" / "glyphs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("cap_*.png"):
        old.unlink()

    print("Starting WGC stream...")
    streamer = cap.FrameStreamer("Lineage")

    deadline = time.monotonic() + 3.0
    while streamer.latest() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if streamer.latest() is None:
        print("ERROR: no frame after 3s", file=sys.stderr)
        streamer.stop()
        return 1

    print(f"Capturing {N_CAPTURES} frames at {INTERVAL_S}s interval...")
    for i in range(N_CAPTURES):
        img = streamer.latest()
        if img is None:
            time.sleep(INTERVAL_S)
            continue
        for name in ("hp_text", "mp_text"):
            crop = img.crop(rois[name])
            crop.save(out_dir / f"cap_{i+1:02d}_{name.split('_')[0]}_native.png")
            crop.resize(
                (crop.width * 4, crop.height * 4)
            ).save(out_dir / f"cap_{i+1:02d}_{name.split('_')[0]}_4x.png")
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{N_CAPTURES}")
        time.sleep(INTERVAL_S)

    streamer.stop()
    print(f"\nDone. Files in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
