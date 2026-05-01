"""Coordinate-system glue for the hid_mouse output path.

Three coordinate systems are in play:

  game        (x, y) inside the Lineage client area, 0..1280 × 0..960
  screen      desktop / virtual-screen pixel coords (Win32 POINT)
  hid         absolute HID pointer space, 0..32767 × 0..32767, mapped
              by Windows across the entire virtual screen

The Arduino firmware (``hid_mouse.ino``) takes hid coordinates via
``M x y`` so we need to convert from game-cell coords (which is what
the bot logic naturally thinks in — "click at item slot 3,2") all the
way down to hid before each ``MouseClient.move_to`` call.

The mapping math is deterministic but depends on:
  * the game window's screen position (``ClientToScreen`` of (0,0))
  * the virtual-screen rectangle (multi-monitor aware)

Both are read on demand via Win32 — fast (~1 µs) — so we don't bother
caching across calls. Reading right before each move also means the
mapping self-heals if the user drags the game window mid-session.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes


_user32 = ctypes.windll.user32

# GetSystemMetrics indices for the virtual screen (covers all monitors).
SM_XVIRTUALSCREEN  = 76
SM_YVIRTUALSCREEN  = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

HID_MAX = 32767


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def virtual_screen_rect() -> tuple[int, int, int, int]:
    """Return the virtual-screen rectangle as (left, top, width, height)
    in pixels. Spans all monitors for multi-monitor setups."""
    return (
        _user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        _user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


def client_to_screen(hwnd: int, x: int, y: int) -> tuple[int, int]:
    """Translate (x, y) in the window's client area to absolute screen
    pixel coords. Uses Win32 ClientToScreen so it accounts for window
    position, decorations and DPI scaling."""
    p = _POINT(int(x), int(y))
    if not _user32.ClientToScreen(hwnd, ctypes.byref(p)):
        raise OSError("ClientToScreen failed")
    return p.x, p.y


def screen_to_hid(screen_x: int, screen_y: int) -> tuple[int, int]:
    """Map screen pixels → HID absolute coords (0..32767).

    The HID Absolute Pointer device reports coords proportional to the
    virtual screen, so HID (0,0) is the virtual-screen top-left and
    HID (32767, 32767) is the bottom-right.
    """
    vx, vy, vw, vh = virtual_screen_rect()
    if vw <= 0 or vh <= 0:
        raise OSError(f"invalid virtual screen rect ({vw}×{vh})")
    rel_x = (screen_x - vx) / vw
    rel_y = (screen_y - vy) / vh
    rel_x = min(max(rel_x, 0.0), 1.0)
    rel_y = min(max(rel_y, 0.0), 1.0)
    return round(rel_x * HID_MAX), round(rel_y * HID_MAX)


def game_to_hid(hwnd: int, game_x: int, game_y: int) -> tuple[int, int]:
    """One-shot: game client (x, y) → HID (x, y)."""
    sx, sy = client_to_screen(hwnd, game_x, game_y)
    return screen_to_hid(sx, sy)


def get_cursor_screen_pos() -> tuple[int, int]:
    """Read the current cursor's absolute screen position. Anti-cheat
    safe — purely a desktop-API read with no game-process touch.

    Used by HumanMouse to start interpolation from where the cursor
    actually is right now (rather than blindly assuming the previous
    target landed). Win32 may snap the cursor to the nearest pixel
    when dragged by a real mouse; this stays in sync with that.
    """
    p = _POINT()
    if not _user32.GetCursorPos(ctypes.byref(p)):
        raise OSError("GetCursorPos failed")
    return p.x, p.y


def get_cursor_hid_pos() -> tuple[int, int]:
    """Same as get_cursor_screen_pos but in HID coords."""
    return screen_to_hid(*get_cursor_screen_pos())


# ───────────── Mouse acceleration (Pointer Precision) ─────────────
# Windows' "Enhance pointer precision" non-linearly scales each mouse
# delta based on current speed. That makes our HumanMouse bezier path
# overshoot-and-correct ("亂飄"). Toggle the system setting off while
# the bot is driving the mouse, restore on exit.

SPI_GETMOUSE = 0x0003
SPI_SETMOUSE = 0x0004
SPIF_SENDCHANGE = 0x02


def get_mouse_acceleration_settings() -> tuple[int, int, int]:
    """Return ``(threshold1, threshold2, accel)``. ``accel`` is 0 or 1
    (Pointer Precision off / on)."""
    arr = (ctypes.c_int * 3)()
    if not _user32.SystemParametersInfoW(SPI_GETMOUSE, 0, arr, 0):
        raise OSError("SPI_GETMOUSE failed")
    return arr[0], arr[1], arr[2]


def set_mouse_acceleration_settings(t1: int, t2: int, accel: int) -> None:
    arr = (ctypes.c_int * 3)(int(t1), int(t2), int(accel))
    if not _user32.SystemParametersInfoW(
        SPI_SETMOUSE, 0, arr, SPIF_SENDCHANGE
    ):
        raise OSError("SPI_SETMOUSE failed")


class MouseAccelerationOff:
    """Context manager: disable Pointer Precision while inside, restore
    on exit. Safe under exception."""

    def __init__(self) -> None:
        self._original: tuple[int, int, int] | None = None

    def __enter__(self) -> "MouseAccelerationOff":
        self._original = get_mouse_acceleration_settings()
        # Keep the thresholds, just turn accel off.
        set_mouse_acceleration_settings(
            self._original[0], self._original[1], 0
        )
        return self

    def __exit__(self, *exc) -> None:
        if self._original is not None:
            try:
                set_mouse_acceleration_settings(*self._original)
            except Exception:  # noqa: BLE001
                pass
            self._original = None
