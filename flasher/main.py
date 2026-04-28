"""Red Team Control Center — PySide6 entry point."""
from __future__ import annotations

import sys

from PySide6 import QtCore, QtGui, QtWidgets

import style


APP_TITLE = "Red Team Control Center"
APP_SIZE = (1400, 820)
MIN_SIZE = (1300, 680)
SIDEBAR_WIDTH = 260


NAV_ITEMS = [
    ("main",     "\U0001F3E0  主畫面"),
    ("bot",      "\U0001F916  機器人設定"),
    ("skill",    "\U00002728  技能設定"),
    ("hardware", "\U0001F50C  硬體設定"),
    ("env",      "\U00002699  環境設定"),
]


FONT_DELTAS = {"small": 0, "medium": 2, "large": 4}


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(*APP_SIZE)
        self.setMinimumSize(*MIN_SIZE)
        self._center()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        layout.addWidget(self.sidebar)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        self.pages: dict[str, QtWidgets.QWidget] = {}
        self._page_factories = {
            "main":     self._make_main_page,
            "bot":      self._make_bot_page,
            "skill":    self._make_skill_page,
            "hardware": self._make_hardware_page,
            "env":      self._make_env_page,
        }

        self.switch_page("main")

    # ------------------------------------------------------------------ sidebar

    def _build_sidebar(self) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(SIDEBAR_WIDTH)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(20, 24, 20, 16)
        layout.setSpacing(0)

        logo = QtWidgets.QLabel("RED TEAM")
        logo.setObjectName("logo")
        layout.addWidget(logo)

        sub = QtWidgets.QLabel("Control Center")
        sub.setObjectName("logoSub")
        layout.addWidget(sub)

        layout.addSpacing(28)

        self.nav_buttons: dict[str, QtWidgets.QPushButton] = {}
        for key, text in NAV_ITEMS:
            btn = QtWidgets.QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setProperty("active", False)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.switch_page(k))
            layout.addWidget(btn)
            layout.addSpacing(4)
            self.nav_buttons[key] = btn

        layout.addStretch(1)

        self.status_label = QtWidgets.QLabel("\U000026AB  未連接")
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)

        return frame

    def _center(self) -> None:
        screen = self.screen().availableGeometry()
        x = screen.x() + (screen.width() - APP_SIZE[0]) // 2
        y = screen.y() + (screen.height() - APP_SIZE[1]) // 2
        self.move(x, y)

    # ------------------------------------------------------------------ pages

    def _make_main_page(self):
        from pages.main_page import MainPage
        return MainPage(self)

    def _make_bot_page(self):
        from pages.bot_settings import BotSettingsPage
        return BotSettingsPage(self)

    def _make_skill_page(self):
        from pages.skill_settings import SkillSettingsPage
        return SkillSettingsPage(self)

    def _make_hardware_page(self):
        from pages.hardware_settings import HardwareSettingsPage
        return HardwareSettingsPage(self)

    def _make_env_page(self):
        from pages.environment_settings import EnvironmentSettingsPage
        return EnvironmentSettingsPage(self)

    def switch_page(self, key: str) -> None:
        if key not in self.pages:
            page = self._page_factories[key]()
            self.pages[key] = page
            self.stack.addWidget(page)

        self.stack.setCurrentWidget(self.pages[key])

        for k, btn in self.nav_buttons.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_status(self, text: str, *, ok: bool | None = None) -> None:
        dot = "\U0001F7E2" if ok else ("\U0001F534" if ok is False else "\U000026AB")
        self.status_label.setText(f"{dot}  {text}")

    # ------------------------------------------------------------------ theme / font

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
    style.load_bundled_fonts()  # register Inter + any other bundled fonts
    style.ensure_icons()
    app.setStyleSheet(style.make_qss())
    app.setFont(QtGui.QFont(style.FAMILY_UI, 10 + style.FONT_DELTA))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
