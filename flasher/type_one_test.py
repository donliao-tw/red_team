"""Minimal typing test — assumes the user has manually clicked a
shop row that's now selected. Script just sends a single
key_tap("1") and waits. If that registers as qty=1, key_tap is
fine and our row-click is what breaks focus. If qty stays 0,
key_tap itself isn't reaching Lineage.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board_client import BoardClient, BoardClientError, jitter_sleep


def main() -> int:
    try:
        client = BoardClient.auto_detect()
    except BoardClientError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"Board: {client.port}, {client.version()}")
    print("\nYou should have already clicked a shop row (highlighted).")
    print("Counting down 3 seconds, then sending key_tap('1')…")
    for n in (3, 2, 1):
        print(f"  {n}…")
        time.sleep(1.0)

    print("→ key_tap('1')")
    client.key_tap("1")
    jitter_sleep(0.3)
    print("done. Check if qty changed to 1 in the shop window.")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
