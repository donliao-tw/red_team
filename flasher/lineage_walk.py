"""High-level walk primitives for Lineage Classic.

Lineage uses isometric tiles (2:1 diamond ratio). Empirical calibration
(see docs/dev-log.md): a click 100 px in each cardinal direction from
the player's screen centre walks the character roughly:

  N: 5 tiles   →  ~20 px/tile vertical
  S: 3 tiles   →  ~33 px/tile vertical
  E: 2 tiles   →  ~50 px/tile horizontal
  W: 2 tiles   →  ~50 px/tile horizontal

The N/S asymmetry probably reflects an off-by-30-px PLAYER_XY estimate
(if the actual player centre is at y=400 rather than 380, both N and S
yield ~26 px/tile, matching the standard 2:1 isometric ratio).
We use TILE_X=50, TILE_Y=26 as the working baseline.

Click-to-walk semantics: clicking ground at (X, Y) makes the character
walk *toward* that pixel until it arrives, hits an obstacle, or another
click redirects it. So `walk(direction, n_tiles)` actually computes a
target n_tiles away in pixel space — Lineage will walk roughly that
distance if path is clear.
"""
from __future__ import annotations

from board_client import BoardClient, jitter_sleep
from human_mouse import HumanMouse


# Player screen-space anchor — character's *feet* (where the click
# direction is computed from), not the body centre. Refined from
# (640, 400) (body) → (640, 410) (feet) to make N/S pitches symmetric
# under the 2:1 isometric tile model.
PLAYER_XY: tuple[int, int] = (640, 410)

# Per-tile pixel pitch in screen space. 2:1 isometric ratio.
TILE_X: int = 50
TILE_Y: int = 26

# Time the character takes to walk one tile (empirically ~0.8 s).
WALK_S_PER_TILE: float = 0.8

# Direction → screen-pixel offset for *one tile* in that direction.
# Cardinal directions move along screen axes (N/S vertical, E/W
# horizontal). Diagonals use the isometric NE/SE/NW/SW axes which are
# **not** 45° in screen space — for a 2:1 diamond, the NE-axis sits at
# atan2(-13, 25) ≈ -27.5° from horizontal, not -45°. Clicking at a
# 45° screen angle results in mixed walking (e.g. "north 2 tiles
# then north-west") because the click target falls between the NE
# and N axes; the game resolves it as nearest-axis movement and
# changes direction partway.
# Diagonals: NE/NW use TILE_Y/2 = 13, but SE/SW use 11. Empirically the
# south-pointing diagonals need a slightly LESS steep Y offset to land
# on the isometric SE/SW axes — clicks at the symmetric +13 angle land
# slightly south of the SE-axis and Lineage resolves them as "south
# then south-east" in two legs. Biasing the click toward the E/W axis
# (smaller |dy|) makes the angle round to SE/SW cleanly.
TILE_PITCH: dict[str, tuple[int, int]] = {
    "N":  (0, -TILE_Y),
    "S":  (0, +TILE_Y),
    "E":  (+TILE_X, 0),
    "W":  (-TILE_X, 0),
    "NE": (+TILE_X // 2, -13),
    "NW": (-TILE_X // 2, -13),
    "SE": (+TILE_X // 2, +11),
    "SW": (-TILE_X // 2, +11),
}

# Backward-compat alias used by older tests.
DIRECTIONS = TILE_PITCH


def tile_offset_to_pixel(direction: str, n_tiles: int) -> tuple[int, int]:
    """Pixel target n_tiles in `direction` from PLAYER_XY (game coords)."""
    if direction not in TILE_PITCH:
        raise ValueError(f"unknown direction {direction!r}")
    dx_per, dy_per = TILE_PITCH[direction]
    return PLAYER_XY[0] + dx_per * n_tiles, PLAYER_XY[1] + dy_per * n_tiles


def walk(mouse: HumanMouse, direction: str, n_tiles: int,
         *, wait_per_tile: float = WALK_S_PER_TILE,
         settle_s: float = 0.5) -> None:
    """Click the tile n_tiles in `direction` from player and wait for
    the character to arrive.

    Note: Lineage's *normal* movement is press-and-hold, which lets
    the character walk continuously and stop automatically on
    obstacles. ``walk()`` (single click) only works for short hops;
    long traversal should use ``walk_hold()`` instead so we don't
    have to keep re-clicking after each stop.
    """
    target = tile_offset_to_pixel(direction, n_tiles)
    mouse.click_at_game(*target)
    jitter_sleep(wait_per_tile * n_tiles + settle_s)


def walk_hold(mouse: HumanMouse, direction: str,
              hold_s: float | tuple[float, float] = (0.8, 2.5),
              *, far_tiles: int = 8) -> float:
    """Press-and-hold left button toward a faraway tile in
    ``direction`` for ``hold_s`` seconds, then release.

    ``hold_s`` may be a single number or a ``(low, high)`` range; if
    a range, the actual hold time is sampled uniformly. **Always pass
    a range** for movement loops — a fixed hold reads as scripted to
    detection. ``HumanMouse.hold_at_game`` already adds ±8 % micro
    jitter on top of whatever value we pass, but human-like behaviour
    needs per-move *macro* variation as well (some movements are 0.9 s,
    some 2.4 s, depending on what the bot is heading toward).

    ``far_tiles`` controls *how far* the click is aimed; bounded by
    hold time + obstacles. 8 gives the cursor a clearly off-direction
    landing point so the character keeps walking instead of arriving
    and stopping.

    Returns the hold time actually used (for logging).
    """
    import random as _random
    if isinstance(hold_s, tuple):
        lo, hi = hold_s
        actual = _random.uniform(lo, hi)
    else:
        actual = float(hold_s)
    target = tile_offset_to_pixel(direction, far_tiles)
    mouse.hold_at_game(*target, hold_s=actual)
    return actual
