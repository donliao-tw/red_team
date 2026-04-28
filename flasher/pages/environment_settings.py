"""環境設定 — app preferences (font size, theme, future general options)."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import widgets
from ._base import Page


FONT_LEVELS = [("small", "小"), ("medium", "中"), ("large", "大")]
THEME_OPTIONS = [("dark", "深色 Dark"), ("light", "淺色 Light")]


class EnvironmentSettingsPage(Page):
    title = "環境設定"
    subtitle = "外觀、字體、應用程式偏好"

    def build(self) -> None:
        self.body_layout.setSpacing(12)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        content = QtWidgets.QWidget()
        scroll.setWidget(content)
        cols = QtWidgets.QHBoxLayout(content)
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(16)

        col_a = QtWidgets.QVBoxLayout(); col_a.setSpacing(12)
        col_b = QtWidgets.QVBoxLayout(); col_b.setSpacing(12)

        col_a.addWidget(self._build_appearance())
        col_a.addStretch(1)
        col_b.addStretch(1)  # placeholder for future cards

        cols.addLayout(col_a, stretch=1)
        cols.addLayout(col_b, stretch=1)

        self.body_layout.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------------ cards

    def _build_appearance(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("外觀")

        # ── Font size row ──
        layout.addWidget(self._labeled_row(
            "字體大小",
            self._build_font_radios(),
        ))

        # ── Theme row ──
        layout.addWidget(self._labeled_row(
            "主題",
            self._build_theme_radios(),
        ))

        return card

    def _labeled_row(self, label_text: str, control: QtWidgets.QWidget) -> QtWidgets.QWidget:
        """Two-part row: title on left, control on right."""
        wrap = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(wrap)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(16)

        lbl = QtWidgets.QLabel(label_text)
        lbl.setMinimumWidth(80)
        h.addWidget(lbl, alignment=QtCore.Qt.AlignVCenter)

        h.addWidget(control, alignment=QtCore.Qt.AlignVCenter)
        h.addStretch(1)
        return wrap

    def _build_font_radios(self) -> QtWidgets.QWidget:
        wrap = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)

        group = QtWidgets.QButtonGroup(self)
        for value, text in FONT_LEVELS:
            rb = widgets.radio(text, checked=(value == "medium"), value=value)
            rb.toggled.connect(lambda checked, v=value: checked and self.app.set_font_size(v))
            group.addButton(rb)
            h.addWidget(rb)
        self.cfg["font_level"] = group
        return wrap

    def _build_theme_radios(self) -> QtWidgets.QWidget:
        wrap = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)

        group = QtWidgets.QButtonGroup(self)
        for value, text in THEME_OPTIONS:
            rb = widgets.radio(text, checked=(value == "dark"), value=value)
            rb.toggled.connect(lambda checked, v=value: checked and self.app.set_theme(v))
            group.addButton(rb)
            h.addWidget(rb)
        self.cfg["theme"] = group
        return wrap
