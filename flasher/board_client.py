"""Low-level driver for the hid_mouse Arduino firmware (composite
mouse + keyboard, **firmware v0.4+**).

Talks the line-oriented ASCII protocol defined in
[firmware/hid_mouse/hid_mouse.ino](../firmware/hid_mouse/hid_mouse.ino):

    MR dx dy mouse: move by relative delta (each clamped to ±127)
    C        mouse: left click
    R        mouse: right click
    D        mouse: left button press (hold)
    U        mouse: left button release
    K name   keyboard: tap (press + release) the named key
    KD name  keyboard: hold key down
    KU name  keyboard: release key
    P        ping        (responds: pong)
    V        version     (responds: hid_mouse v<n>)

Lineage Classic filters HID Absolute Pointer (tablet-style) reports
for hover events — earlier firmware (v0.1-0.3) used HID-Project's
``AbsoluteMouse`` and the cursor *moved* but tooltips never appeared.
v0.4 uses the standard ``Mouse`` class which sends relative-delta
reports indistinguishable from a consumer USB mouse, so hover events
now reach the game.

Trade-off: the panel must track the cursor's current screen position
(via ``GetCursorPos``) and compute deltas. Long moves are chunked into
multiple MR commands (HID limits each report to ±127 per axis).

Only the wire protocol — no movement smoothing, no game-window mapping,
no key combo macros. Stack human-like behaviour on top in
human_mouse.py.

Module is named ``board_client`` (renamed from ``mouse_client``) since
it drives the keyboard too. Older callers that import ``MouseClient``
from ``mouse_client`` still work via a thin shim.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import serial
import serial.tools.list_ports as list_ports


DELTA_MAX = 127  # HID Mouse relative report limit per axis
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT_S = 0.5

# Backwards-compat aliases — older code referenced HID Absolute coords.
HID_MIN = 0
HID_MAX = 32767


# Key-name aliases the firmware accepts. Listed here for editor
# autocomplete / runtime validation; the canonical lookup lives in
# the firmware's lookupKey().
KNOWN_KEY_NAMES: frozenset[str] = frozenset({
    # navigation / control
    "tab", "esc", "escape", "enter", "return", "space", "backspace",
    "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown", "insert", "delete",
    # modifiers
    "shift", "ctrl", "alt",
    # function keys
    *(f"f{i}" for i in range(1, 13)),
    # alphanumerics — single ASCII chars also accepted
    *(chr(c) for c in range(ord("a"), ord("z") + 1)),
    *(chr(c) for c in range(ord("0"), ord("9") + 1)),
})


class BoardClientError(RuntimeError):
    """Raised when the firmware reports an error or the link drops."""


# Backwards-compat alias for older code paths.
MouseClientError = BoardClientError


@dataclass(frozen=True)
class PortCandidate:
    device: str
    description: str
    vid_pid: str


class BoardClient:
    """Thread-safe wire protocol client. Each public call holds an
    internal lock so two callers can't interleave commands.

    Use as a context manager or call ``close()`` explicitly:

        with BoardClient.auto_detect() as b:
            b.move_to(16384, 16384)
            b.click()
            b.key_tap("tab")
    """

    def __init__(self, port: str, *, baud: int = DEFAULT_BAUD,
                 timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._port = port
        self._lock = threading.Lock()
        # Pro Micro USB-CDC needs ~50 ms after open before reads work
        # cleanly — give it a beat then drain stale bytes.
        self._ser = serial.Serial(
            port, baudrate=baud,
            timeout=timeout_s, write_timeout=timeout_s,
        )
        time.sleep(0.05)
        self._ser.reset_input_buffer()

    @property
    def port(self) -> str:
        return self._port

    def close(self) -> None:
        try:
            self._ser.close()
        except Exception:
            pass

    def __enter__(self) -> "BoardClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ────────────────────────── wire protocol ──────────────────────────

    def _command(self, line: str) -> str:
        """Send one command line, return the response line (sans trailing
        newline). Caller holds ``_lock``."""
        if not line.endswith("\n"):
            line += "\n"
        self._ser.write(line.encode("ascii"))
        self._ser.flush()
        resp = self._ser.readline().decode("ascii", errors="replace").strip()
        if not resp:
            raise BoardClientError(f"no response to {line.strip()!r}")
        if resp.startswith("err"):
            raise BoardClientError(f"firmware: {resp}")
        return resp

    def ping(self) -> bool:
        with self._lock:
            try:
                return self._command("P") == "pong"
            except (BoardClientError, serial.SerialException):
                return False

    def version(self) -> str:
        with self._lock:
            return self._command("V")

    # ── mouse ──────────────────────────────────────────────────────

    def move_relative(self, dx: int, dy: int) -> None:
        """Move the cursor by (dx, dy) screen pixels. Either or both
        can be negative. Long moves are chunked internally into
        ``MR`` reports of ±127 max per axis (HID Mouse limit)."""
        dx = int(dx)
        dy = int(dy)
        with self._lock:
            while dx != 0 or dy != 0:
                step_x = max(-DELTA_MAX, min(DELTA_MAX, dx))
                step_y = max(-DELTA_MAX, min(DELTA_MAX, dy))
                self._command(f"MR {step_x} {step_y}")
                dx -= step_x
                dy -= step_y

    def click(self) -> None:
        with self._lock:
            self._command("C")

    def right_click(self) -> None:
        with self._lock:
            self._command("R")

    def press(self) -> None:
        """Left button down. Pair with ``release()`` for drag."""
        with self._lock:
            self._command("D")

    def release(self) -> None:
        with self._lock:
            self._command("U")

    # ── keyboard ───────────────────────────────────────────────────

    def key_tap(self, name: str) -> None:
        """Press + release a key. e.g. ``key_tap('tab')``,
        ``key_tap('f1')``, ``key_tap('a')``."""
        self._validate_key(name)
        with self._lock:
            self._command(f"K {name}")

    def key_down(self, name: str) -> None:
        """Hold a key down. Pair with ``key_up`` to release."""
        self._validate_key(name)
        with self._lock:
            self._command(f"KD {name}")

    def key_up(self, name: str) -> None:
        self._validate_key(name)
        with self._lock:
            self._command(f"KU {name}")

    def key_combo(self, modifier: str, key: str) -> None:
        """Modifier-held tap. e.g. ``key_combo('shift', 'a')`` for ``Shift+A``,
        ``key_combo('ctrl', 'c')`` for copy. The firmware itself doesn't
        understand combos, so we send three commands: hold modifier, tap
        key, release modifier. The lock acquired by each call serialises
        them — interleaving with other callers can't break the combo."""
        self.key_down(modifier)
        try:
            self.key_tap(key)
        finally:
            self.key_up(modifier)

    @staticmethod
    def _validate_key(name: str) -> None:
        n = name.lower()
        if n not in KNOWN_KEY_NAMES:
            raise ValueError(
                f"unknown key {name!r}; valid: {sorted(KNOWN_KEY_NAMES)}"
            )

    # ────────────────────────── auto-detect ──────────────────────────

    @classmethod
    def list_candidates(cls) -> list[PortCandidate]:
        """All visible COM ports with a USB VID/PID. The hid_mouse board
        spoofs VID/PID, so we can't filter by ID — caller must ping each
        candidate to find ours."""
        out = []
        for p in list_ports.comports():
            if p.vid is None or p.pid is None:
                continue
            out.append(PortCandidate(
                device=p.device,
                description=p.description or "",
                vid_pid=f"{p.vid:04X}:{p.pid:04X}",
            ))
        return out

    @classmethod
    def auto_detect(cls, *, baud: int = DEFAULT_BAUD,
                    timeout_s: float = DEFAULT_TIMEOUT_S
                    ) -> "BoardClient":
        last_error: Exception | None = None
        for cand in cls.list_candidates():
            try:
                client = cls(cand.device, baud=baud, timeout_s=timeout_s)
            except (serial.SerialException, OSError) as e:
                last_error = e
                continue
            if client.ping():
                return client
            client.close()
        raise BoardClientError(
            "no hid_mouse board responded to ping on any visible port"
            + (f"; last error: {last_error}" if last_error else "")
        )


# Backward-compat alias — older code uses ``MouseClient``.
MouseClient = BoardClient
