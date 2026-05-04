"""Game window capture via Windows Graphics Capture (WGC).

Pure read-side: WGC only consumes the swap-chain framebuffer that the
compositor already has access to. We never call into the game process,
read its memory, hook DLLs, or modify any handles. This is the
anti-cheat-safe path mandated by CLAUDE.md.

Public API:
    find_game_window(needle="Lineage") -> int       # returns HWND
    get_window_title(hwnd) -> str
    get_client_size(hwnd) -> (w, h)
    grab_frame(needle="Lineage") -> PIL.Image       # blocking, ~500ms
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Optional

from PIL import Image
from windows_capture import Frame, InternalCaptureControl, WindowsCapture


_user32 = ctypes.windll.user32

_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


# Required Lineage client size — anything else means the calibrated
# pixel positions are off and OCR / pixel-mask read garbage. Monitor
# raises window_size_wrong until the user fixes it.
EXPECTED_CLIENT_SIZE = (1280, 960)


def _iter_visible_windows():
    results = []

    def cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        n = _user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        _user32.GetWindowTextW(hwnd, buf, n + 1)
        results.append((hwnd, buf.value))
        return True

    _user32.EnumWindows(_EnumWindowsProc(cb), 0)
    return results


def find_game_window(needle: str = "Lineage") -> Optional[int]:
    """Return the HWND of the first visible window whose title contains
    ``needle`` (case-sensitive substring match), or None.
    """
    for hwnd, title in _iter_visible_windows():
        if needle in title:
            return hwnd
    return None


def get_window_title(hwnd: int) -> str:
    n = _user32.GetWindowTextLengthW(hwnd)
    if n == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def get_client_size(hwnd: int) -> tuple[int, int]:
    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    r = _RECT()
    _user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right, r.bottom


def grab_frame(needle: str = "Lineage", *, timeout: float = 3.0) -> Image.Image:
    """Capture one frame of the matching window via WGC.

    Blocks until a frame arrives (typically <100 ms after start), then
    stops the capture session. Raises RuntimeError on timeout / not found.
    """
    title = None
    for hwnd, t in _iter_visible_windows():
        if needle in t:
            title = t
            break
    if title is None:
        raise RuntimeError(f"window matching {needle!r} not found")

    cap = WindowsCapture(
        cursor_capture=False,
        draw_border=False,
        monitor_index=None,
        window_name=needle,
    )

    state = {"img": None, "err": None}
    done = threading.Event()

    @cap.event
    def on_frame_arrived(frame: Frame, control: InternalCaptureControl):
        if state["img"] is not None:
            return
        try:
            buf = bytes(frame.frame_buffer)
            state["img"] = Image.frombuffer(
                "RGB", (frame.width, frame.height),
                buf, "raw", "BGRX", 0, 1,
            )
        except Exception as e:  # noqa: BLE001
            state["err"] = e
        finally:
            control.stop()
            done.set()

    @cap.event
    def on_closed():
        done.set()

    cap.start()  # blocks until control.stop()
    if not done.wait(timeout):
        raise RuntimeError("capture timed out")
    if state["err"]:
        raise state["err"]
    if state["img"] is None:
        raise RuntimeError("no frame received")
    return state["img"]


# ──────────────────────────── ROI helpers ────────────────────────────

# Hard-coded for 1920×1032 client area, Lineage Classic in maximized window.
# Re-survey when running at a different resolution.
ROI_1280x960 = {
    # Calibrated against a real 1280×960 capture (frame is 1282×992
    # because WGC includes the 1-px border + 31-px title bar).
    # All coordinates are in *frame* space, not client space.
    "hp_text":     (330, 788, 540, 825),    # "HP:308/308" white on red
    "mp_text":     (680, 788, 880, 825),    # "MP:116/116" white on purple
    "level_exp":   (15,  808, 290, 832),    # orange ribbon "LEV:28 79.1664%"
    "debuffs":     (60,  848, 215, 928),    # 2x2 status icons + values
    "lawful":      (60,  930, 270, 965),    # "Lawful  32767"
    "chat_log":    (310, 808, 1080, 970),   # chat / system messages
    "action_bar":  (1080, 770, 1282, 970),  # F1 tabs + 4×3 skill grid
    # Status sub-cells split out of `debuffs` (155×80, 2×2) so each
    # field has its own tight ROI for OCR. Coordinates are absolute
    # in frame space, not relative to the parent debuffs box.
    "defense":     (60,  848, 137, 888),    # top-left:    [icon] N
    "mdef":        (137, 848, 215, 888),    # top-right:   [icon] N%
    "weight":      (60,  888, 137, 928),    # bottom-left: [icon] N%
    "hunger":      (137, 888, 215, 928),    # bottom-right (orange): [icon] N%
    # Sundial time bar, just below Lawful. Spans most of the bottom
    # row of the left UI pane — the cream-yellow cursor moves L→R
    # as game time advances. Left half = night, right half = day.
    "time_icon":   (72,  965, 270, 985),
}


# Active ROI set — switched when monitor detects the client size.
ROI_1920x1032 = {
    # Calibrated against a maximized 1920×1032 client window with the
    # chat panel collapsed. Re-measure when the in-game UI scale changes.
    # OCR accuracy drops fast if these are too loose — keep them snug.
    "hp_text":     (700, 808, 870,  838),     # "HP:308/308" inside the red bar
    "mp_text":     (980, 808, 1140, 838),     # "MP:116/116" inside the purple bar
    "level_exp":   (290, 815, 540, 850),      # orange ribbon "LEV:28  79.1664%"
    "debuffs":     (290, 858, 540, 955),      # 2 rows × 2 cols (-13/19% + 29%/100%)
    "lawful":      (290, 955, 540, 990),      # "Lawful  32767"
    "chat_log":    (540, 860, 1320, 1020),    # chat / system messages strip
    "action_bar":  (1320, 800, 1820, 1020),   # F1-F3 tabs + 4×3 skill grid
}


def parse_hpmp(text_lines: list[str],
               expected_max: int | None = None) -> tuple[int, int] | None:
    """Pull (current, max) from RapidOCR output of an HP/MP ROI.

    OCR mis-reads the slash three different ways depending on font size:
      * "308/308" → ['308', '1308']   (slash → '1' splits the token)
      * "308/308" → ['HP:308/308']    (slash kept, regex finds two ints)
      * "308/308" → ['HP:3087308']    (slash → '7'/'1' fuses one token)

    The fused case is ambiguous when current and max have different
    digit counts ("507308" might be 50/308 or 507/308). When we know
    ``expected_max`` from a previous good OCR, we anchor on it; without
    it we try 3-digit, 4-digit, 2-digit max in order and reject splits
    where current > max.
    """
    import re
    nums = []
    for t in text_lines:
        for m in re.finditer(r"\d+", t):
            nums.append(m.group())

    if len(nums) >= 2:
        cur, raw_max = int(nums[0]), int(nums[1])
        s = str(raw_max)
        # Slash misread as leading '1' (e.g. "308/308" → "1308")
        if s.startswith("1") and len(s) == len(str(cur)) + 1:
            raw_max = int(s[1:])
        return cur, raw_max

    if len(nums) != 1:
        return None

    s = nums[0]

    # Best case: anchor on a known max. The slash usually became a single
    # digit between cur and max, so the token looks like CUR + ?CHAR + MAX.
    if expected_max is not None:
        mstr = str(expected_max)
        if s.endswith(mstr) and len(s) > len(mstr):
            cur_str = s[:-len(mstr) - 1]  # drop the artefact char
            if cur_str.isdigit():
                return int(cur_str), expected_max

    # No max hint — try a few common max-digit lengths and pick one
    # where 0 <= cur <= max.
    for max_digits in (3, 4, 2):
        if len(s) < max_digits + 2:
            continue
        mstr = s[-max_digits:]
        cur_str = s[:-(max_digits + 1)]  # skip artefact char
        if not (cur_str.isdigit() and mstr.isdigit()):
            continue
        cur, mx = int(cur_str), int(mstr)
        if 0 <= cur <= mx:
            return cur, mx
    return None


# Lazy-loaded RapidOCR instance — heavy import (~1.5s + model load)
_OCR_ENGINE = None


def _get_ocr():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


# Some ROIs OCR better at native size — orange-on-orange ribbons lose
# their already-low contrast when bicubically upscaled.
NO_UPSCALE_ROIS = {"level_exp"}


def ocr_rois(img: Image.Image,
             rois: dict | None = None) -> dict[str, list[str]]:
    """Run OCR on every ROI in ``rois``. Returns ``{name: [text_lines]}``.

    Small ROIs are auto-upscaled 2× to clear RapidOCR's detection floor,
    *except* names listed in ``NO_UPSCALE_ROIS`` which read better raw.
    """
    import numpy as np
    if rois is None:
        rois = ROI_1920x1032
    ocr = _get_ocr()
    out = {}
    for name, box in rois.items():
        crop = img.crop(box)
        if name in NO_UPSCALE_ROIS:
            src = crop
        elif max(crop.size) < 600:
            src = upscale_for_ocr(crop, 2)
        else:
            src = crop
        result, _ = ocr(np.array(src))
        out[name] = [t for _, t, _ in result] if result else []
    return out


def parse_level_exp(text_lines: list[str]) -> tuple[str | None, str | None]:
    """Reconstruct (level, exp_pct) from RapidOCR output of the orange ribbon.

    OCR splits "LEV:28  79.1664%" into something like
    ``["E11", "28", "79", "1664%"]`` — the LEV prefix becomes garbage,
    and the floating-point gets cut at the decimal. We:

      * collect numeric tokens in reading order, noting which carries '%'
      * find a (digits, digits%) adjacent pair → that's the EXP value,
        joined back as "{int}.{frac}%"
      * the level is the most recent 1–2-digit number (in 1..99) seen
        *before* that pair; falls back to the same scan over all tokens.
    """
    import re
    tokens: list[tuple[str, bool]] = []
    for t in text_lines:
        for m in re.finditer(r"(\d+)(%?)", t):
            tokens.append((m.group(1), m.group(2) == "%"))

    exp = None
    pct_idx: int | None = None
    for i in range(len(tokens) - 1, 0, -1):
        if tokens[i][1] and not tokens[i - 1][1]:
            exp = f"{tokens[i-1][0]}.{tokens[i][0]}%"
            pct_idx = i - 1
            break

    if exp is None:
        # Direct decimal hit: `\d+\.\d+` covers cases where the trailing
        # '%' got mis-OCR'd as '8' or dropped — joined output looks like
        # 'EV:28 79.16648' rather than '79 1664%'.
        joined = " ".join(text_lines)
        m = re.search(r"(\d{1,2})\.(\d{2,5})", joined)
        if m:
            decimal = m.group(2)[:4]  # cap to 4 decimals to drop OCR's % artefact
            exp = f"{m.group(1)}.{decimal}%"

    def _first_level(seq) -> str | None:
        for tok, _ in seq:
            if 1 <= len(tok) <= 2 and 1 < int(tok) < 100:
                return tok
        return None

    lv = None
    if pct_idx is not None:
        lv = _first_level(reversed(tokens[:pct_idx]))
    if lv is None:
        lv = _first_level(tokens)

    return lv, exp


# ──────────────────────────── HP / MP pixel masks ────────────────────────────

# Bar fill rectangles. Calibrated for 1920×1032 currently; the
# 1280×960 boxes below get swapped in by GameMonitor when the game
# is at the supported size.
#
# A dragon-head ornament sits over the centre of the bar — it's white
# and never matches the red mask, so it shows up as a 10-px gap. The
# 'rightmost matching column' algorithm correctly skips over the gap.
HP_BAR_BOX_1920 = (570, 824, 825, 840)
MP_BAR_BOX_1920 = (970, 824, 1225, 840)
HP_BAR_BOX_1280 = (282, 796, 562, 820)
MP_BAR_BOX_1280 = (688, 796, 937, 820)

# Active boxes — flipped by GameMonitor on attach
HP_BAR_BOX = HP_BAR_BOX_1920
MP_BAR_BOX = MP_BAR_BOX_1920


def _column_coverage(arr_mask) -> float:
    """Fraction of columns that contain at least one matching pixel.

    Direction-agnostic — works whether the bar fills left-to-right,
    right-to-left, or shrinks from both ends. Lineage's HP bar
    actually drains from the *left* (full HP = full red, low HP =
    bright red on the right with grey crust on the left), so the
    earlier 'rightmost matching column' approach always returned 1.0.
    """
    cols = arr_mask.any(axis=0)
    return cols.sum() / cols.size if cols.size else 0.0


def hp_fill_ratio(img: Image.Image) -> float:
    """Fraction of the HP bar that's filled (0.0–1.0), via pixel mask.

    Mask matches the bar's saturated deep red only — the empty trough
    is desaturated grey/dark crimson and bright peach trim above is
    desaturated (G,B >> 0). Pure red fill has R≈125, G≈9, B≈0 — easy
    to isolate via R > 3·G and R > 3·B with R > 80.
    """
    import numpy as np
    arr = np.asarray(img.crop(HP_BAR_BOX))
    R = arr[..., 0].astype(int)
    G = arr[..., 1].astype(int)
    B = arr[..., 2].astype(int)
    mask = (R > 80) & (R > G * 3) & (R > B * 3)
    return _column_coverage(mask)


def mp_fill_ratio(img: Image.Image) -> float:
    """Fraction of the MP bar that's filled (0.0–1.0)."""
    import numpy as np
    arr = np.asarray(img.crop(MP_BAR_BOX))
    R = arr[..., 0].astype(int)
    G = arr[..., 1].astype(int)
    B = arr[..., 2].astype(int)
    # MP bar is desaturated purple — B always slightly above R and G.
    mask = (B > 80) & (B > R) & (B > G)
    return _column_coverage(mask)


# ──────────────────────────── FrameStreamer ────────────────────────────

class FrameStreamer:
    """Persistent WGC session that keeps the latest frame in memory.

    Created on demand by GameMonitor — kept alive for the lifetime of
    the app so per-frame readers (HP/MP pixel mask) don't pay the
    ~275 ms WGC start-up tax on every poll.

    WGC fires `on_frame_arrived` at the compositor's pace (typically
    60 Hz). We throttle the PIL conversion to ~10 Hz so we don't burn
    CPU memcpy'ing 8 MB / frame at 60 Hz when the consumer reads at 5.
    """

    THROTTLE_S = 0.1  # min interval between PIL conversions

    def __init__(self, needle: str = "Lineage") -> None:
        import time as _t
        self._latest: Image.Image | None = None
        self._lock = threading.Lock()
        self._stopped = False
        self._last_decode_t = 0.0

        cap = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            monitor_index=None,
            window_name=needle,
        )

        @cap.event
        def on_frame_arrived(frame: Frame, control: InternalCaptureControl):
            if self._stopped:
                control.stop()
                return
            now = _t.monotonic()
            if now - self._last_decode_t < self.THROTTLE_S:
                return
            self._last_decode_t = now
            try:
                buf = bytes(frame.frame_buffer)
                img = Image.frombuffer(
                    "RGB", (frame.width, frame.height),
                    buf, "raw", "BGRX", 0, 1,
                )
            except Exception:
                return
            with self._lock:
                self._latest = img

        @cap.event
        def on_closed():
            pass

        # start_free_threaded() runs WGC on its own thread. Returns
        # immediately. Frames start arriving within ~250 ms.
        cap.start_free_threaded()
        self._cap = cap

    def latest(self) -> Image.Image | None:
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self._stopped = True


# ──────────────────────────── GameMonitor ────────────────────────────

class GameMonitor:
    """Two-rate poller for the game window:

      * Fast loop (default 200 ms / 5 Hz) — HP / MP via template match.
        Sub-millisecond, exact integer. The bar text is rendered in a
        fixed pixel font on a fixed grid — Hamming distance against
        per-glyph 10×10 binary templates is deterministic, never wrong.
      * Slow loop (default 5000 ms) — RapidOCR for LV / EXP / Lawful
        (the non-HP/MP fields whose layout / font isn't fixed enough
        for templates).

    Holds a single FrameStreamer that keeps WGC running, so each tick
    is a memory read (~1 ms) instead of a fresh capture (~275 ms).

    Embedding (typically in MainWindow):

        self.monitor = GameMonitor()
        self.monitor.hp_changed.connect(self._on_hp)
        ...
        self.monitor.start()
    """

    def __init__(
        self,
        fast_ms: int = 200,
        slow_ms: int = 5000,
        needle: str = "Lineage",
        # Back-compat alias used by the older single-rate constructor.
        interval_ms: int | None = None,
    ) -> None:
        if interval_ms is not None:
            slow_ms = interval_ms
        from PySide6 import QtCore
        from digit_match import load_templates
        self._templates = load_templates()

        # We can't subclass QObject inside the function, so we compose
        # — an inner QObject holds the signals, and the public surface
        # mirrors them.
        class _Signals(QtCore.QObject):
            hp_changed = QtCore.Signal(int, int)         # (current, max)
            mp_changed = QtCore.Signal(int, int)
            level_changed = QtCore.Signal(str)
            exp_changed = QtCore.Signal(str)
            lawful_changed = QtCore.Signal(int)
            defense_changed = QtCore.Signal(int)
            mdef_changed = QtCore.Signal(int)            # percent
            weight_changed = QtCore.Signal(int)          # percent
            hunger_changed = QtCore.Signal(int)          # percent
            time_changed = QtCore.Signal(str)            # "day" | "night"
            account_changed = QtCore.Signal(str)         # account id from window title
            connection_changed = QtCore.Signal(bool, str)  # (online, message)
            window_size_wrong = QtCore.Signal(int, int)  # actual (w, h) when mismatched
            poll_started = QtCore.Signal()
            poll_finished = QtCore.Signal(float)         # latency_ms

        self._sig = _Signals()
        self.hp_changed = self._sig.hp_changed
        self.mp_changed = self._sig.mp_changed
        self.level_changed = self._sig.level_changed
        self.exp_changed = self._sig.exp_changed
        self.lawful_changed = self._sig.lawful_changed
        self.defense_changed = self._sig.defense_changed
        self.mdef_changed = self._sig.mdef_changed
        self.weight_changed = self._sig.weight_changed
        self.hunger_changed = self._sig.hunger_changed
        self.time_changed = self._sig.time_changed
        self.account_changed = self._sig.account_changed
        self.connection_changed = self._sig.connection_changed
        self.window_size_wrong = self._sig.window_size_wrong
        self.poll_started = self._sig.poll_started
        self.poll_finished = self._sig.poll_finished
        self._last_account: str | None = None
        self._last_size: tuple[int, int] | None = None

        self._fast_timer = QtCore.QTimer()
        self._fast_timer.timeout.connect(self._fast_poll)
        self._fast_ms = fast_ms

        self._slow_timer = QtCore.QTimer()
        self._slow_timer.timeout.connect(self._slow_poll)
        self._slow_ms = slow_ms

        self._needle = needle
        self._busy = False        # serialises slow OCR worker
        self._connected: bool | None = None
        self._streamer: FrameStreamer | None = None
        self._hp_max: int | None = None
        self._mp_max: int | None = None

        # Decoration offset — frame coords shift relative to the
        # baseline (1280×960 client → 1282×992 frame, title=31,
        # border=1) when the game window is on a monitor with
        # different DPI / theme / chrome sizes. Re-computed on first
        # frame after attach by comparing streamer frame size to the
        # baseline expected for the detected client size.
        self._roi_offset: tuple[int, int] = (0, 0)
        self._roi_baseline_set: bool = False
        self._roi_src: dict | None = None

        # The fast loop reads HP/MP via template match (sub-ms). The
        # slow loop OCRs the rest. Drop chat (no bot signal) and HP/MP
        # (owned by fast loop). Drop the parent `debuffs` ROI too since
        # we OCR each of its 4 sub-cells (defense / mdef / weight /
        # hunger) individually for higher reliability.
        self._poll_rois = {
            k: v for k, v in ROI_1920x1032.items()
            if k not in ("chat_log", "hp_text", "mp_text", "debuffs")
        }
        self._hp_box = ROI_1920x1032["hp_text"]
        self._mp_box = ROI_1920x1032["mp_text"]
        self._time_icon_box = ROI_1920x1032.get("time_icon")

        # Per-field OCR + agreement + bitmap-cache readers for the
        # status zone. These don't run RapidOCR themselves — they take
        # the OCR text we already produced and validate / cache.
        from status_reader import make_default_readers
        self._field_readers = make_default_readers()

    def start(self) -> None:
        # Force OCR model init on the main thread *before* any worker
        # spawns. RapidOCR / onnxruntime hangs forever if its first init
        # happens inside a thread spawned under a running Qt event loop.
        # Costs ~800 ms one-shot on first launch.
        _get_ocr()

        self._try_attach()
        if not self._fast_timer.isActive():
            self._fast_timer.start(self._fast_ms)
        if not self._slow_timer.isActive():
            self._slow_timer.start(self._slow_ms)
        # Fire once immediately so HP/MP populate without waiting a tick.
        self._fast_poll()
        self._slow_poll()

    def stop(self) -> None:
        self._fast_timer.stop()
        self._slow_timer.stop()
        if self._streamer is not None:
            self._streamer.stop()
            self._streamer = None

    def set_interval(self, ms: int) -> None:
        """Back-compat alias — adjusts the slow (OCR) interval."""
        self._slow_ms = ms
        if self._slow_timer.isActive():
            self._slow_timer.start(ms)

    def trigger_now(self) -> None:
        """Force an immediate slow OCR pass on top of the periodic ones."""
        self._slow_poll()

    # ── internals ────────────────────────────────────────────────

    def _try_attach(self) -> bool:
        """Find the game window + spin up a FrameStreamer if not already.

        Also checks the client size against ``EXPECTED_CLIENT_SIZE`` and
        flips the active ROI / pixel-mask boxes to match. Bails out
        (with ``window_size_wrong``) if the game isn't at a supported
        size — capture would still work but every coordinate would be
        wrong, so we wait for the user to resize.
        """
        import re
        global HP_BAR_BOX, MP_BAR_BOX
        hwnd = find_game_window(self._needle)
        if hwnd is None:
            self._set_connection(False, f"未偵測到 {self._needle} 視窗")
            return False

        size = get_client_size(hwnd)
        if size != self._last_size:
            self._last_size = size
            self._roi_baseline_set = False  # re-calibrate offset
            if size == (1280, 960):
                self._roi_src = ROI_1280x960
            elif size == (1920, 1032):
                self._roi_src = ROI_1920x1032
            else:
                self._roi_src = None
            if self._roi_src is None:
                self.window_size_wrong.emit(*size)
                self._set_connection(
                    False,
                    f"視窗大小 {size[0]}×{size[1]} 不支援（需 1280×960）",
                )
                return False
            # Apply ROIs with current offset (0,0 until a frame measures).
            self._apply_roi_offset()

        # Account id from window title — cheap, no OCR.
        title = get_window_title(hwnd)
        m_account = re.search(r"Login\s*\[([^\]]+)\]", title)
        if m_account:
            acc = m_account.group(1).strip()
            if acc != self._last_account:
                self._last_account = acc
                self.account_changed.emit(acc)

        if self._streamer is None:
            try:
                self._streamer = FrameStreamer(self._needle)
            except Exception as e:  # noqa: BLE001
                self._set_connection(False, f"無法附加 WGC: {e}")
                return False
        self._set_connection(True, f"已連接 {self._needle} {size[0]}×{size[1]}")
        return True

    def _calibrate_roi_offset(self, frame_img) -> None:
        """One-shot calibration after the first WGC frame arrives.

        ROIs were measured against the dev machine's chrome (1-px
        border, 31-px title bar). On another monitor / DPI / theme
        the title bar runs 45-50 px and shifts every ROI down — HP
        text crops then sample brass trim above the bar instead of
        the digits and template match returns nothing.

        Step 1: compute a coarse offset from chrome-size delta.
        Step 2: scan ±3 px around the coarse Y offset, picking the
                 first value that makes ``read_hp`` succeed. Real
                 monitors have sub-pixel rendering noise that makes
                 the chrome-size formula off-by-one occasionally.
        """
        if self._last_size is None:
            return
        cw, ch = self._last_size
        fw, fh = frame_img.size
        v_chrome = fh - ch
        h_chrome = fw - cw
        coarse = (h_chrome // 2 - 1, v_chrome - 32)
        self._roi_offset = coarse
        self._apply_roi_offset()
        self._roi_baseline_set = True

        # Fine-tune: try ±3 px Y shifts; whichever lets read_hp
        # parse a value wins. read_hp is fast (~0.3 ms) so the scan
        # is cheap.
        import numpy as np
        from digit_match import read_hp
        best_dy = coarse[1]
        for dy_try in (coarse[1], coarse[1] - 1, coarse[1] + 1,
                       coarse[1] - 2, coarse[1] + 2,
                       coarse[1] - 3, coarse[1] + 3):
            self._roi_offset = (coarse[0], dy_try)
            self._apply_roi_offset()
            try:
                hp_arr = np.asarray(frame_img.crop(self._hp_box))
                hp = read_hp(hp_arr, self._templates)
            except Exception:  # noqa: BLE001
                hp = None
            if hp is not None:
                best_dy = dy_try
                break
        self._roi_offset = (coarse[0], best_dy)
        self._apply_roi_offset()

    def _apply_roi_offset(self) -> None:
        """Re-derive ``_poll_rois`` / ``_hp_box`` / ``_mp_box`` /
        ``_time_icon_box`` from ``_roi_src`` plus the current
        ``_roi_offset``."""
        if self._roi_src is None:
            return
        dx, dy = self._roi_offset

        def shift(roi):
            return (roi[0] + dx, roi[1] + dy, roi[2] + dx, roi[3] + dy)

        self._poll_rois = {
            k: shift(v)
            for k, v in self._roi_src.items()
            if k not in ("chat_log", "hp_text", "mp_text", "debuffs")
        }
        self._hp_box = shift(self._roi_src["hp_text"])
        self._mp_box = shift(self._roi_src["mp_text"])
        time_box = self._roi_src.get("time_icon")
        self._time_icon_box = shift(time_box) if time_box else None

    def _fast_poll(self) -> None:
        """HP/MP via template match — sub-millisecond, exact integer."""
        if self._streamer is None:
            return
        img = self._streamer.latest()
        if img is None:
            return
        # First frame after attach: calibrate ROI offset for this
        # monitor's window decoration size.
        if not self._roi_baseline_set:
            self._calibrate_roi_offset(img)
        import numpy as np
        from digit_match import read_hp, read_mp
        hp_arr = np.asarray(img.crop(self._hp_box))
        mp_arr = np.asarray(img.crop(self._mp_box))
        hp = read_hp(hp_arr, self._templates)
        if hp:
            self._hp_max = hp[1]
            self.hp_changed.emit(*hp)
        mp = read_mp(mp_arr, self._templates)
        if mp:
            self._mp_max = mp[1]
            self.mp_changed.emit(*mp)

    def _slow_poll(self) -> None:
        if self._busy:
            return
        self._busy = True
        import threading
        threading.Thread(target=self._slow_worker, daemon=True).start()

    def _slow_worker(self) -> None:
        import re
        import time as _time
        t0 = _time.time()
        self.poll_started.emit()
        try:
            if self._streamer is None:
                if not self._try_attach():
                    return
            assert self._streamer is not None
            img = self._streamer.latest()
            if img is None:
                # Streamer hasn't produced a frame yet. Give it a beat.
                _time.sleep(0.3)
                img = self._streamer.latest()
                if img is None:
                    return

            # HP/MP are read by the fast loop via template match. The
            # slow loop OCRs LV/EXP, the 4 status sub-cells, and Lawful.
            ocr = ocr_rois(img, self._poll_rois)

            lv, exp = parse_level_exp(ocr.get("level_exp", []))
            if lv:
                self.level_changed.emit(lv)
            if exp:
                self.exp_changed.emit(exp)

            # Status zone: feed each field's OCR text into its
            # FieldReader (which validates + agreement-confirms +
            # bitmap-caches). Emit signal only if the reader has a
            # confirmed value.
            import numpy as np
            for field, signal in (
                ("defense", self.defense_changed),
                ("mdef",    self.mdef_changed),
                ("weight",  self.weight_changed),
                ("hunger",  self.hunger_changed),
                ("lawful",  self.lawful_changed),
            ):
                if field not in self._poll_rois:
                    continue
                text = " ".join(ocr.get(field, []))
                box = self._poll_rois[field]
                crop_arr = np.asarray(img.crop(box))
                v = self._field_readers[field].read(crop_arr, text)
                if v is not None:
                    signal.emit(v)

            # Time of day — separate path (icon, not OCR).
            if self._time_icon_box is not None:
                from status_reader import classify_time_of_day
                arr = np.asarray(img.crop(self._time_icon_box))
                tod = classify_time_of_day(arr)
                if tod is not None:
                    self.time_changed.emit(tod)

        except Exception as e:  # noqa: BLE001
            self._set_connection(False, f"錯誤: {type(e).__name__}: {e}")
        finally:
            self._busy = False
            self.poll_finished.emit((_time.time() - t0) * 1000)

    def _set_connection(self, ok: bool, msg: str) -> None:
        if ok != self._connected:
            self._connected = ok
            self.connection_changed.emit(ok, msg)


def upscale_for_ocr(img: Image.Image, factor: int = 2) -> Image.Image:
    """Bicubic upscale of a tight ROI before OCR.

    RapidOCR's detection step has a minimum-text-size threshold; tight
    HP/MP boxes (height ~30 px) often fall under it. 2× upscale fixes
    that without changing the bytes the OCR sees.
    """
    return img.resize(
        (img.size[0] * factor, img.size[1] * factor),
        Image.BICUBIC,
    )


def crop(image: Image.Image, roi: tuple[int, int, int, int]) -> Image.Image:
    """Crop ``image`` to the given (x1, y1, x2, y2) box."""
    return image.crop(roi)
