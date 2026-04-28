"""Reusable Qt widget builders so pages stay readable.

Each helper either returns a single widget, or a tuple ``(widget, getter)``
where the getter reads the current value. Pages stash the getters in
``self.cfg`` for later persistence.
"""
from __future__ import annotations

from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

import style


SIMPLE_HOTKEYS = [f"F{i}" for i in range(1, 13)]
PAGE_KEYS = ["F1", "F2", "F3"]                # = P1 / P2 / P3
SKILL_KEYS = [f"F{i}" for i in range(5, 13)]  # F5..F12


# ──────────────────────────── Cards ────────────────────────────

def make_card(title: str, *, expand: bool = False) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    """Create a labelled rounded card. Returns (card_frame, content_layout).

    Caller adds widgets to ``content_layout``. ``expand=True`` lets the
    caller size policy = expanding (used by 黑名單's tall textareas).
    """
    card = QtWidgets.QFrame()
    card.setObjectName("card")
    if expand:
        card.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

    outer = QtWidgets.QVBoxLayout(card)
    outer.setContentsMargins(16, 10, 16, 14)
    outer.setSpacing(4)

    title_lbl = QtWidgets.QLabel(title)
    title_lbl.setObjectName("cardTitle")
    outer.addWidget(title_lbl)

    content = QtWidgets.QVBoxLayout()
    content.setContentsMargins(0, 6, 0, 0)
    content.setSpacing(6)
    outer.addLayout(content, stretch=1 if expand else 0)

    return card, content


def sub_panel() -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    """Create a darker sub-panel (used inside cards for inner 2-col)."""
    panel = QtWidgets.QFrame()
    panel.setObjectName("subpanel")
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)
    return panel, layout


# ──────────────────────────── Inputs ────────────────────────────

def num_entry(value: int | str = "", *, width: int = 56) -> QtWidgets.QLineEdit:
    e = QtWidgets.QLineEdit(str(value))
    e.setFixedWidth(width)
    e.setAlignment(QtCore.Qt.AlignCenter)
    return e


def text_entry(value: str = "", *, width: int = 200) -> QtWidgets.QLineEdit:
    e = QtWidgets.QLineEdit(value)
    if width:
        e.setFixedWidth(width)
    return e


def textarea(value: str = "", *, height: int = 72) -> QtWidgets.QPlainTextEdit:
    box = QtWidgets.QPlainTextEdit(value)
    box.setMinimumHeight(height)
    return box


def checkbox(text: str, *, checked: bool = False) -> QtWidgets.QCheckBox:
    cb = QtWidgets.QCheckBox(text)
    cb.setChecked(checked)
    return cb


def radio(text: str, *, checked: bool = False, value: str | None = None) -> QtWidgets.QRadioButton:
    """A radio button. Pass ``value`` to attach a logical key for serialization
    (so QButtonGroup readers can recover 'small'/'medium'/'large' rather than
    the displayed 小/中/大).
    """
    rb = QtWidgets.QRadioButton(text)
    rb.setChecked(checked)
    if value is not None:
        rb.setProperty("value", value)
    return rb


def label(text: str, *, secondary: bool = False) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    if secondary:
        lbl.setObjectName("secondary")
    return lbl


def hint(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    lbl.setObjectName("hint")
    return lbl


def option_menu(values: list[str], value: str, *, width: int = 140) -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox()
    combo.addItems(values)
    if value not in values:
        combo.addItem(value)
    combo.setCurrentText(value)
    combo.setFixedWidth(width)
    return combo


# ──────────────────────────── Slider with % label ────────────────────────────

class PercentSlider(QtWidgets.QWidget):
    """Slider 0–100 with current-value label on the right."""

    def __init__(self, value: int = 50, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(value)
        layout.addWidget(self.slider, stretch=1)

        self._lbl = QtWidgets.QLabel(f"{value}%")
        self._lbl.setObjectName("secondary")
        self._lbl.setMinimumWidth(36)
        self._lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        layout.addWidget(self._lbl)

        self.slider.valueChanged.connect(lambda v: self._lbl.setText(f"{v}%"))

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, v) -> None:
        self.slider.setValue(int(v))


# ──────────────────────────── Hotkey selector ────────────────────────────

class HotkeyMenu(QtWidgets.QWidget):
    """Two side-by-side combos: page (F1/F2/F3) + skill (F5..F12).

    Internal canonical value is 'P1-F5' style. ``value()`` returns this.
    """

    def __init__(self, value: str = "P1-F5", *, paged: bool = True,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._paged = paged

        if not paged:
            self._single = QtWidgets.QComboBox()
            self._single.addItems(SIMPLE_HOTKEYS)
            if value not in SIMPLE_HOTKEYS:
                self._single.addItem(value)
            self._single.setCurrentText(value)
            self._single.setFixedWidth(80)
            layout.addWidget(self._single)
            return

        page_init, skill_init = self._parse(value)

        self._page = QtWidgets.QComboBox()
        self._page.addItems(PAGE_KEYS)
        self._page.setCurrentText(page_init)
        self._page.setFixedWidth(58)
        # Qt elides items in the dropdown view when its width matches the
        # combo's. Letting the view auto-size to its longest item fixes that.
        self._page.view().setMinimumWidth(0)
        self._page.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        layout.addWidget(self._page)

        self._skill = QtWidgets.QComboBox()
        self._skill.addItems(SKILL_KEYS)
        self._skill.setCurrentText(skill_init)
        self._skill.setFixedWidth(68)
        self._skill.view().setMinimumWidth(0)
        self._skill.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        layout.addWidget(self._skill)

    @staticmethod
    def _parse(value: str) -> tuple[str, str]:
        if "-" in value:
            p, s = value.split("-", 1)
            if p.startswith("P"):
                p = "F" + p[1:]
            if p not in PAGE_KEYS:
                p = "F1"
            if s not in SKILL_KEYS:
                s = "F5"
            return p, s
        return "F1", value if value in SKILL_KEYS else "F5"

    def value(self) -> str:
        if not self._paged:
            return self._single.currentText()
        p = self._page.currentText()
        s = self._skill.currentText()
        return f"P{p[1:]}-{s}"

    def set_value(self, v: str) -> None:
        if not self._paged:
            self._single.setCurrentText(v)
            return
        page, skill = self._parse(v)
        self._page.setCurrentText(page)
        self._skill.setCurrentText(skill)


# ──────────────────────────── Help button (? + tooltip) ────────────────────────────

def help_button(hints: list[str], *, label_text: str = "提示") -> QtWidgets.QWidget:
    """Round '?' button + adjacent caption. Hover shows ``hints``."""
    container = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    btn = QtWidgets.QPushButton("?")
    btn.setObjectName("help")
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setToolTip("\n".join("• " + h for h in hints))
    layout.addWidget(btn)

    if label_text:
        cap = QtWidgets.QLabel(label_text)
        cap.setObjectName("hint")
        layout.addWidget(cap)

    layout.addStretch(1)
    return container


# ──────────────────────────── Layout helpers ────────────────────────────

def hbox(spacing: int = 8) -> QtWidgets.QHBoxLayout:
    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    return layout


def vbox(spacing: int = 6) -> QtWidgets.QVBoxLayout:
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    return layout


def stretch_widget() -> QtWidgets.QWidget:
    """Spacer widget that expands to fill available space."""
    w = QtWidgets.QWidget()
    w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    return w
