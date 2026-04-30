"""Live HP/MP template-match validator.

Run while in-game. Reads HP/MP at 5 Hz for 30 seconds, prints each
reading with a millisecond timestamp. Eyeball-compare against the game.
This validates 2-digit and 1-digit cur cases not covered by the
recorded glyph captures.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture as cap
from digit_match import load_templates, read_hp, read_mp


DURATION_S = 30
INTERVAL_S = 0.2


def main() -> int:
    hwnd = cap.find_game_window("Lineage")
    if hwnd is None:
        print("ERROR: Lineage window not found", file=sys.stderr)
        return 1
    size = cap.get_client_size(hwnd)
    if size == (1280, 960):
        rois = cap.ROI_1280x960
    elif size == (1920, 1032):
        rois = cap.ROI_1920x1032
    else:
        print(f"ERROR: unsupported size {size}", file=sys.stderr)
        return 1

    templates = load_templates()
    print(f"Loaded templates: {sorted(templates.keys())}")
    print("Connecting WGC stream...")

    streamer = cap.FrameStreamer("Lineage")
    deadline = time.monotonic() + 3.0
    while streamer.latest() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if streamer.latest() is None:
        print("ERROR: no frame after 3s", file=sys.stderr)
        streamer.stop()
        return 1

    hp_box = rois["hp_text"]
    mp_box = rois["mp_text"]

    out = Path(__file__).resolve().parent.parent / "samples" / "live_test"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("tick_*.png"):
        old.unlink()

    print(f"\nReading at 5 Hz for {DURATION_S}s, saving HP/MP crops every "
          "1 s for verification.\n")
    print(f"{'t(s)':>6}  {'HP':<14} {'MP':<14}  {'us/read':>9}  {'saved':<5}")
    print("-" * 70)

    t0 = time.monotonic()
    end = t0 + DURATION_S
    last_save_t = -10.0
    save_idx = 0
    while time.monotonic() < end:
        loop_t = time.monotonic()
        img = streamer.latest()
        if img is None:
            time.sleep(INTERVAL_S)
            continue
        hp_crop = img.crop(hp_box)
        mp_crop = img.crop(mp_box)
        m_t0 = time.perf_counter()
        hp_arr = np.asarray(hp_crop)
        mp_arr = np.asarray(mp_crop)
        hp = read_hp(hp_arr, templates)
        mp = read_mp(mp_arr, templates)
        m_us = (time.perf_counter() - m_t0) * 1e6
        hp_s = f"{hp[0]}/{hp[1]}" if hp else "--"
        mp_s = f"{mp[0]}/{mp[1]}" if mp else "--"

        save_marker = ""
        if loop_t - last_save_t >= 1.0:
            save_idx += 1
            last_save_t = loop_t
            tag = f"tick_{save_idx:02d}_t{loop_t-t0:04.1f}s"
            hp_crop.resize((hp_crop.width * 4, hp_crop.height * 4)).save(
                out / f"{tag}_hp_4x_{hp_s.replace('/', '_')}.png")
            mp_crop.resize((mp_crop.width * 4, mp_crop.height * 4)).save(
                out / f"{tag}_mp_4x_{mp_s.replace('/', '_')}.png")
            save_marker = f"#{save_idx:02d}"

        print(f"{loop_t - t0:>6.2f}  {hp_s:<14} {mp_s:<14}  {m_us:>7.0f}  {save_marker}")
        elapsed = time.monotonic() - loop_t
        if elapsed < INTERVAL_S:
            time.sleep(INTERVAL_S - elapsed)

    streamer.stop()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
