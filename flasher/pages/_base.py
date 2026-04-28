"""Base class for sidebar pages."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import style


class Page(QtWidgets.QWidget):
    """Subclass and override ``build()`` to populate ``self.body_layout``.

    Pages keep config state in ``self.cfg: dict`` so a future load/save
    layer can serialise it.
    """

    title: str = ""
    subtitle: str = ""

    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.cfg: dict = {}

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(28, 18, 28, 18)
        outer.setSpacing(12)

        # Header — title + middot + subtitle inline
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)

        title_lbl = QtWidgets.QLabel(self.title)
        title_lbl.setObjectName("pageTitle")
        header.addWidget(title_lbl, alignment=QtCore.Qt.AlignBottom)

        if self.subtitle:
            sub_lbl = QtWidgets.QLabel("·  " + self.subtitle)
            sub_lbl.setObjectName("pageSubtitle")
            header.addWidget(sub_lbl, alignment=QtCore.Qt.AlignBottom)

        header.addStretch(1)
        outer.addLayout(header)

        # Body container — subclasses add to body_layout
        self.body = QtWidgets.QWidget()
        self.body_layout = QtWidgets.QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 6, 0, 0)
        self.body_layout.setSpacing(0)
        outer.addWidget(self.body, stretch=1)

        self.build()

    def build(self) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------ serialize / apply

    def serialize(self) -> dict:
        """Return a flat ``{key: value}`` snapshot of all fields in self.cfg.

        Each widget type is read with the appropriate accessor — callers
        get plain Python values (bool / str / int) and don't need to know
        about Qt widget types.
        """
        return {key: _read_widget(w) for key, w in self.cfg.items()}

    def apply(self, config: dict) -> None:
        """Write values from ``config`` back into the matching widgets.

        Keys not present in self.cfg are silently ignored (so loading a
        partial / older config file is safe).
        """
        for key, value in config.items():
            w = self.cfg.get(key)
            if w is None:
                continue
            _write_widget(w, value)


def _read_widget(w):
    """Read the current value from a widget, dispatching by type."""
    if isinstance(w, QtWidgets.QCheckBox):
        return w.isChecked()
    if isinstance(w, QtWidgets.QLineEdit):
        return w.text()
    if isinstance(w, QtWidgets.QComboBox):
        return w.currentText()
    if isinstance(w, (QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)):
        return w.toPlainText()
    if isinstance(w, QtWidgets.QButtonGroup):
        btn = w.checkedButton()
        if btn is None:
            return None
        v = btn.property("value")
        return v if v is not None else btn.text()
    if isinstance(w, QtWidgets.QRadioButton):
        return w.isChecked()
    if isinstance(w, QtWidgets.QSlider):
        return w.value()
    # Custom widgets that follow the value()/set_value() protocol
    # (HotkeyMenu, PercentSlider).
    if hasattr(w, "value") and callable(getattr(w, "value")):
        return w.value()
    return None


def _write_widget(w, value) -> None:
    """Set a widget's value, dispatching by type."""
    if isinstance(w, QtWidgets.QCheckBox):
        w.setChecked(bool(value))
    elif isinstance(w, QtWidgets.QLineEdit):
        w.setText(str(value))
    elif isinstance(w, QtWidgets.QComboBox):
        w.setCurrentText(str(value))
    elif isinstance(w, (QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)):
        w.setPlainText(str(value))
    elif isinstance(w, QtWidgets.QButtonGroup):
        for btn in w.buttons():
            key = btn.property("value")
            if key == value or btn.text() == value:
                btn.setChecked(True)
                return
    elif isinstance(w, QtWidgets.QRadioButton):
        w.setChecked(bool(value))
    elif isinstance(w, QtWidgets.QSlider):
        w.setValue(int(value))
    elif hasattr(w, "set_value") and callable(getattr(w, "set_value")):
        w.set_value(value)
