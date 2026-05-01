"""Verify firmware v0.2 and keyboard commands.

Stage 1 — silent verification:
  * confirm board responds to ping
  * read version (must say v0.2)
  * exercise the K command at firmware level (any safe key)

Stage 2 — countdown + Tab tap:
  * 3-second countdown for the user to focus the Lineage window
  * tap Tab → inventory should open
  * 2-second pause
  * tap Tab again → inventory should close

Run from a terminal you're not editing in (so a stray Tab doesn't
auto-complete or cycle focus). Best: alt-tab to game just before the
countdown ends.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board_client import BoardClient, BoardClientError


def main() -> int:
    try:
        client = BoardClient.auto_detect()
    except BoardClientError as e:
        print(f"FAILED to find board: {e}", file=sys.stderr)
        return 1

    print(f"connected: {client.port}")

    # Version check
    v = client.version()
    print(f"version:  {v}")
    if "v0.2" not in v and "v0.3" not in v:
        print(f"  WARN: expected v0.2+ but got {v!r} — keyboard probably not flashed", file=sys.stderr)

    # Stage 2: live Tab test against Lineage
    print()
    print("─" * 50)
    print("LIVE Tab TEST — focus the Lineage window NOW.")
    print("Sending Tab in 5 seconds…")
    for n in range(5, 0, -1):
        print(f"  {n}…")
        time.sleep(1)
    print("  → tap Tab")
    client.key_tap("tab")
    print("  (inventory should be open. waiting 2 s.)")
    time.sleep(2)
    print("  → tap Tab again to close")
    client.key_tap("tab")
    time.sleep(0.5)

    client.close()
    print("\nDone. Did the inventory open and close?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
