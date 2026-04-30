"""Throwaway: connect to Lineage, OCR HP/MP every 500ms, print raw + parsed.

Run while regenerating in-game, then eyeball-compare each line against the
HP/MP shown in the game. Goal is to confirm whether RapidOCR itself is
100% accurate, or whether it occasionally mis-reads — that determines
whether the off-by-1 is architectural (fast loop overwriting mid OCR) or
intrinsic to OCR (needs custom digit reader / voting).

Output columns: timestamp | raw hp_text | parsed | raw mp_text | parsed
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Make the flasher package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap


N_CAPTURES = 15
INTERVAL_S = 0.5


def main() -> int:
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        print("ERROR: Lineage window not found", file=sys.stderr)
        return 1

    size = cap.get_client_size(hwnd)
    print(f"Detected client size: {size[0]}×{size[1]}")
    if size == (1280, 960):
        rois = {k: v for k, v in cap.ROI_1280x960.items()
                if k in ("hp_text", "mp_text")}
    elif size == (1920, 1032):
        rois = {k: v for k, v in cap.ROI_1920x1032.items()
                if k in ("hp_text", "mp_text")}
    else:
        print(f"ERROR: unsupported size {size}", file=sys.stderr)
        return 1

    out_dir = Path(__file__).resolve().parent.parent / "samples" / "ocr_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    # wipe any prior run so we don't mix stale frames in
    for old in out_dir.glob("cap_*.png"):
        old.unlink()

    print("Warming up OCR (cold start ~800ms)...")
    cap._get_ocr()

    print("Starting WGC stream...")
    streamer = cap.FrameStreamer("Lineage")

    # Wait for first frame
    deadline = time.monotonic() + 3.0
    while streamer.latest() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if streamer.latest() is None:
        print("ERROR: no frame after 3s", file=sys.stderr)
        streamer.stop()
        return 1

    print(f"\nCapturing {N_CAPTURES} frames at {INTERVAL_S}s interval. "
          f"Eyeball-compare each row vs in-game HP/MP.\n")
    print(f"{'#':>3} {'t(s)':>6}  {'hp_raw':<28} {'hp_parsed':<14} "
          f"{'mp_raw':<28} {'mp_parsed':<14}")
    print("-" * 110)

    hp_max_seen = None
    mp_max_seen = None
    t0 = time.monotonic()

    for i in range(N_CAPTURES):
        t = time.monotonic() - t0
        img = streamer.latest()
        if img is None:
            print(f"{i+1:>3} {t:>6.2f}  <no frame>")
            time.sleep(INTERVAL_S)
            continue

        # Save crops up-scaled 4× so my (Claude's) image-read sees the
        # digits clearly. Native crop is ~210×37 — too small to read.
        hp_crop = img.crop(rois["hp_text"])
        mp_crop = img.crop(rois["mp_text"])
        hp_crop.resize((hp_crop.width * 4, hp_crop.height * 4)).save(
            out_dir / f"cap_{i+1:02d}_hp.png")
        mp_crop.resize((mp_crop.width * 4, mp_crop.height * 4)).save(
            out_dir / f"cap_{i+1:02d}_mp.png")

        ocr = cap.ocr_rois(img, rois)
        hp_lines = ocr.get("hp_text", [])
        mp_lines = ocr.get("mp_text", [])

        hp_parsed = cap.parse_hpmp(hp_lines, expected_max=hp_max_seen)
        mp_parsed = cap.parse_hpmp(mp_lines, expected_max=mp_max_seen)
        if hp_parsed:
            hp_max_seen = hp_parsed[1]
        if mp_parsed:
            mp_max_seen = mp_parsed[1]

        hp_raw = " | ".join(hp_lines)[:27]
        mp_raw = " | ".join(mp_lines)[:27]
        hp_str = f"{hp_parsed[0]}/{hp_parsed[1]}" if hp_parsed else "--"
        mp_str = f"{mp_parsed[0]}/{mp_parsed[1]}" if mp_parsed else "--"

        print(f"{i+1:>3} {t:>6.2f}  {hp_raw:<28} {hp_str:<14} "
              f"{mp_raw:<28} {mp_str:<14}")

        time.sleep(INTERVAL_S)

    streamer.stop()
    print("\nDone. If every row's hp_parsed matches the in-game number, "
          "OCR is sound and the panel's off-by-1 is fast-loop overwrite. "
          "If some rows are wrong, OCR itself needs hardening.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
