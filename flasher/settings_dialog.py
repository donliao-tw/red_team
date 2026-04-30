"""Settings dialog — sidebar + page stack, opened from the main window.

The five settings pages (bot / skill / hardware / env) live here, lazy-
constructed on first navigation. Pages call back into ``self.app`` for
theme / font / status changes; this dialog forwards those to its parent
MainWindow so the look stays consistent across both windows.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets


NAV_ITEMS = [
    ("bot",      "\U0001F916  機器人設定"),
    ("skill",    "\U00002728  技能設定"),
    ("hardware", "\U0001F50C  硬體設定"),
    ("env",      "\U00002699  環境設定"),
]


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._main = parent
        self.setWindowTitle("設定 — Red Team")
        self.resize(1300, 760)
        self.setMinimumSize(1100, 640)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        layout.addWidget(self.sidebar)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        self.pages: dict[str, QtWidgets.QWidget] = {}
        self._factories = {
            "bot":      self._make_bot,
            "skill":    self._make_skill,
            "hardware": self._make_hardware,
            "env":      self._make_env,
        }

        self.show_on_page("bot")

    # ------------------------------------------------------------------ sidebar

    def _build_sidebar(self) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(240)

        vbox = QtWidgets.QVBoxLayout(frame)
        vbox.setContentsMargins(20, 24, 20, 16)
        vbox.setSpacing(0)

        logo = QtWidgets.QLabel("RED TEAM")
        logo.setObjectName("logo")
        vbox.addWidget(logo)
        sub = QtWidgets.QLabel("Settings")
        sub.setObjectName("logoSub")
        vbox.addWidget(sub)

        vbox.addSpacing(28)

        self.nav_buttons: dict[str, QtWidgets.QPushButton] = {}
        for key, text in NAV_ITEMS:
            btn = QtWidgets.QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setProperty("active", False)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.show_on_page(k))
            vbox.addWidget(btn)
            vbox.addSpacing(4)
            self.nav_buttons[key] = btn

        vbox.addStretch(1)

        return frame

    # ------------------------------------------------------------------ pages

    def _make_bot(self):
        from pages.bot_settings import BotSettingsPage
        return BotSettingsPage(self)

    def _make_skill(self):
        from pages.skill_settings import SkillSettingsPage
        return SkillSettingsPage(self)

    def _make_hardware(self):
        from pages.hardware_settings import HardwareSettingsPage
        return HardwareSettingsPage(self)

    def _make_env(self):
        from pages.environment_settings import EnvironmentSettingsPage
        return EnvironmentSettingsPage(self)

    def show_on_page(self, key: str) -> None:
        if key not in self.pages:
            page = self._factories[key]()
            self.pages[key] = page
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(self.pages[key])
        for k, btn in self.nav_buttons.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ------------------------------------------------------------------ delegated methods (called by pages via self.app)

    def switch_page(self, key: str) -> None:
        self.show_on_page(key)

    def set_font_size(self, level: str) -> None:
        if self._main is not None:
            self._main.set_font_size(level)

    def set_theme(self, theme: str) -> None:
        if self._main is not None:
            self._main.set_theme(theme)

    def set_status(self, text: str, *, ok: bool | None = None) -> None:
        if self._main is not None:
            self._main.set_status(text, ok=ok)
