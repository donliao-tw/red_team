"""Bot flow editor — ordered list of automation steps.

Steps are displayed as colour-coded cards inside a dark outer panel.
Each card has a coloured left accent bar, a number badge, a type combo,
inline params, and ▲▼/× controls.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import style

# (key, display_label, implemented, accent_colour)
STEP_DEFS = [
    ("teleport", "傳送",     True,  "#4a80c0"),
    ("shop",     "購物",     True,  "#4a9a62"),
    ("wait",     "等待",     True,  "#c8972a"),
    ("patrol",   "巡邏攻擊", False, "#666666"),
    ("loop",     "重複從頭", True,  "#8855bb"),
]

_KEYS    = [d[0] for d in STEP_DEFS]
_LABELS  = [d[1] for d in STEP_DEFS]
_DONE    = {d[0]: d[2] for d in STEP_DEFS}
_COLORS  = {d[0]: d[3] for d in STEP_DEFS}


# ──────────────────────────── params helpers ────────────────────────────

def _make_params(step_type: str) -> QtWidgets.QWidget:
    w = QtWidgets.QWidget()
    h = QtWidgets.QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)

    if step_type == "teleport":
        lbl = QtWidgets.QLabel("目的地:")
        lbl.setObjectName("flowLabel")
        h.addWidget(lbl)
        ed = QtWidgets.QLineEdit()
        ed.setPlaceholderText("例: 奇岩村 雜貨商人")
        ed.setObjectName("flowParam_destination")
        h.addWidget(ed, stretch=1)

    elif step_type == "shop":
        lbl = QtWidgets.QLabel("使用購物設定清單")
        lbl.setObjectName("flowHint")
        h.addWidget(lbl)
        h.addStretch(1)

    elif step_type in ("wait", "patrol"):
        sp = QtWidgets.QSpinBox()
        sp.setRange(1, 600)
        sp.setValue(60 if step_type == "patrol" else 5)
        sp.setObjectName("flowParam_minutes")
        sp.setFixedWidth(60)
        h.addWidget(sp)
        lbl = QtWidgets.QLabel("分鐘")
        lbl.setObjectName("flowLabel")
        h.addWidget(lbl)
        if not _DONE[step_type]:
            tag = QtWidgets.QLabel("（未實作）")
            tag.setObjectName("flowHint")
            h.addWidget(tag)
        h.addStretch(1)

    elif step_type == "loop":
        sp = QtWidgets.QSpinBox()
        sp.setRange(0, 9999)
        sp.setValue(0)
        sp.setObjectName("flowParam_times")
        sp.setFixedWidth(60)
        h.addWidget(sp)
        lbl = QtWidgets.QLabel("次（0＝無限）")
        lbl.setObjectName("flowLabel")
        h.addWidget(lbl)
        h.addStretch(1)

    else:
        h.addStretch(1)

    return w


def _read_params(pw: QtWidgets.QWidget, step_type: str) -> dict:
    data: dict = {"type": step_type}
    if step_type == "teleport":
        ed = pw.findChild(QtWidgets.QLineEdit, "flowParam_destination")
        data["destination"] = ed.text() if ed else ""
    elif step_type in ("wait", "patrol"):
        sp = pw.findChild(QtWidgets.QSpinBox, "flowParam_minutes")
        data["minutes"] = sp.value() if sp else 5
    elif step_type == "loop":
        sp = pw.findChild(QtWidgets.QSpinBox, "flowParam_times")
        data["times"] = sp.value() if sp else 0
    return data


def _apply_params(pw: QtWidgets.QWidget, step_type: str, data: dict) -> None:
    if step_type == "teleport":
        ed = pw.findChild(QtWidgets.QLineEdit, "flowParam_destination")
        if ed:
            ed.setText(str(data.get("destination", "")))
    elif step_type in ("wait", "patrol"):
        sp = pw.findChild(QtWidgets.QSpinBox, "flowParam_minutes")
        if sp:
            sp.setValue(int(data.get("minutes", 5)))
    elif step_type == "loop":
        sp = pw.findChild(QtWidgets.QSpinBox, "flowParam_times")
        if sp:
            sp.setValue(int(data.get("times", 0)))


# ──────────────────────────── StepRow ────────────────────────────

class StepRow(QtWidgets.QWidget):
    """One step card: [accent bar] [num] [type] [params] [▲▼] [×]"""

    sig_move_up   = QtCore.Signal()
    sig_move_down = QtCore.Signal()
    sig_remove    = QtCore.Signal()
    sig_type_changed = QtCore.Signal()

    def __init__(self, step_type: str = "teleport", index: int = 1,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(0)

        # Coloured left accent strip
        self._accent = QtWidgets.QFrame()
        self._accent.setFixedWidth(4)
        self._accent.setFixedHeight(36)
        h.addWidget(self._accent)
        h.addSpacing(8)

        # Number badge
        self._num_lbl = QtWidgets.QLabel(str(index))
        self._num_lbl.setObjectName("stepNum")
        self._num_lbl.setFixedSize(20, 20)
        self._num_lbl.setAlignment(QtCore.Qt.AlignCenter)
        h.addWidget(self._num_lbl)
        h.addSpacing(6)

        # Type combo
        self._combo = QtWidgets.QComboBox()
        self._combo.setObjectName("flowCombo")
        self._combo.setFixedWidth(88)
        for key, label, done, _ in STEP_DEFS:
            self._combo.addItem(label, userData=key)
            if not done:
                model = self._combo.model()
                item = model.item(self._combo.count() - 1)
                if item:
                    item.setEnabled(False)
        init_idx = _KEYS.index(step_type) if step_type in _KEYS else 0
        self._combo.setCurrentIndex(init_idx)
        self._combo.currentIndexChanged.connect(self._on_type_changed)
        h.addWidget(self._combo)
        h.addSpacing(8)

        # Params stack
        self._stack = QtWidgets.QStackedWidget()
        self._stack.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        for key, _, _, _ in STEP_DEFS:
            self._stack.addWidget(_make_params(key))
        self._stack.setCurrentIndex(init_idx)
        h.addWidget(self._stack, stretch=1)
        h.addSpacing(4)

        # ▲▼ stacked
        btn_up = QtWidgets.QPushButton("▲")
        btn_up.setObjectName("flowArrow")
        btn_up.setFixedSize(20, 16)
        btn_up.setCursor(QtCore.Qt.PointingHandCursor)
        btn_up.clicked.connect(self.sig_move_up)

        btn_dn = QtWidgets.QPushButton("▼")
        btn_dn.setObjectName("flowArrow")
        btn_dn.setFixedSize(20, 16)
        btn_dn.setCursor(QtCore.Qt.PointingHandCursor)
        btn_dn.clicked.connect(self.sig_move_down)

        arrows = QtWidgets.QWidget()
        av = QtWidgets.QVBoxLayout(arrows)
        av.setContentsMargins(0, 0, 0, 0)
        av.setSpacing(1)
        av.addWidget(btn_up)
        av.addWidget(btn_dn)
        h.addWidget(arrows)
        h.addSpacing(4)

        # × delete
        btn_x = QtWidgets.QPushButton("×")
        btn_x.setObjectName("shopDel")
        btn_x.setFixedSize(22, 22)
        btn_x.setCursor(QtCore.Qt.PointingHandCursor)
        btn_x.clicked.connect(self.sig_remove)
        h.addWidget(btn_x)
        h.addSpacing(4)

        self._set_type(step_type)

    def _set_type(self, step_type: str) -> None:
        color = _COLORS.get(step_type, "#555")
        self._accent.setStyleSheet(
            f"background: {color}; border-radius: 2px;")
        self._num_lbl.setStyleSheet(
            f"background: {color}22; color: {color}; border-radius: 10px; "
            f"font-size: {8 + style.FONT_DELTA}pt; font-weight: 700;")

    def _on_type_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        key = _KEYS[idx] if 0 <= idx < len(_KEYS) else "teleport"
        self._set_type(key)
        self.sig_type_changed.emit()

    def set_number(self, n: int) -> None:
        self._num_lbl.setText(str(n))

    def step_type(self) -> str:
        idx = self._combo.currentIndex()
        return _KEYS[idx] if 0 <= idx < len(_KEYS) else "teleport"

    def to_dict(self) -> dict:
        return _read_params(self._stack.currentWidget(), self.step_type())

    def from_dict(self, data: dict) -> None:
        t = data.get("type", "teleport")
        if t in _KEYS:
            idx = _KEYS.index(t)
            self._combo.setCurrentIndex(idx)
            _apply_params(self._stack.widget(idx), t, data)


# ──────────────────────────── FlowEditor ────────────────────────────

class FlowEditor(QtWidgets.QWidget):
    """Dark outer card containing the scrollable step list."""

    changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # Outer card — dark background, rounded
        self._card = QtWidgets.QFrame()
        self._card.setObjectName("flowCard")
        card_v = QtWidgets.QVBoxLayout(self._card)
        card_v.setContentsMargins(8, 8, 8, 8)
        card_v.setSpacing(0)

        # Scroll area inside the card
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("flowScroll")

        self._container = QtWidgets.QWidget()
        self._container.setObjectName("flowContainer")
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(3)
        self._vbox.addStretch(1)
        scroll.setWidget(self._container)
        card_v.addWidget(scroll)

        outer.addWidget(self._card, stretch=1)

        # ＋ 新增步驟 — below the card
        add_row = QtWidgets.QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_btn = QtWidgets.QPushButton("＋ 新增步驟")
        add_btn.setObjectName("shopAdd")
        add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self.add_step("teleport"))
        add_row.addWidget(add_btn)
        add_row.addStretch(1)
        outer.addLayout(add_row)

        self._rows: list[StepRow] = []

    # ── public API ──────────────────────────────────────────────────

    def add_step(self, step_type: str = "teleport") -> StepRow:
        row = StepRow(step_type, index=len(self._rows) + 1)
        pos = len(self._rows)
        self._rows.append(row)
        self._vbox.insertWidget(pos, row)
        row.sig_move_up.connect(lambda r=row: self._move(r, -1))
        row.sig_move_down.connect(lambda r=row: self._move(r, +1))
        row.sig_remove.connect(lambda r=row: self._remove(r))
        self.changed.emit()
        return row

    def steps(self) -> list[dict]:
        return [r.to_dict() for r in self._rows]

    def set_steps(self, steps: list[dict]) -> None:
        for r in list(self._rows):
            self._vbox.removeWidget(r)
            r.deleteLater()
        self._rows.clear()
        for data in steps:
            r = self.add_step(data.get("type", "teleport"))
            r.from_dict(data)

    # ── internals ───────────────────────────────────────────────────

    def _renumber(self) -> None:
        for i, r in enumerate(self._rows, 1):
            r.set_number(i)

    def _move(self, row: StepRow, delta: int) -> None:
        idx = self._rows.index(row)
        new_idx = idx + delta
        if not (0 <= new_idx < len(self._rows)):
            return
        self._rows.pop(idx)
        self._rows.insert(new_idx, row)
        for r in self._rows:
            self._vbox.removeWidget(r)
        for i, r in enumerate(self._rows):
            self._vbox.insertWidget(i, r)
        self._renumber()
        self.changed.emit()

    def _remove(self, row: StepRow) -> None:
        if row in self._rows:
            self._rows.remove(row)
        self._vbox.removeWidget(row)
        row.deleteLater()
        self._renumber()
        self.changed.emit()


# ──────────────────────────── BotFlowTab ────────────────────────────

class BotFlowTab(QtWidgets.QWidget):
    """Tab content: flow name input + FlowEditor."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(8)

        # Flow name row
        name_row = QtWidgets.QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)
        lbl = QtWidgets.QLabel("流程名稱:")
        lbl.setObjectName("flowLabel")
        name_row.addWidget(lbl)
        self.name_edit = QtWidgets.QLineEdit("預設流程")
        self.name_edit.setMaximumWidth(180)
        name_row.addWidget(self.name_edit)
        name_row.addStretch(1)
        v.addLayout(name_row)

        # Hint
        hint = QtWidgets.QLabel(
            "依序執行每個步驟；「重複從頭」讓流程循環。"
        )
        hint.setObjectName("flowHint")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.editor = FlowEditor()
        v.addWidget(self.editor, stretch=1)

    def flow_name(self) -> str:
        return self.name_edit.text().strip() or "預設流程"

    def steps(self) -> list[dict]:
        return self.editor.steps()

    def set_flow(self, name: str, steps: list[dict]) -> None:
        self.name_edit.setText(name)
        self.editor.set_steps(steps)
