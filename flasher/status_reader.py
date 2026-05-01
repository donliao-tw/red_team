"""Status-zone field readers — OCR + agreement validation + bitmap cache.

The Lineage status zone (defense / mdef / weight / hunger / Lawful + the
sun/moon time icon) sits below the LV/EXP ribbon and HP/MP bars. Most
of these values change only on a player action (equip swap, item drop,
day/night cycle), so we don't need streaming-perfect recognition. The
strategy here is:

  1. **Bitmap-hash cache** — hash the cell's binary text mask. If the
     hash has been seen before and validated, return the cached value
     instantly. Same value always produces the same bitmap (deterministic
     pixel font), so cache hits are free and 100% accurate.

  2. **OCR + agreement** — on a cache miss, run RapidOCR. Don't trust a
     single read: keep the last N readings per field, and only accept
     a value when it has been seen N consecutive times. Once accepted,
     write (hash, value) to the cache so future reads are fast.

  3. **Time of day** is a separate path — the icon is classified by
     yellow-pixel ratio (HSV-equivalent). Day = high yellow saturation,
     night = low. Returns None when uncertain (panel keeps last state).

The cache lives only for the lifetime of the GameMonitor, so a fresh
launch re-runs OCR until each value is seen N times again. No persistence
to disk yet — that can come later if startup latency matters.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import re
from typing import Callable, Optional

import numpy as np
from PIL import Image


def _bitmap_hash(crop_arr: np.ndarray) -> str:
    """Stable hash of the cell's bright-text bitmap. Robust to JPEG-style
    noise because we threshold first, but sensitive to actual text changes.
    """
    if crop_arr.ndim == 3:
        # Achromatic-bright mask — same threshold across HP-style and
        # status-style fonts. Reasonable for hash purposes.
        R, G, B = crop_arr[..., 0], crop_arr[..., 1], crop_arr[..., 2]
        sat = crop_arr.max(axis=2).astype(int) - crop_arr.min(axis=2).astype(int)
        mask = (R > 180) & (G > 180) & (B > 180) & (sat < 40)
    else:
        mask = crop_arr > 180
    return hashlib.blake2b(mask.tobytes(), digest_size=12).hexdigest()


# ───────────────────────────── FieldReader ─────────────────────────────


@dataclass
class FieldReader:
    """One status-zone field. Owns its own bitmap-hash cache and an
    agreement window over the last N OCR readings.

    Parameters
    ----------
    name
        Logical field name (used for log messages).
    parse
        Callable that takes the raw OCR text and returns the validated
        value, or None if the OCR result is implausible. Examples:

            lambda s: int(s) if s.isdigit() and 0 <= int(s) <= 999 else None

    agreement
        Number of consecutive identical OCR results required before a
        value is accepted. Defaults to 3.
    """

    name: str
    parse: Callable[[str], Optional[object]]
    agreement: int = 3
    cache: dict[str, object] = field(default_factory=dict)
    _recent: deque = field(default_factory=lambda: deque(maxlen=8))
    _confirmed: Optional[object] = None

    def read(self, crop_arr: np.ndarray, ocr_text: str) -> Optional[object]:
        """Take the cell crop + an already-run OCR string. Returns the
        best current estimate of the field value, or None if OCR can't
        produce a parseable result.

        Behaviour:
          * Cache hit → return cached value (100% reliable).
          * First successful parse → emit immediately so the GUI doesn't
            sit on '?' for the agreement window. Tentative until cached.
          * After ``self.agreement`` consecutive identical reads → write
            (hash, value) to the cache so future reads of the same
            bitmap are free.
        """
        h = _bitmap_hash(crop_arr)
        if h in self.cache:
            self._confirmed = self.cache[h]
            return self._confirmed

        v = self.parse(ocr_text)
        if v is None:
            return self._confirmed

        # Latest parsed value is the live reading the GUI shows.
        self._confirmed = v

        self._recent.append((h, v))
        if len(self._recent) >= self.agreement:
            recent_vals = [x[1] for x in list(self._recent)[-self.agreement:]]
            if all(x == v for x in recent_vals):
                # Lock this bitmap to this value — future hash hits
                # short-circuit OCR + parsing entirely.
                self.cache[h] = v
        return v

    @property
    def confirmed(self) -> Optional[object]:
        return self._confirmed


# ─────────────────────────── Field parsers ───────────────────────────


def parse_int(text: str, *, lo: int = 0, hi: int = 99999) -> Optional[int]:
    m = re.search(r"-?\d+", text)
    if m is None:
        return None
    try:
        v = int(m.group())
    except ValueError:
        return None
    return v if lo <= v <= hi else None


def parse_percent(text: str, *, lo: int = 0, hi: int = 200) -> Optional[int]:
    """Pull a leading integer out of OCR results like '16%', '100%',
    or '16 %'. Allows the % sign to be missing — RapidOCR sometimes
    drops it."""
    m = re.search(r"\d+", text)
    if m is None:
        return None
    try:
        v = int(m.group())
    except ValueError:
        return None
    return v if lo <= v <= hi else None


def parse_lawful(text: str) -> Optional[int]:
    """Lawful: signed 16-bit. Range -32768 to 32767."""
    m = re.search(r"-?\d{1,5}", text)
    if m is None:
        return None
    try:
        v = int(m.group())
    except ValueError:
        return None
    return v if -32768 <= v <= 32767 else None


# ───────────────────────────── Time of day ─────────────────────────────


def classify_time_of_day(crop_arr: np.ndarray) -> Optional[str]:
    """Return 'day', 'night' or None for the in-game sundial.

    The time bar is a horizontal sundial: a ~200 px wide gradient
    (left=dark blue night, right=light day) with a pale-yellow moon
    cursor (~RGB 242,226,118) gliding left-to-right as game time
    passes. Empirically the dark-to-light transition happens around
    65 % of the bar width — values up to that are "still night",
    past it the sky is bright enough to be "day".

    A 5 % deadzone around the boundary returns None (panel keeps the
    last confirmed state) so dawn/dusk doesn't make the icon flicker.
    """
    R = crop_arr[..., 0].astype(int)
    G = crop_arr[..., 1].astype(int)
    B = crop_arr[..., 2].astype(int)
    cursor = (R > 220) & (G > 200) & (B < 150) & ((R - B) > 70)
    ys, xs = np.where(cursor)
    if len(xs) < 6:
        return None
    cx = float(xs.mean())
    width = crop_arr.shape[1]
    pct = cx / width
    NIGHT_DAY_BOUNDARY = 0.65
    DEADZONE = 0.05
    if pct < NIGHT_DAY_BOUNDARY - DEADZONE:
        return "night"
    if pct > NIGHT_DAY_BOUNDARY + DEADZONE:
        return "day"
    return None


# ───────────────────────────── Factory ─────────────────────────────


def make_default_readers() -> dict[str, FieldReader]:
    """Standard reader set for the Lineage status panel.

    Numeric ranges are loose — we just want to filter OCR garbage like
    'O' read as '0' inside multi-digit results that exceed the value
    domain.
    """
    return {
        "defense": FieldReader("defense", lambda s: parse_int(s, lo=0, hi=999)),
        "mdef":    FieldReader("mdef",    parse_percent),
        "weight":  FieldReader("weight",  parse_percent),
        "hunger":  FieldReader("hunger",  parse_percent),
        "lawful":  FieldReader("lawful",  parse_lawful),
    }
