"""Human-like cursor movement on top of the raw BoardClient.

Even with a real-mouse-style HID descriptor (firmware v0.4+, relative
deltas), a cursor that teleports in straight lines at constant speed
reads as scripted to anti-cheat / contest-judge analysis. This module
produces:

  * **Bezier-curve paths** — cubic with two control points slightly
    offset from the direct line, so the cursor takes a slight arc
    rather than a straight ruler stroke.
  * **Ease-in-out velocity** — accelerates from rest, holds higher
    speed in the middle, decelerates onto the target.
  * **Sub-pixel jitter** — ±0.5 px noise per sample, mimicking a
    hand on a mouse.
  * **Distance-aware duration** — Fitts-style heuristic so short
    movements take ~200 ms and full-screen swings take ~500 ms.
  * **Click delays** — settle pause before pressing, follow-through
    after releasing.

All randomness uses ``random.uniform`` / ``random.randint`` so each
call's path is unique. Two consecutive ``move_to_game(640, 480)``
calls produce different bezier control points and slightly different
total durations.

Implementation notes for v0.4+ relative-delta firmware:

  * Bezier interpolation runs in *screen pixel* coordinates.
  * For each interpolation step we read ``GetCursorPos()`` (Win32,
    cheap, anti-cheat-safe) and send the delta to the next planned
    sample. This self-heals against Windows mouse-ballistics ("Enhance
    pointer precision") drift — even if the OS scales our deltas
    non-linearly, we re-aim each step at the next true target.
"""
from __future__ import annotations

import math
import random
import time

from board_client import BoardClient
from window_mapper import client_to_screen, get_cursor_screen_pos


# Tuning knobs — exposed at module level so a future settings page
# can let the user nudge them per-character / per-machine.
DEFAULT_FPS = 100               # interpolation steps per second
MIN_DURATION_MS = 180
DURATION_PER_PIXEL = 0.4        # ms per pixel of screen distance (~400 ms / 1000 px)
JITTER_RANDOM_MS_RANGE = (-30, 60)


class HumanMouse:
    """Compose smooth, jittered cursor moves over a ``BoardClient``.

    Bind to a specific game window's HWND so ``move_to_game`` can
    interpret game-relative coordinates. The HWND can be re-set if the
    game gets relaunched.
    """

    def __init__(self, client: BoardClient, hwnd: int) -> None:
        self.client = client
        self.hwnd = hwnd

    # ────────────────────────── public API ──────────────────────────

    def move_to_game(self, game_x: int, game_y: int,
                     *, duration_ms: int | None = None) -> None:
        """Smooth-move the cursor to (game_x, game_y) inside the game's
        client area. Re-reads the game window position each call so a
        moved/resized window doesn't break the mapping."""
        target_screen = client_to_screen(self.hwnd, int(game_x), int(game_y))
        self._smooth_move_to_screen(target_screen, duration_ms=duration_ms)

    def hover_at_game(self, game_x: int, game_y: int,
                      *, hover_ms: int = 600,
                      duration_ms: int | None = None) -> None:
        """Move + rest. Use before reading a tooltip — the rest gives
        the game time to render the tooltip before the caller captures
        a frame."""
        self.move_to_game(game_x, game_y, duration_ms=duration_ms)
        time.sleep(max(0.0, (hover_ms + random.randint(-50, 100)) / 1000))

    def click_at_game(self, game_x: int, game_y: int,
                      *, duration_ms: int | None = None,
                      pre_click_ms: int = 80,
                      post_click_ms: int = 120) -> None:
        """Move + settle + click + follow-through."""
        self.move_to_game(game_x, game_y, duration_ms=duration_ms)
        time.sleep(max(0.0, (pre_click_ms + random.randint(-20, 30)) / 1000))
        self.client.click()
        time.sleep(max(0.0, (post_click_ms + random.randint(-30, 40)) / 1000))

    def right_click_at_game(self, game_x: int, game_y: int,
                            **kwargs) -> None:
        self.move_to_game(game_x, game_y,
                          duration_ms=kwargs.get("duration_ms"))
        time.sleep(max(0.0, (kwargs.get("pre_click_ms", 80)
                             + random.randint(-20, 30)) / 1000))
        self.client.right_click()
        time.sleep(max(0.0, (kwargs.get("post_click_ms", 120)
                             + random.randint(-30, 40)) / 1000))

    def hold_at_game(self, game_x: int, game_y: int, hold_s: float,
                     *, duration_ms: int | None = None,
                     pre_press_ms: int = 80) -> None:
        """Smooth-move to (game_x, game_y), press the left button,
        hold for ``hold_s`` seconds (jittered), then release.

        Lineage's continuous-walk uses this: holding the left button
        with the cursor over a faraway tile makes the character walk
        toward it indefinitely (it stops automatically when it hits
        an obstacle). For movement loops we hold ~1-2 s, release,
        check the minimap, then re-aim.
        """
        self.move_to_game(game_x, game_y, duration_ms=duration_ms)
        time.sleep(max(0.0, (pre_press_ms + random.randint(-20, 30)) / 1000))
        self.client.press()
        # Jitter the hold so the press isn't exactly hold_s every time.
        time.sleep(max(0.0, hold_s + hold_s * random.uniform(-0.08, 0.08)))
        self.client.release()

    # ────────────────────────── internals ──────────────────────────

    def _smooth_move_to_screen(self, target_screen: tuple[int, int],
                               *, duration_ms: int | None = None) -> None:
        """Send a bezier-curve sequence of relative-delta moves.

        Earlier versions re-read GetCursorPos at each step to "self-heal"
        against Windows mouse-ballistics drift, but the per-step
        correction made the cursor zigzag visibly (each correction
        over- or under-shot due to acceleration). The current design:

          * Compute the full bezier path in screen-pixel space upfront.
          * Send each step's delta against the *previous planned*
            position — the cursor follows the planned arc smoothly,
            even if absolute drift accumulates.
          * After the path completes, read GetCursorPos once and send
            a single corrective delta so the cursor *does* land on the
            target (the user's eye sees the gentle arc + a tiny final
            settle, which actually looks more human than a perfectly
            tracked path).
        """
        start = get_cursor_screen_pos()
        dx_total = target_screen[0] - start[0]
        dy_total = target_screen[1] - start[1]
        dist = math.hypot(dx_total, dy_total)
        if dist < 2:
            return

        if duration_ms is None:
            duration_ms = self._default_duration_ms(dist)

        steps = max(2, int(duration_ms * DEFAULT_FPS / 1000))
        sleep_per_step = duration_ms / 1000 / steps

        # Cubic bezier control points: two waypoints between start and
        # end, each offset perpendicular to the direct line by a random
        # fraction of the distance — gives the path a gentle arc.
        nx, ny = -dy_total / dist, dx_total / dist
        o1 = random.uniform(-0.15, 0.15) * dist
        o2 = random.uniform(-0.15, 0.15) * dist
        t1 = random.uniform(0.2, 0.4)
        t2 = random.uniform(0.6, 0.8)
        p1 = (start[0] + dx_total * t1 + nx * o1,
              start[1] + dy_total * t1 + ny * o1)
        p2 = (start[0] + dx_total * t2 + nx * o2,
              start[1] + dy_total * t2 + ny * o2)

        prev_x, prev_y = start
        for i in range(1, steps + 1):
            t = i / steps
            te = _ease_in_out_cubic(t)
            x, y = _cubic_bezier(start, p1, p2, target_screen, te)
            # Tiny sub-pixel jitter — kept small so it doesn't dominate
            # the visible motion noise.
            x += random.uniform(-0.3, 0.3)
            y += random.uniform(-0.3, 0.3)
            nx_planned = round(x)
            ny_planned = round(y)
            dx = nx_planned - prev_x
            dy = ny_planned - prev_y
            if dx or dy:
                self.client.move_relative(dx, dy)
            prev_x, prev_y = nx_planned, ny_planned
            if i < steps:
                time.sleep(sleep_per_step)

        # Final corrective settle: read where the cursor ended up
        # (ballistics may have drifted it slightly off target) and snap
        # to the exact target.
        cur = get_cursor_screen_pos()
        fdx = target_screen[0] - cur[0]
        fdy = target_screen[1] - cur[1]
        if fdx or fdy:
            self.client.move_relative(fdx, fdy)

    @staticmethod
    def _default_duration_ms(pixel_distance: float) -> int:
        base = MIN_DURATION_MS + pixel_distance * DURATION_PER_PIXEL
        jitter = random.randint(*JITTER_RANDOM_MS_RANGE)
        return max(MIN_DURATION_MS, int(base + jitter))


# ────────────────────────── primitives ──────────────────────────

def _cubic_bezier(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1 - t
    bx = (u ** 3) * p0[0] + 3 * (u ** 2) * t * p1[0] \
        + 3 * u * (t ** 2) * p2[0] + (t ** 3) * p3[0]
    by = (u ** 3) * p0[1] + 3 * (u ** 2) * t * p1[1] \
        + 3 * u * (t ** 2) * p2[1] + (t ** 3) * p3[1]
    return bx, by


def _ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    f = -2 * t + 2
    return 1 - (f * f * f) / 2
