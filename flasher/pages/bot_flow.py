"""Bot flow editor — ordered list of automation steps.

Each step has a type (teleport / shop / wait / patrol / loop) and inline
parameters. Steps are displayed in a scrollable list; ▲▼ buttons reorder
them and × removes them.  The widget exposes steps() / set_steps() so the
parent page can persist the flow.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import widgets

# (key, display_label, implemented)
STEP_DEFS = [
    ("teleport", "傳送",     True),
    ("shop",     "購物",     True),
    ("wait",     "等待",     True),
    ("patrol",   "巡邏攻擊", False),
    ("loop",     "重複從頭", True),
]

_KEYS   = [d[0] for d in STEP_DEFS]
_LABELS = [d[1] for d in STEP_DEFS]
_DONE   = {d[0]: d[2] for d in STEP_DEFS}


# ──────────────────────────── params helpers ────────────────────────────

def _make_params(step_type: str) -> QtWidgets.QWidget:
    w = QtWidgets.QWidget()
    h = QtWidgets.QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)

    if step_type == "teleport":
        h.addWidget(QtWidgets.QLabel("目的地:"))
        ed = QtWidgets.QLineEdit()
        ed.setPlaceholderText("例: 奇岩村 雜貨商人")
        ed.setObjectName("flowParam_destination")
        h.addWidget(ed, stretch=1)

    elif step_type == "shop":
        lbl = QtWidgets.QLabel("（使用購物設定清單）")
        lbl.setObjectName("flowParamHint")
        h.addWidget(lbl)
        h.addStretch(1)

    elif step_type in ("wait", "patrol"):
        sp = QtWidgets.QSpinBox()
        sp.setRange(1, 600)
        sp.setValue(60 if step_type == "patrol" else 5)
        sp.setObjectName("flowParam_minutes")
        sp.setFixedWidth(64)
        h.addWidget(sp)
        h.addWidget(QtWidgets.QLabel("分鐘"))
        if not _DONE[step_type]:
            lbl = QtWidgets.QLabel("（未實作）")
            lbl.setObjectName("flowParamHint")
            h.addWidget(lbl)
        h.addStretch(1)

    elif step_type == "loop":
        sp = QtWidgets.QSpinBox()
        sp.setRange(0, 9999)
        sp.setValue(0)
        sp.setObjectName("flowParam_times")
        sp.setFixedWidth(64)
        h.addWidget(sp)
        h.addWidget(QtWidgets.QLabel("次（0＝無限）"))
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

class StepRow(QtWidgets.QFrame):
    """One step: [▲▼] [type combo] [params] [×]"""

    sig_move_up   = QtCore.Signal()
    sig_move_down = QtCore.Signal()
    sig_remove    = QtCore.Signal()

    def __init__(self, step_type: str = "teleport",
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("flowStep")
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(6, 3, 6, 3)
        h.setSpacing(6)

        # ▲▼ stack
        btn_up = QtWidgets.QPushButton("▲")
        btn_up.setFixedSize(22, 16)
        btn_up.setObjectName("flowArrow")
        btn_up.setCursor(QtCore.Qt.PointingHandCursor)
        btn_up.clicked.connect(self.sig_move_up)

        btn_dn = QtWidgets.QPushButton("▼")
        btn_dn.setFixedSize(22, 16)
        btn_dn.setObjectName("flowArrow")
        btn_dn.setCursor(QtCore.Qt.PointingHandCursor)
        btn_dn.clicked.connect(self.sig_move_down)

        arrows = QtWidgets.QWidget()
        av = QtWidgets.QVBoxLayout(arrows)
        av.setContentsMargins(0, 0, 0, 0)
        av.setSpacing(1)
        av.addWidget(btn_up)
        av.addWidget(btn_dn)
        h.addWidget(arrows)

        # Type combo — grey out unimplemented entries
        self._combo = QtWidgets.QComboBox()
        self._combo.setFixedWidth(96)
        for key, label, done in STEP_DEFS:
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

        # Params: one QWidget per type, switched via QStackedWidget
        self._stack = QtWidgets.QStackedWidget()
        self._stack.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        for key, _, _ in STEP_DEFS:
            self._stack.addWidget(_make_params(key))
        self._stack.setCurrentIndex(init_idx)
        h.addWidget(self._stack, stretch=1)

        # × delete
        btn_x = QtWidgets.QPushButton("×")
        btn_x.setFixedSize(24, 24)
        btn_x.setObjectName("shopDel")
        btn_x.setCursor(QtCore.Qt.PointingHandCursor)
        btn_x.clicked.connect(self.sig_remove)
        h.addWidget(btn_x)

    def _on_type_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

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
    """Scrollable ordered list of StepRow widgets + ＋ add button."""

    changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self._container = QtWidgets.QWidget()
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setContentsMargins(0, 0, 4, 0)
        self._vbox.setSpacing(4)
        self._vbox.addStretch(1)          # sentinel stretch at the bottom
        scroll.setWidget(self._container)
        outer.addWidget(scroll, stretch=1)

        add_btn = QtWidgets.QPushButton("＋ 新增步驟")
        add_btn.setObjectName("shopAdd")
        add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self.add_step("teleport"))
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(add_btn)
        row.addStretch(1)
        outer.addLayout(row)

        self._rows: list[StepRow] = []

    # ── public API ─────────────────────────────────────────────────

    def add_step(self, step_type: str = "teleport") -> StepRow:
        row = StepRow(step_type)
        pos = len(self._rows)
        self._rows.append(row)
        self._vbox.insertWidget(pos, row)   # before the sentinel stretch
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

    # ── internals ──────────────────────────────────────────────────

    def _move(self, row: StepRow, delta: int) -> None:
        idx = self._rows.index(row)
        new_idx = idx + delta
        if not (0 <= new_idx < len(self._rows)):
            return
        self._rows.pop(idx)
        self._rows.insert(new_idx, row)
        # Rebuild order in layout (sentinel stretch stays last)
        for r in self._rows:
            self._vbox.removeWidget(r)
        for i, r in enumerate(self._rows):
            self._vbox.insertWidget(i, r)
        self.changed.emit()

    def _remove(self, row: StepRow) -> None:
        if row in self._rows:
            self._rows.remove(row)
        self._vbox.removeWidget(row)
        row.deleteLater()
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
        name_row.addWidget(QtWidgets.QLabel("流程名稱:"))
        self.name_edit = QtWidgets.QLineEdit("預設流程")
        self.name_edit.setMaximumWidth(200)
        name_row.addWidget(self.name_edit)
        name_row.addStretch(1)
        v.addLayout(name_row)

        # Hint
        hint = QtWidgets.QLabel(
            "依序執行每個步驟；「重複從頭」讓流程循環。"
            "灰色項目尚未實作，加入後執行時會跳過。"
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        v.addWidget(hint)

        # The flow editor
        self.editor = FlowEditor()
        v.addWidget(self.editor, stretch=1)

    def flow_name(self) -> str:
        return self.name_edit.text().strip() or "預設流程"

    def steps(self) -> list[dict]:
        return self.editor.steps()

    def set_flow(self, name: str, steps: list[dict]) -> None:
        self.name_edit.setText(name)
        self.editor.set_steps(steps)
