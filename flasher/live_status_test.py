"""Live status-zone test — drives the slow-loop pipeline against the
real game window and prints what each FieldReader resolves to over
~30 s. Useful to verify that defense / mdef / weight / hunger /
Lawful / time emerge with values that match in-game.

Captures the time-icon ROI as a 4× PNG on the first iteration so we
can compare against expected day/night state.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from status_reader import classify_time_of_day, make_default_readers


DURATION_S = 30
INTERVAL_S = 5


def main() -> int:
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        print("ERROR: Lineage window not found", file=sys.stderr)
        return 1
    size = cap.get_client_size(hwnd)
    print(f"Detected client size: {size}")
    if size == (1280, 960):
        rois = cap.ROI_1280x960
    elif size == (1920, 1032):
        rois = cap.ROI_1920x1032
    else:
        print(f"ERROR: unsupported size {size}", file=sys.stderr)
        return 1

    fields = ("defense", "mdef", "weight", "hunger", "lawful")
    field_rois = {f: rois[f] for f in fields if f in rois}
    if not field_rois:
        print("ERROR: status sub-ROIs missing for this resolution", file=sys.stderr)
        return 1

    print("Warming up RapidOCR (cold start ~800 ms)...")
    cap._get_ocr()

    print("Starting WGC stream...")
    streamer = cap.FrameStreamer("Lineage")
    deadline = time.monotonic() + 3.0
    while streamer.latest() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if streamer.latest() is None:
        print("ERROR: no frame", file=sys.stderr)
        streamer.stop()
        return 1

    readers = make_default_readers()
    out_dir = Path(__file__).resolve().parent.parent / "samples" / "live_status"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{DURATION_S}s @ {INTERVAL_S}s cadence — eyeball-compare to game.\n")
    header = f"  {'t':>5}"
    for f in fields:
        header += f"  {f:>9}"
    header += f"  {'time':>6}"
    print(header)
    print("-" * len(header))

    t0 = time.monotonic()
    iteration = 0
    while time.monotonic() - t0 < DURATION_S:
        iteration += 1
        loop_t = time.monotonic()
        img = streamer.latest()
        if img is None:
            time.sleep(INTERVAL_S)
            continue

        # OCR the field ROIs
        ocr = cap.ocr_rois(img, field_rois)

        row = f"  {loop_t - t0:>5.1f}"
        for f in fields:
            box = field_rois[f]
            crop_arr = np.asarray(img.crop(box))
            text = " ".join(ocr.get(f, []))
            v = readers[f].read(crop_arr, text)
            row += f"  {str(v) if v is not None else '--':>9}"

        # Time of day
        if "time_icon" in rois:
            arr = np.asarray(img.crop(rois["time_icon"]))
            tod = classify_time_of_day(arr)
            row += f"  {tod or '--':>6}"
            # Save the time icon crop on first iter for visual check
            if iteration == 1:
                Image.fromarray(arr).resize(
                    (arr.shape[1] * 6, arr.shape[0] * 6)
                ).save(out_dir / "time_icon_6x.png")

        print(row)
        elapsed = time.monotonic() - loop_t
        if elapsed < INTERVAL_S:
            time.sleep(INTERVAL_S - elapsed)

    streamer.stop()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
