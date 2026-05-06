"""One-shot CLI flash of the v0.6 firmware with a chosen profile.

Run with no args to list profiles; pass profile-name + COM port to flash.
Example:
    python flasher\\flash_v06.py "Logitech G502 HERO" COM7
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from profiles import PROFILES
from flash import flash_with_reset


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python flash_v06.py <profile-key> <port>")
        print("\navailable profiles:")
        for key, p in PROFILES.items():
            print(f'  {key:24s}  {p.name}  (VID:PID = {p.vid_pid})')
        return 1

    key = sys.argv[1]
    port = sys.argv[2]
    profile = PROFILES.get(key)
    if profile is None:
        print(f"unknown profile key: {key!r}")
        print(f"valid keys: {sorted(PROFILES.keys())}")
        return 1

    print(f"flashing v0.6 with profile {profile.name!r} → {port}")
    ok = flash_with_reset(profile, port)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
