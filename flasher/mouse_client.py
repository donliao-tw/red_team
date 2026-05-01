"""Backwards-compat shim — board_client.py is the canonical module
now that the firmware drives both mouse and keyboard. New code should
import ``BoardClient`` from ``board_client`` directly. Existing imports
of ``MouseClient`` still resolve through this module.
"""
from board_client import (  # noqa: F401
    HID_MAX,
    HID_MIN,
    BoardClient as MouseClient,
    BoardClientError as MouseClientError,
    PortCandidate,
)
