"""Ping the hid_mouse Arduino. Run before any movement work to confirm:
  * board is connected
  * firmware is loaded and responding
  * ASCII protocol round-trip works at 115200

Usage:
    python flasher/mouse_ping_test.py             # auto-detect + ping
    python flasher/mouse_ping_test.py COM7        # ping a specific port
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mouse_client import MouseClient, MouseClientError


def main() -> int:
    print("Visible USB COM ports:")
    for c in MouseClient.list_candidates():
        print(f"  {c.device:>6}  {c.vid_pid}  {c.description}")
    print()

    if len(sys.argv) > 1:
        port = sys.argv[1]
        print(f"Connecting to {port}...")
        try:
            client = MouseClient(port)
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED: {e}")
            return 1
    else:
        print("Auto-detecting hid_mouse board (pinging each port)...")
        try:
            client = MouseClient.auto_detect()
        except MouseClientError as e:
            print(f"  FAILED: {e}")
            print("\nIs the Arduino plugged in and flashed?")
            return 1

    print(f"Connected on {client.port}")

    # Round-trip latency
    n = 20
    t0 = time.perf_counter()
    ok = 0
    for _ in range(n):
        if client.ping():
            ok += 1
    dt = (time.perf_counter() - t0) / n * 1000
    print(f"  ping: {ok}/{n} OK, {dt:.1f} ms/round-trip")

    try:
        v = client.version()
        print(f"  version: {v}")
    except MouseClientError as e:
        print(f"  version: error: {e}")

    client.close()
    print("\nOK — wire protocol is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
