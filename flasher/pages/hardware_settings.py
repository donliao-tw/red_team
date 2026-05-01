"""硬體設定 — Arduino board management, firmware flashing, VID/PID spoofing."""
from __future__ import annotations

import threading
import time
from datetime import datetime

import serial
from PySide6 import QtCore, QtGui, QtWidgets

import board as board_module
import board_client
import flash
import profiles
import style
import widgets
from ._base import Page


class HardwareSettingsPage(Page):
    title = "硬體設定"
    subtitle = "Arduino 偵測 / 韌體燒錄 / VID·PID 偽裝"

    # Signals fired from worker threads → main thread (queued by Qt).
    log_emitted = QtCore.Signal(str)
    op_done = QtCore.Signal(bool, str)

    def build(self) -> None:
        self._busy = False
        self._boards: list[board_module.BoardInfo] = []

        self.log_emitted.connect(self._append_log)
        self.op_done.connect(self._on_op_done)

        self.body_layout.setSpacing(12)

        # Top row: 3 cards side by side. Log fills the rest below.
        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        top.addWidget(self._build_board_card(),   stretch=1)
        top.addWidget(self._build_profile_card(), stretch=1)
        top.addWidget(self._build_action_card(),  stretch=1)
        self.body_layout.addLayout(top)

        self.body_layout.addWidget(self._build_log_card(), stretch=1)

        # Initial scan after the page is shown.
        QtCore.QTimer.singleShot(50, self.refresh_boards)

    # ------------------------------------------------------------------ board

    def _build_board_card(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("板子偵測")

        self.board_combo = QtWidgets.QComboBox()
        self.board_combo.addItem("（沒有偵測到板子）")
        self.board_combo.setMinimumHeight(32)
        layout.addWidget(self.board_combo)

        self.refresh_btn = QtWidgets.QPushButton("重新掃描")
        self.refresh_btn.setMinimumHeight(32)
        self.refresh_btn.clicked.connect(self.refresh_boards)
        layout.addWidget(self.refresh_btn)

        layout.addStretch(1)
        return card

    # ------------------------------------------------------------------ profile

    def _build_profile_card(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("偽裝設定檔")

        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItems(profiles.names())
        self.profile_combo.setCurrentText(profiles.get(profiles.DEFAULT_KEY).name)
        self.profile_combo.setMinimumHeight(32)
        self.profile_combo.currentTextChanged.connect(self._on_profile_change)
        layout.addWidget(self.profile_combo)

        self.profile_detail = QtWidgets.QLabel("")
        self.profile_detail.setStyleSheet(
            f"font-family: {style.FAMILY_MONO}; color: {style.TEXT_SECONDARY};"
        )
        self.profile_detail.setWordWrap(True)
        layout.addWidget(self.profile_detail)

        self._on_profile_change(self.profile_combo.currentText())
        layout.addStretch(1)
        return card

    def _on_profile_change(self, name: str) -> None:
        try:
            p = profiles.by_name(name)
        except KeyError:
            return
        self.profile_detail.setText(
            f"VID: 0x{p.vid:04X}    PID: 0x{p.pid:04X}\n"
            f"Product:       {p.product}\n"
            f"Manufacturer:  {p.manufacturer}"
        )

    # ------------------------------------------------------------------ actions

    def _build_action_card(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("動作")

        self.flash_btn = QtWidgets.QPushButton("編譯並燒錄")
        self.flash_btn.setObjectName("destructive")
        self.flash_btn.setMinimumHeight(34)
        self.flash_btn.clicked.connect(self._do_flash)

        self.compile_btn = QtWidgets.QPushButton("僅編譯（不燒錄）")
        self.compile_btn.setObjectName("secondary")
        self.compile_btn.setMinimumHeight(34)
        self.compile_btn.clicked.connect(self._do_compile)

        self.reset_btn = QtWidgets.QPushButton("軟重置（1200bps）")
        self.reset_btn.setObjectName("secondary")
        self.reset_btn.setMinimumHeight(34)
        self.reset_btn.clicked.connect(self._do_reset)

        self.ping_btn = QtWidgets.QPushButton("Ping 測試")
        self.ping_btn.setObjectName("secondary")
        self.ping_btn.setMinimumHeight(34)
        self.ping_btn.clicked.connect(self._do_ping)

        layout.addWidget(self.flash_btn)
        layout.addWidget(self.compile_btn)
        layout.addWidget(self.reset_btn)
        layout.addWidget(self.ping_btn)
        layout.addStretch(1)
        return card

    # ------------------------------------------------------------------ log

    def _build_log_card(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("日誌", expand=True)

        # Header row: title (already in card) + clear button on right
        header_row, h = self._row()
        h.addStretch(1)
        clear_btn = QtWidgets.QPushButton("清除")
        clear_btn.setObjectName("secondary")
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(self._clear_log)
        h.addWidget(clear_btn)
        layout.addWidget(header_row)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(140)
        font = QtGui.QFont(style.FAMILY_MONO, 10)
        self.log_box.setFont(font)
        layout.addWidget(self.log_box, stretch=1)

        return card

    # ------------------------------------------------------------------ helpers

    def _row(self) -> tuple[QtWidgets.QWidget, QtWidgets.QHBoxLayout]:
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        return w, h

    def _selected_board(self) -> board_module.BoardInfo | None:
        idx = self.board_combo.currentIndex()
        if idx < 0 or idx >= len(self._boards):
            return None
        return self._boards[idx]

    def refresh_boards(self) -> None:
        self._boards = board_module.list_serial_ports()
        self.board_combo.clear()
        if not self._boards:
            self.board_combo.addItem("（沒有偵測到板子）")
            self.app.set_status("未連接", ok=False)
            self._append_log("沒有偵測到任何 USB 序列裝置。")
            return

        # Ping every visible port — VID/PID is spoofed (Logitech /
        # Razer / MS) so KNOWN_BOARDS doesn't match the runtime
        # firmware. The hid_mouse board is whichever port responds
        # with "pong" + a "hid_mouse v..." version string.
        hid_mouse_idx: int | None = None
        version_by_idx: dict[int, str] = {}
        for i, b in enumerate(self._boards):
            v = self._ping_one(b.port)
            if v:
                version_by_idx[i] = v
                if hid_mouse_idx is None:
                    hid_mouse_idx = i

        for i, b in enumerate(self._boards):
            label = b.label
            if i in version_by_idx:
                label += f"  ✅ {version_by_idx[i]}"
            self.board_combo.addItem(label)

        # Auto-select: a flashed hid_mouse board first; failing that,
        # any KNOWN_BOARDS entry (only matches if the board is in
        # bootloader / unflashed state).
        if hid_mouse_idx is not None:
            self.board_combo.setCurrentIndex(hid_mouse_idx)
        else:
            for i, b in enumerate(self._boards):
                if b.known is not None:
                    self.board_combo.setCurrentIndex(i)
                    break

        chosen = self._selected_board()
        if chosen and self.board_combo.currentIndex() in version_by_idx:
            self.app.set_status(
                f"已連接 hid_mouse @ {chosen.port}", ok=True,
            )
        elif chosen and chosen.known is not None:
            self.app.set_status(
                f"未燒錄板子 @ {chosen.port}（請先燒錄）", ok=None,
            )
        else:
            self.app.set_status("找不到 hid_mouse 板", ok=False)
        self._append_log(
            f"偵測到 {len(self._boards)} 個裝置，"
            f"{len(version_by_idx)} 個是已燒錄的 hid_mouse"
        )

    @staticmethod
    def _ping_one(port: str) -> str | None:
        """Open the port, ping, return the firmware version string, or
        None on failure. Quick (~120 ms / port) — drains right after."""
        try:
            client = board_client.BoardClient(port, timeout_s=0.3)
        except Exception:  # noqa: BLE001
            return None
        try:
            if not client.ping():
                return None
            return client.version()
        except Exception:  # noqa: BLE001
            return None
        finally:
            client.close()

    # ------------------------------------------------------------------ actions

    def _do_compile(self) -> None:
        if self._busy:
            return
        profile = profiles.by_name(self.profile_combo.currentText())
        self._run_async(
            label=f"編譯 ({profile.name})",
            fn=lambda log: flash.compile_sketch(profile, on_log=log),
        )

    def _do_flash(self) -> None:
        if self._busy:
            return
        b = self._selected_board()
        if b is None:
            self._append_log("[失敗] 請先選擇板子")
            return
        profile = profiles.by_name(self.profile_combo.currentText())
        self._run_async(
            label=f"編譯並燒錄 ({profile.name} → {b.port})",
            fn=lambda log: flash.flash_with_reset(profile, b.port, on_log=log),
        )

    def _do_reset(self) -> None:
        b = self._selected_board()
        if b is None:
            self._append_log("[失敗] 請先選擇板子")
            return
        self._append_log(f"== 軟重置 {b.port} ==")
        self._run_async(
            label="soft_reset",
            fn=lambda log: (board_module.soft_reset(b.port), True)[1],
        )

    def _do_ping(self) -> None:
        b = self._selected_board()
        if b is None:
            self._append_log("[失敗] 請先選擇板子")
            return

        def ping(log):
            log(f"== Ping {b.port} @115200 ==")
            try:
                with serial.Serial(b.port, 115200, timeout=1.0) as s:
                    time.sleep(0.2)
                    s.reset_input_buffer()
                    s.write(b"P\n")
                    s.write(b"V\n")
                    deadline = time.time() + 1.5
                    got_any = False
                    while time.time() < deadline:
                        line = s.readline().decode("utf-8", errors="replace").rstrip()
                        if line:
                            log(f"  <- {line}")
                            got_any = True
                    if not got_any:
                        log("[失敗] 板子沒有回應 (是否已燒錄 hid_mouse 韌體？)")
                        return False
                    return True
            except serial.SerialException as e:
                log(f"[失敗] {e}")
                return False

        self._run_async(label="ping", fn=ping)

    # ------------------------------------------------------------------ async / log

    def _run_async(self, *, label: str, fn) -> None:
        self._set_busy(True)
        self._append_log(f"--- {label} 開始 ---")

        def worker():
            try:
                ok = fn(self.log_emitted.emit)
            except Exception as e:
                self.log_emitted.emit(f"[exception] {e!r}")
                ok = False
            self.op_done.emit(ok, label)

        threading.Thread(target=worker, daemon=True).start()

    def _on_op_done(self, ok: bool, label: str) -> None:
        self._append_log(f"--- {label} {'完成' if ok else '失敗'} ---")
        self._set_busy(False)
        # Re-scan the board list — VID/PID may have changed after flash.
        QtCore.QTimer.singleShot(800, self.refresh_boards)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for btn in (self.flash_btn, self.compile_btn, self.reset_btn,
                    self.ping_btn, self.refresh_btn):
            btn.setEnabled(not busy)

    def _append_log(self, line: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{ts}] {line}")

    def _clear_log(self) -> None:
        self.log_box.clear()
