"""Manual test: switch to F1 page then double-tap F6 (self-heal).

Focus the Lineage window before the countdown ends.
The character should cast the heal skill on themselves.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board_client import BoardClient, BoardClientError, jitter_sleep

PAGE_KEY = "f1"
SLOT_KEY = "f6"


def main() -> int:
    try:
        client = BoardClient.auto_detect()
    except BoardClientError as e:
        print(f"FAILED to find board: {e}", file=sys.stderr)
        return 1

    print(f"connected: {client.port}  ({client.version()})")
    print()
    print(f"Will press: {PAGE_KEY.upper()} (page switch)  then  {SLOT_KEY.upper()} x2 (self-heal)")
    print()
    print("*** 請立刻 Alt+Tab 切到遊戲視窗，不要再看這個畫面 ***")
    print()
    for n in range(10, 0, -1):
        print(f"  {n}…")
        time.sleep(1)

    print(f"  → {PAGE_KEY.upper()} (切頁)")
    client.key_tap(PAGE_KEY)
    jitter_sleep(0.3)

    print(f"  → {SLOT_KEY.upper()} (第一下)")
    client.key_tap(SLOT_KEY)
    jitter_sleep(0.20)

    print(f"  → {SLOT_KEY.upper()} (第二下)")
    client.key_tap(SLOT_KEY)

    client.close()
    print("\nDone. Did the character cast the heal skill on themselves?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
