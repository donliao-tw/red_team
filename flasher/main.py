"""Red Team Control Center — compact main panel.

The main window is intentionally narrow and focused on runtime control:
login, config file, two progress bars, three function toggles (each with
a gear that opens settings on the relevant tab), a stats card, and the
console log. All detailed configuration lives in the settings dialog
(``settings_dialog.py``) which is opened from any of the gear icons or
the "OCR設定" footer button.
"""
from __future__ import annotations

import sys

from PySide6 import QtCore, QtGui, QtWidgets

import style
from settings_dialog import SettingsDialog


APP_TITLE = "Red Team"
APP_VERSION = "0.1.0"
APP_SIZE = (440, 800)
MIN_SIZE = (400, 640)


FONT_DELTAS = {"small": 0, "medium": 2, "large": 4}


# Hard-coded sample log lines — purely cosmetic; replaced by real events
# once the bot runtime is wired up.
SAMPLE_LOG = [
    "[02:51:12] 系統：正在驗證開卡資訊…",
    "[02:51:12] 系統：驗證成功！到期日：2026-05-11 19:31:45",
    "[02:51:12] 系統：資料版本已是最新 (20260410001)",
    "[02:51:12] 成功連結：Login [9AHHSYB9KZ2R@plaync.com]",
    "[02:51:12] 系統：地圖繪製模組啟動",
    "[02:51:28] 系統：已載入設定檔：騎士.ini",
    "[02:51:35] 保護執行中。",
    "[02:51:35] 保護暫停中…等待回到前台",
    "[02:51:52] 系統：腳本 [騎士-古洞2樓] 啟動。",
    "[02:51:52] 系統：[腳本定位] 已在村莊，重置腳本。",
]


class TitleBar(QtWidgets.QFrame):
    """Custom dark title bar for the frameless main window.

    Drag to move, double-click to maximize, three Window controls on the right.
    """

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self._win = parent
        self.setObjectName("titleBar")
        self.setFixedHeight(34)

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(14, 0, 0, 0)
        h.setSpacing(8)

        title = QtWidgets.QLabel("RED TEAM")
        title.setObjectName("titleBarLabel")
        h.addWidget(title)
        h.addStretch(1)

        for text, role, slot in (
            ("–", "min",   self._win.showMinimized),
            ("□", "max",   self._toggle_max),
            ("✕", "close", self._win.close),
        ):
            btn = QtWidgets.QPushButton(text)
            btn.setObjectName("titleBtn")
            btn.setProperty("role", role)
            btn.setFixedSize(40, 34)
            btn.setFocusPolicy(QtCore.Qt.NoFocus)
            btn.clicked.connect(slot)
            h.addWidget(btn)

        self._drag_pos: QtCore.QPoint | None = None

    def _toggle_max(self) -> None:
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() == QtCore.Qt.LeftButton:
            self._win.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._toggle_max()
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_pos = None


class FunctionButton(QtWidgets.QPushButton):
    """Icon-only toggle. Right-click to pick a custom active colour."""

    DEFAULT_CHECKED_COLOR = "#d97706"

    colorChanged = QtCore.Signal(str)

    def __init__(self, icon: str, tooltip: str) -> None:
        super().__init__(icon)
        self.setObjectName("funcMain")
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip(tooltip + "\n（右鍵更改啟動色）")
        self.setMinimumHeight(40)
        self._checked_color = self.DEFAULT_CHECKED_COLOR

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        initial = QtGui.QColor(self._checked_color)
        color = QtWidgets.QColorDialog.getColor(initial, self, "選擇啟動色")
        if color.isValid():
            self.set_checked_color(color.name())
            event.accept()

    def set_checked_color(self, color: str) -> None:
        if color == self._checked_color:
            return
        self._checked_color = color
        self._apply_checked_color()
        self.colorChanged.emit(color)

    def _apply_checked_color(self) -> None:
        base = QtGui.QColor(self._checked_color)
        top = base.lighter(135).name()
        mid = base.name()
        bottom = base.darker(140).name()
        edge = base.darker(170).name()
        sheen = base.lighter(155).name()

        self.setStyleSheet(f"""
            QPushButton#funcMain:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {top}, stop:0.45 {mid}, stop:1 {bottom});
                border: 1px solid {edge};
                border-top: 1px solid {sheen};
                color: white;
            }}
            QPushButton#funcMain:checked:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {sheen}, stop:0.45 {top}, stop:1 {mid});
            }}
        """)


class ProgressRow(QtWidgets.QWidget):
    """Three-column label row over a thin progress bar."""

    def __init__(self) -> None:
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self.left = QtWidgets.QLabel("")
        self.left.setObjectName("progressText")
        self.middle = QtWidgets.QLabel("")
        self.middle.setObjectName("progressText")
        self.middle.setAlignment(QtCore.Qt.AlignCenter)
        self.right = QtWidgets.QLabel("")
        self.right.setObjectName("progressText")
        self.right.setAlignment(QtCore.Qt.AlignRight)

        top.addWidget(self.left)
        top.addWidget(self.middle, stretch=1)
        top.addWidget(self.right)
        v.addLayout(top)

        self.bar = QtWidgets.QProgressBar()
        self.bar.setObjectName("progressBar")
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.bar.setRange(0, 100)
        v.addWidget(self.bar)

    def set_values(self, *, left: str, middle: str, right: str, percent: int) -> None:
        self.left.setText(left)
        self.middle.setText(middle)
        self.right.setText(right)
        self.bar.setValue(percent)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint, True)
        self.resize(*APP_SIZE)
        self.setMinimumSize(*MIN_SIZE)
        self._center()

        self._settings: SettingsDialog | None = None  # lazy-created

        central = QtWidgets.QFrame()
        central.setObjectName("appShell")
        self.setCentralWidget(central)

        shell = QtWidgets.QVBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.title_bar = TitleBar(self)
        shell.addWidget(self.title_bar)

        body = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(body)
        v.setContentsMargins(12, 12, 12, 10)
        v.setSpacing(10)
        shell.addWidget(body, stretch=1)

        v.addLayout(self._build_login_row())
        v.addLayout(self._build_config_row())
        v.addWidget(self._build_progress_block())
        v.addLayout(self._build_function_grid())
        v.addWidget(self._build_stats_card())
        v.addWidget(self._build_log(), stretch=1)
        v.addLayout(self._build_footer())
        v.addWidget(self._build_banner())

        # Protect is always-on by default — it's auxiliary protection, not a
        # primary mode, so it makes sense to start enabled.
        self.btn_protect.setChecked(True)

        # Bind 機器人(掛機) ↔ 娃娃 active colour: changing one updates the other.
        # 保護 keeps its own colour independently. The set_checked_color guard
        # against same-value no-ops prevents the ping-pong from looping.
        self.btn_afk.colorChanged.connect(self.btn_doll.set_checked_color)
        self.btn_doll.colorChanged.connect(self.btn_afk.set_checked_color)

    # ------------------------------------------------------------------ rows

    def _build_login_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        self.unlock_btn = QtWidgets.QPushButton("\U0001F513")  # 🔓 open padlock
        self.unlock_btn.setObjectName("iconBtn")
        self.unlock_btn.setFixedSize(38, 34)
        self.unlock_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.unlock_btn.setToolTip("解除鎖定")
        self.unlock_btn.setStyleSheet("font-size: 14pt;")
        row.addWidget(self.unlock_btn)

        self.skill_settings_btn = QtWidgets.QPushButton("⚙")
        self.skill_settings_btn.setObjectName("iconBtn")
        self.skill_settings_btn.setFixedSize(38, 34)
        self.skill_settings_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.skill_settings_btn.setToolTip("技能設定")
        self.skill_settings_btn.setStyleSheet("font-size: 14pt;")
        self.skill_settings_btn.clicked.connect(lambda: self._open_settings("skill"))
        row.addWidget(self.skill_settings_btn)

        self.login_combo = QtWidgets.QComboBox()
        self.login_combo.addItems([
            "Login [9AHHSYB9KZ2R@plaync.com]",
        ])
        row.addWidget(self.login_combo, stretch=1)

        self.refresh_btn = QtWidgets.QPushButton("↻")
        self.refresh_btn.setObjectName("iconBtn")
        self.refresh_btn.setFixedSize(38, 34)
        self.refresh_btn.setStyleSheet("font-size: 14pt;")
        self.refresh_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.refresh_btn.setToolTip("重新整理")
        row.addWidget(self.refresh_btn)

        return row

    def _build_config_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        self.ini_combo = QtWidgets.QComboBox()
        self.ini_combo.setEditable(True)
        self.ini_combo.addItems(["騎士.ini", "default.ini"])
        row.addWidget(self.ini_combo, stretch=1)

        for label in ("讀取", "儲存", "新增"):
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("secondary")
            btn.setMinimumWidth(48)
            row.addWidget(btn)

        return row

    def _build_progress_block(self) -> QtWidgets.QWidget:
        wrap = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self.prog_hp = ProgressRow()
        self.prog_hp.bar.setObjectName("hpBar")
        self.prog_hp.set_values(
            left="HP",
            middle="1850 / 2000",
            right="92%",
            percent=92,
        )
        v.addWidget(self.prog_hp)

        self.prog_mp = ProgressRow()
        self.prog_mp.bar.setObjectName("mpBar")
        self.prog_mp.set_values(
            left="MP",
            middle="320 / 500",
            right="64%",
            percent=64,
        )
        v.addWidget(self.prog_mp)

        return wrap

    # All three function toggles map to inner tabs of the 機器人設定 page.
    _BOT_TAB_FOR_TOGGLE = {
        "protect": "protect",
        "afk":     "afk",
        "doll":    "doll",
    }

    # Toggles in this set exclude each other; toggles outside it are
    # independent (e.g. 保護 can stay on regardless of 掛機/娃娃).
    _EXCLUSIVE_GROUP = {"afk", "doll"}

    def _build_function_grid(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)

        self.btn_protect = FunctionButton("\U0001F6E1️", tooltip="保護功能")
        self.btn_afk     = FunctionButton("\U0001F916",  tooltip="掛機功能 (HOME)")
        self.btn_doll    = FunctionButton("\U0001F9D8",  tooltip="娃娃功能 (END)")

        # Protect is auxiliary (always-on protection), so it gets a narrower
        # cell than the two primary mode toggles.
        row.addWidget(self.btn_protect, stretch=2)
        row.addWidget(self.btn_afk,     stretch=3)
        row.addWidget(self.btn_doll,    stretch=3)

        self.gear_btn = QtWidgets.QPushButton("⚙")
        self.gear_btn.setObjectName("funcGear")
        self.gear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.gear_btn.setFixedSize(40, 40)
        self.gear_btn.clicked.connect(self._open_active_settings)
        row.addWidget(self.gear_btn)

        self._toggles = {
            "protect": self.btn_protect,
            "afk":     self.btn_afk,
            "doll":    self.btn_doll,
        }
        # Activation order — most recent at the end. Used so the shared gear
        # opens the tab of whichever toggle the user touched last.
        self._activation_order: list[str] = []

        for key, btn in self._toggles.items():
            btn.toggled.connect(lambda checked, k=key: self._on_func_toggled(k, checked))

        self._refresh_gear_tooltip()
        return row

    def _on_func_toggled(self, key: str, checked: bool) -> None:
        if checked:
            if key in self._activation_order:
                self._activation_order.remove(key)
            self._activation_order.append(key)

            # Only afk ↔ doll are mutually exclusive; protect is independent.
            if key in self._EXCLUSIVE_GROUP:
                for other in self._EXCLUSIVE_GROUP - {key}:
                    btn = self._toggles[other]
                    if btn.isChecked():
                        btn.blockSignals(True)
                        btn.setChecked(False)
                        btn.blockSignals(False)
                        if other in self._activation_order:
                            self._activation_order.remove(other)
        else:
            if key in self._activation_order:
                self._activation_order.remove(key)
        self._refresh_gear_tooltip()

    def _active_toggle(self) -> str | None:
        return self._activation_order[-1] if self._activation_order else None

    def _refresh_gear_tooltip(self) -> None:
        active = self._active_toggle()
        if active is None:
            self.gear_btn.setToolTip("設定")
        else:
            label = self._toggles[active].toolTip()
            self.gear_btn.setToolTip(f"{label} — 設定")

    def _open_active_settings(self) -> None:
        active = self._active_toggle()
        inner_tab = self._BOT_TAB_FOR_TOGGLE.get(active, "afk")
        self._open_settings("bot")
        bot_page = self._settings.pages.get("bot")
        if bot_page is not None and hasattr(bot_page, "show_tab"):
            bot_page.show_tab(inner_tab)

    def _build_stats_card(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        sl = QtWidgets.QGridLayout(card)
        sl.setContentsMargins(14, 12, 14, 12)
        sl.setHorizontalSpacing(10)
        sl.setVerticalSpacing(8)

        self.stat_exp = self._stat_row(
            icon="\U0001F4D6",
            primary="0.0000%",
            rate="0.0000% / H",
            tooltip="經驗值（累積 / 每小時）",
            primary_color="#7fb8e6",   # light blue
            rate_color="#5a87a8",
        )
        self.stat_gold = self._stat_row(
            icon="\U0001F4B0",
            primary="0",
            rate="0 / H",
            tooltip="金錢（累積 / 每小時）",
            primary_color="#e6c14a",   # warm gold
            rate_color="#a88f3a",
        )
        self.stat_time = self._stat_row(
            icon="⏱️",
            primary="00:00:00",
            rate=None,
            tooltip="已運行時間",
            primary_color="#c4a577",   # light brown
            rate_color="#8c7654",
        )

        self.stat_reset = QtWidgets.QPushButton("↻")
        self.stat_reset.setObjectName("resetBtn")
        self.stat_reset.setFixedSize(32, 32)
        self.stat_reset.setCursor(QtCore.Qt.PointingHandCursor)
        self.stat_reset.setToolTip("重置統計\n（升級或死亡後請按此歸零）")

        # Bottom row: ⏱ time stat with the reset tucked into the corner.
        bottom = QtWidgets.QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(0)
        bottom.addWidget(self.stat_time, stretch=1)
        bottom.addWidget(self.stat_reset, alignment=QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)

        sl.addWidget(self.stat_exp,  0, 0)
        sl.addWidget(self.stat_gold, 1, 0)
        sl.addLayout(bottom,         2, 0)
        sl.setColumnStretch(0, 1)

        return card

    def _stat_row(
        self, *,
        icon: str,
        primary: str,
        rate: str | None,
        tooltip: str,
        primary_color: str,
        rate_color: str,
    ) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setToolTip(tooltip)
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)

        icon_lbl = QtWidgets.QLabel(icon)
        icon_lbl.setObjectName("statIcon")
        icon_lbl.setToolTip(tooltip)
        h.addWidget(icon_lbl)

        primary_lbl = QtWidgets.QLabel(primary)
        primary_lbl.setObjectName("statPrimary")
        primary_lbl.setToolTip(tooltip)
        primary_lbl.setStyleSheet(f"color: {primary_color};")
        h.addWidget(primary_lbl)

        h.addStretch(1)

        if rate is not None:
            rate_lbl = QtWidgets.QLabel(rate)
            rate_lbl.setObjectName("statRate")
            rate_lbl.setToolTip(tooltip)
            rate_lbl.setStyleSheet(f"color: {rate_color};")
            h.addWidget(rate_lbl)

        return w

    def _build_log(self) -> QtWidgets.QWidget:
        wrap = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        # Thin header row with the collapse/expand chevron, right-aligned.
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch(1)
        self.log_toggle = QtWidgets.QPushButton("▾")
        self.log_toggle.setObjectName("iconBtn")
        self.log_toggle.setFixedSize(28, 20)
        self.log_toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.log_toggle.setToolTip("收合記錄")
        self.log_toggle.clicked.connect(self._toggle_log)
        header.addWidget(self.log_toggle)
        v.addLayout(header)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setObjectName("consoleLog")
        self.log.setReadOnly(True)
        self.log.setFrameShape(QtWidgets.QFrame.NoFrame)
        for line in SAMPLE_LOG:
            self.log.appendPlainText(line)
        v.addWidget(self.log, stretch=1)

        self._log_collapsed = False
        return wrap

    def _toggle_log(self) -> None:
        self._log_collapsed = not self._log_collapsed
        if self._log_collapsed:
            # ~5 lines of 9pt monospace + padding
            self.log.setMaximumHeight(110)
            self.log_toggle.setText("▴")
            self.log_toggle.setToolTip("展開記錄")
            self.resize(self.width(), 580)
        else:
            self.log.setMaximumHeight(16777215)
            self.log_toggle.setText("▾")
            self.log_toggle.setToolTip("收合記錄")
            self.resize(self.width(), APP_SIZE[1])

    def _build_footer(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        self.pin_chk = QtWidgets.QCheckBox("置頂")
        self.pin_chk.toggled.connect(self._toggle_pin)
        row.addWidget(self.pin_chk)

        self.auth_btn = QtWidgets.QPushButton("\U0001FAAA")  # 🪪 ID card
        self.auth_btn.setObjectName("footerIcon")
        self.auth_btn.setFixedSize(48, 38)
        self.auth_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.auth_btn.setToolTip("驗證資訊")
        self.auth_btn.clicked.connect(self._show_auth_info)
        row.addWidget(self.auth_btn)

        self.ocr_btn = QtWidgets.QPushButton("\U0001F575️")  # 🕵️ detective with magnifying glass
        self.ocr_btn.setObjectName("footerIcon")
        self.ocr_btn.setFixedSize(48, 38)
        self.ocr_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.ocr_btn.setToolTip("OCR 設定")
        self.ocr_btn.clicked.connect(lambda: self._open_settings("env"))
        row.addWidget(self.ocr_btn)

        row.addStretch(1)

        ver = QtWidgets.QLabel(f"Ver : {APP_VERSION}")
        ver.setObjectName("verLabel")
        row.addWidget(ver)

        return row

    def _build_banner(self) -> QtWidgets.QLabel:
        self.banner = QtWidgets.QLabel("腳本已到底，重頭開始循環…")
        self.banner.setObjectName("banner")
        self.banner.setAlignment(QtCore.Qt.AlignCenter)
        return self.banner

    # ------------------------------------------------------------------ window helpers

    def _center(self) -> None:
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - APP_SIZE[0]) // 2
        y = screen.y() + (screen.height() - APP_SIZE[1]) // 2
        self.move(x, y)

    def _toggle_pin(self, checked: bool) -> None:
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, checked)
        self.show()

    def _show_auth_info(self) -> None:
        QtWidgets.QMessageBox.information(
            self, "驗證資訊",
            "Login : 9AHHSYB9KZ2R@plaync.com\n到期日 : 2026-05-11 19:31:45",
        )

    # ------------------------------------------------------------------ settings dialog

    def _open_settings(self, key: str) -> None:
        if self._settings is None:
            self._settings = SettingsDialog(self)
        self._settings.show_on_page(key)
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    # ------------------------------------------------------------------ delegated by pages (via self.app on settings pages)

    def set_status(self, text: str, *, ok: bool | None = None) -> None:
        # No persistent status indicator on the compact main UI — surface
        # status as a log line so the user still sees it.
        prefix = "🟢" if ok else ("🔴" if ok is False else "⚫")
        self.log.appendPlainText(f"[狀態] {prefix} {text}")

    def set_font_size(self, level: str) -> None:
        delta = FONT_DELTAS.get(level, 0)
        style.set_font_delta(delta)
        self._reapply_theme()

    def set_theme(self, theme: str) -> None:
        style.set_theme(theme)
        self._reapply_theme()

    def _reapply_theme(self) -> None:
        app = QtWidgets.QApplication.instance()
        app.setStyleSheet(style.make_qss())
        app.setFont(QtGui.QFont(style.FAMILY_UI, 10 + style.FONT_DELTA))


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    style.load_bundled_fonts()
    style.ensure_icons()
    app.setStyleSheet(style.make_qss())
    app.setFont(QtGui.QFont(style.FAMILY_UI, 10 + style.FONT_DELTA))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
