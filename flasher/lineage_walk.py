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

import time

from board_client import BoardClient
from human_mouse import HumanMouse


# Player screen position. Refined from y=380 → y=400 to make N/S
# pitches symmetric (and matching standard 2:1 isometric tiles).
PLAYER_XY: tuple[int, int] = (640, 400)

# Per-tile pixel pitch in screen space. 2:1 isometric ratio.
TILE_X: int = 50
TILE_Y: int = 26

# Time the character takes to walk one tile (empirically ~0.8 s).
WALK_S_PER_TILE: float = 0.8

# Direction → (dx_tiles, dy_tiles) where +y is south, +x is east.
DIRECTIONS: dict[str, tuple[int, int]] = {
    "N":  (0, -1),
    "S":  (0, +1),
    "E":  (+1, 0),
    "W":  (-1, 0),
    "NE": (+1, -1),
    "NW": (-1, -1),
    "SE": (+1, +1),
    "SW": (-1, +1),
}


def tile_offset_to_pixel(direction: str, n_tiles: int) -> tuple[int, int]:
    """Pixel target n_tiles in `direction` from PLAYER_XY (game coords)."""
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction {direction!r}")
    dx_t, dy_t = DIRECTIONS[direction]
    px = PLAYER_XY[0] + dx_t * n_tiles * TILE_X
    py = PLAYER_XY[1] + dy_t * n_tiles * TILE_Y
    return px, py


def walk(mouse: HumanMouse, direction: str, n_tiles: int,
         *, wait_per_tile: float = WALK_S_PER_TILE,
         settle_s: float = 0.5) -> None:
    """Click the tile n_tiles in `direction` from player and wait for
    the character to arrive.

    The wait is based on the requested tile count + a small settle
    margin. If the character is blocked partway, the wait still
    elapses; subsequent walks just redirect from wherever the
    character actually stopped.
    """
    target = tile_offset_to_pixel(direction, n_tiles)
    mouse.click_at_game(*target)
    time.sleep(wait_per_tile * n_tiles + settle_s)
