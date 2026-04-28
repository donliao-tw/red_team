"""主畫面 — landing dashboard with quick-nav cards to each settings page."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ._base import Page


# (page_key, emoji, title, subtitle)
DESTINATIONS: list[tuple[str, str, str, str]] = [
    ("bot",      "\U0001F916", "機器人設定", "戰鬥模式、瞬移觸發、黑名單"),
    ("skill",    "\U00002728", "技能設定",   "保護功能、自動 Buff、自定計時、主動技能"),
    ("hardware", "\U0001F50C", "硬體設定",   "Arduino 偵測、韌體燒錄、VID·PID 偽裝"),
    ("env",      "\U00002699", "環境設定",   "外觀、字體、應用程式偏好"),
]


class _DashCard(QtWidgets.QFrame):
    """Clickable card. Calls ``on_click`` on left-mouse release within bounds."""

    def __init__(self, on_click) -> None:
        super().__init__()
        self.setObjectName("dashCard")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self._on_click = on_click

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self._on_click()
        super().mouseReleaseEvent(event)


class MainPage(Page):
    title = "主畫面"
    subtitle = "選擇要進入的設定頁面"

    def build(self) -> None:
        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        for i, (key, icon, name, desc) in enumerate(DESTINATIONS):
            grid.addWidget(self._make_card(key, icon, name, desc), i // 2, i % 2)

        self.body_layout.addLayout(grid)
        self.body_layout.addStretch(1)

    def _make_card(self, key: str, icon: str, name: str, desc: str) -> QtWidgets.QFrame:
        card = _DashCard(lambda: self.app.switch_page(key))
        card.setMinimumHeight(140)

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(6)

        icon_lbl = QtWidgets.QLabel(icon)
        icon_lbl.setObjectName("dashCardIcon")
        layout.addWidget(icon_lbl)

        layout.addStretch(1)

        name_lbl = QtWidgets.QLabel(name)
        name_lbl.setObjectName("dashCardName")
        layout.addWidget(name_lbl)

        desc_lbl = QtWidgets.QLabel(desc)
        desc_lbl.setObjectName("dashCardDesc")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        return card
