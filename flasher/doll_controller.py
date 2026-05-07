"""Doll (娃娃) heal controller — self-heal only.

Watches the HP signal from GameMonitor and fires the configured heal
skill via the Arduino HID when the HP% crosses a threshold with the
configured probability.

Page-switch (F1/F2/F3) is pressed ONCE when the controller starts.
Each heal fires the slot key twice (double-tap = self-target in Lineage).
"""
from __future__ import annotations

import random
import time

from PySide6 import QtCore


class DollHealController(QtCore.QObject):
    """QObject so it can be the target of Qt signals from GameMonitor."""

    healed  = QtCore.Signal(str)   # emitted after each successful heal

    COOLDOWN_BASE    = 0.5   # seconds between heal checks
    COOLDOWN_JITTER  = 0.08  # fractional ± jitter on cooldown

    def __init__(self, client, settings: dict,
                 parent: QtCore.QObject | None = None) -> None:
        """
        client   — BoardClient instance (or None for dry-run).
        settings — dict with keys:
            "heal_skill" : "P1-F5" style hotkey string
            "heal_table" : [(hp_threshold%, probability%), ...]
                           evaluated top-to-bottom; first match wins.
        """
        super().__init__(parent)
        self._client  = client
        self._skill   = settings.get("heal_skill", "P1-F6")
        raw_table     = settings.get("heal_table", [])
        self._table   = sorted(raw_table, key=lambda x: -x[0])
        self._last_fire: float = 0.0
        self._page_key, self._slot_key = self._parse_skill(self._skill)
        self._page_switched = False   # switch page on first fire, not at init

    # ── public slot ─────────────────────────────────────────────────

    @QtCore.Slot(int, int)
    def on_hp(self, current: int, max_val: int) -> None:
        if max_val <= 0:
            return

        pct = current / max_val * 100

        # Cooldown guard (with jitter so the gap is never exactly the same)
        jitter_factor = 1.0 + random.uniform(
            -self.COOLDOWN_JITTER, self.COOLDOWN_JITTER
        )
        cooldown = self.COOLDOWN_BASE * jitter_factor
        if time.monotonic() - self._last_fire < cooldown:
            return

        # First matching threshold
        matched = None
        for threshold, probability, cast_count in self._table:
            if pct < threshold:
                matched = (probability, cast_count)
                break

        if matched is None:
            return

        prob, count = matched
        if random.randint(1, 100) > prob:
            return

        self._fire(count)

    # ── internals ────────────────────────────────────────────────────

    def _fire(self, count: int = 1) -> None:
        self._last_fire = time.monotonic()
        if self._client is not None:
            from board_client import jitter_sleep
            if not self._page_switched and self._page_key:
                self._client.key_tap(self._page_key)
                jitter_sleep(0.3, spread=0.10)
                self._page_switched = True
            for i in range(count):
                if i > 0:
                    jitter_sleep(0.4, spread=0.10)
                self._client.key_tap(self._slot_key)
                jitter_sleep(0.30, spread=0.08)
                self._client.key_tap(self._slot_key)
        skill_str = f"{self._slot_key.upper()}×{count*2}"
        self.healed.emit(skill_str)

    @staticmethod
    def _parse_skill(hotkey: str) -> tuple[str, str]:
        """Convert "P1-F5" → ("f1", "f5"), etc."""
        if "-" in hotkey:
            page_part, slot_part = hotkey.split("-", 1)
            # P1/P2/P3 → f1/f2/f3
            if page_part.upper().startswith("P") and page_part[1:].isdigit():
                page_key = "f" + page_part[1:]
            else:
                page_key = page_part.lower()
            return page_key, slot_part.lower()
        # Bare slot like "F5" — no page switch
        return "", hotkey.lower()
