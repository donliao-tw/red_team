"""技能設定 — protection / auto-buffs / custom timers / active skills."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import widgets
from ._base import Page


# (label, default_hotkey, default_enabled, sub_field|None)
BUFFS: list[tuple[str, str, bool, tuple | None]] = [
    ("綠水",         "P1-F10", False, None),
    ("2段加速",       "P1-F11", False, None),
    ("解毒 / 樹枝",   "P1-F7",  False, ("delay_secs", 0)),
    ("精力湯",        "P1-F12", False, None),
    ("神聖武器",      "P1-F6",  False, None),
    ("負重強化",      "P2-F8",  True,  None),
    ("藍水（負重<50）", "P1-F11", True,  ("mp_below", 80)),
    ("戰鬥強化捲",    "P1-F5",  False, None),
    ("保護罩",        "P2-F9",  True,  None),
    ("鎧甲護持",      "P2-F10", True,  None),
    ("魔法防禦",      "P1-F10", False, None),
    ("淨化精神",      "P1-F8",  False, None),
    ("變身卷軸",      "P1-F12", False, ("morph_select", "相同外觀變身")),
]

CUSTOM_DEFAULTS = [
    ("P2-F11", 1800),
    ("P1-F6",  1800),
    ("P1-F7",  1800),
    ("P1-F8",  1800),
    ("P1-F9",  1800),
    ("P1-F10", 1800),
]

ACTIVE_SKILLS: list[tuple[str, str, bool, tuple | None]] = [
    ("加速術",       "P1-F9",  True,  None),
    ("通暢氣脈術",    "P3-F9",  True,  None),
    ("使用敏捷",      "P3-F10", True,  None),
    ("擬似魔法武器",  "P2-F11", True,  None),
    ("體魄強健術",    "P2-F12", True,  None),
    ("使用力盾",      "P3-F12", True,  ("origin_helmet_hotkey", "P3-F8")),
    ("風之神射",      "P1-F5",  False, None),
    ("火焰武器",      "P1-F6",  False, None),
    ("大地防護",      "P1-F7",  False, None),
]

MORPH_CHOICES = ["相同外觀變身", "不同外觀變身", "保留變身"]

FOOTER_HINTS = [
    "自動解毒以外的 BUFF 僅掛機時有效",
    "加速使用力盾內建 MP 限制 20",
    "通暢使用敏捷內建 MP 限制 25",
    "體魄使用力盾內建 MP 限制 25",
    "擬似使用力盾內建 MP 限制 10",
]


class SkillSettingsPage(Page):
    title = "技能設定"
    subtitle = "保護功能、自動 Buff、自定計時、主動技能"

    def build(self) -> None:
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

        col_a.addWidget(self._build_protection())
        col_a.addWidget(self._build_custom())
        col_a.addStretch(1)

        col_b.addWidget(self._build_buff())
        col_b.addWidget(self._build_active())
        col_b.addStretch(1)

        cols.addLayout(col_a, stretch=1)
        cols.addLayout(col_b, stretch=1)

        self.body_layout.addWidget(scroll, stretch=1)
        self.body_layout.addWidget(widgets.help_button(
            FOOTER_HINTS, label_text="使用注意事項（hover）",
        ))

    # ------------------------------------------------------------------ helpers

    def _row(self) -> tuple[QtWidgets.QWidget, QtWidgets.QHBoxLayout]:
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        return w, h

    def _two_subpanels(self) -> tuple[QtWidgets.QWidget, QtWidgets.QVBoxLayout, QtWidgets.QVBoxLayout]:
        """Two side-by-side sub-panels — one solid colour block per column.

        Each column gets a single sub-panel background; rows inside are
        transparent so the panel looks like one continuous block, not
        striped.
        """
        wrap = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        left_panel, left_layout = widgets.sub_panel()
        right_panel, right_layout = widgets.sub_panel()

        h.addWidget(left_panel, stretch=1)
        h.addWidget(right_panel, stretch=1)
        return wrap, left_layout, right_layout

    @staticmethod
    def _key_for(label: str) -> str:
        return (
            label.replace(" ", "")
                 .replace("/", "_")
                 .replace("（", "_")
                 .replace("）", "")
                 .replace("(", "_")
                 .replace(")", "")
                 .replace("<", "lt")
        )

    # ------------------------------------------------------------------ 保護功能

    def _build_protection(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("保護功能")

        # 腳下有物品時自動 F4
        cb = widgets.checkbox("腳下有物品時自動 F4")
        self.cfg["autof4_on_item"] = cb
        layout.addWidget(cb)

        self._protect_pct(layout, "喝水保護", "drink_protect", "F7", 75, True, paged=False)
        self._protect_hpmp(layout, "自補保護", "self_heal", "P1-F5", True,
                           "HP 低於", 80, "MP 高於", 40,
                           "攻擊中或三格內有怪不使用", "self_heal_avoid_combat")
        self._protect_pct(layout, "回村保護", "return_protect", "F6", 26, True, paged=False)
        self._protect_hpmp(layout, "自動驅體", "auto_revive", "P1-F6", False,
                           "HP 高於", 80, "MP 低於", 20,
                           "攻擊中或三格內有怪不使用", "auto_revive_avoid_combat")

        return card

    def _protect_pct(self, layout, label, key, hk, pct, on, *, paged) -> None:
        row, h = self._row()
        cb = widgets.checkbox(label, checked=on)
        self.cfg[f"{key}_enabled"] = cb
        h.addWidget(cb); h.addSpacing(6)

        hk_widget = widgets.HotkeyMenu(hk, paged=paged)
        self.cfg[f"{key}_hotkey"] = hk_widget
        h.addWidget(hk_widget); h.addSpacing(10)

        ps = widgets.PercentSlider(pct)
        self.cfg[f"{key}_pct"] = ps
        h.addWidget(ps, stretch=1)
        layout.addWidget(row)

    def _protect_hpmp(self, layout, label, key, hk, on,
                      hp_label, hp_default, mp_label, mp_default,
                      sub_label, sub_key) -> None:
        # Main: checkbox + hotkey
        row, h = self._row()
        cb = widgets.checkbox(label, checked=on)
        self.cfg[f"{key}_enabled"] = cb
        h.addWidget(cb); h.addSpacing(10)
        hk_widget = widgets.HotkeyMenu(hk)
        self.cfg[f"{key}_hotkey"] = hk_widget
        h.addWidget(hk_widget); h.addStretch(1)
        layout.addWidget(row)

        # Indented HP slider
        for sub_label_text, default, var_key in [
            (hp_label, hp_default, f"{key}_hp_pct"),
            (mp_label, mp_default, f"{key}_mp_pct"),
        ]:
            row, h = self._row()
            h.addSpacing(20)
            lbl = widgets.label(sub_label_text, secondary=True)
            lbl.setMinimumWidth(64)
            h.addWidget(lbl)
            ps = widgets.PercentSlider(default)
            self.cfg[var_key] = ps
            h.addWidget(ps, stretch=1)
            layout.addWidget(row)

        # Sub-checkbox
        row, h = self._row()
        h.addSpacing(20)
        cb = widgets.checkbox(sub_label)
        self.cfg[sub_key] = cb
        h.addWidget(cb); h.addStretch(1)
        layout.addWidget(row)

    # ------------------------------------------------------------------ 自動 Buff

    def _build_buff(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("自動施放 Buff / 熱鍵")

        wrap, left, right = self._two_subpanels()
        half = (len(BUFFS) + 1) // 2
        for label, hk, on, sub in BUFFS[:half]:
            self._buff_row(left, label, hk, on, sub)
        left.addStretch(1)
        for label, hk, on, sub in BUFFS[half:]:
            self._buff_row(right, label, hk, on, sub)
        right.addStretch(1)

        layout.addWidget(wrap)
        return card

    def _buff_row(self, layout, label_text, default_hk, default_on, sub) -> None:
        key = self._key_for(label_text)

        row, h = self._row()
        cb = widgets.checkbox(label_text, checked=default_on)
        self.cfg[f"buff_{key}_enabled"] = cb
        h.addWidget(cb); h.addStretch(1)

        hk = widgets.HotkeyMenu(default_hk)
        self.cfg[f"buff_{key}_hotkey"] = hk
        h.addWidget(hk)
        layout.addWidget(row)

        if sub is None:
            return

        kind, default = sub
        sub_w, sh = self._row()
        sh.addSpacing(18)
        if kind == "delay_secs":
            sh.addWidget(widgets.label("延遲解毒 秒數:", secondary=True))
            e = widgets.num_entry(default)
            self.cfg[f"buff_{key}_delay_secs"] = e
            sh.addWidget(e); sh.addStretch(1)
        elif kind == "mp_below":
            sh.addWidget(widgets.label("MP 低於(%):", secondary=True))
            e = widgets.num_entry(default)
            self.cfg[f"buff_{key}_mp_below"] = e
            sh.addWidget(e); sh.addStretch(1)
        elif kind == "morph_select":
            sh.addWidget(widgets.label("選擇:", secondary=True))
            m = widgets.option_menu(MORPH_CHOICES, default, width=140)
            self.cfg[f"buff_{key}_morph"] = m
            sh.addWidget(m); sh.addStretch(1)
        layout.addWidget(sub_w)

    # ------------------------------------------------------------------ 自定計時

    def _build_custom(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("自定計時 (#1–#6)")

        wrap, left, right = self._two_subpanels()
        half = (len(CUSTOM_DEFAULTS) + 1) // 2
        for i, (hk, secs) in enumerate(CUSTOM_DEFAULTS[:half], start=1):
            self._custom_row(left, i, hk, secs)
        left.addStretch(1)
        for i, (hk, secs) in enumerate(CUSTOM_DEFAULTS[half:], start=half + 1):
            self._custom_row(right, i, hk, secs)
        right.addStretch(1)

        layout.addWidget(wrap)
        return card

    def _custom_row(self, layout, i, hk, secs) -> None:
        row, h = self._row()
        cb = widgets.checkbox(f"自定 #{i}")
        self.cfg[f"custom_{i}_enabled"] = cb
        h.addWidget(cb); h.addStretch(1)
        hk_widget = widgets.HotkeyMenu(hk)
        self.cfg[f"custom_{i}_hotkey"] = hk_widget
        h.addWidget(hk_widget)
        layout.addWidget(row)

        sub_w, sh = self._row()
        sh.addSpacing(18)
        sh.addWidget(widgets.label(f"#{i} 秒數:", secondary=True))
        e = widgets.num_entry(secs, width=72)
        self.cfg[f"custom_{i}_secs"] = e
        sh.addWidget(e); sh.addStretch(1)
        layout.addWidget(sub_w)

    # ------------------------------------------------------------------ 主動技能

    def _build_active(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("主動技能")

        wrap, left, right = self._two_subpanels()
        half = (len(ACTIVE_SKILLS) + 1) // 2
        for label, hk, on, sub in ACTIVE_SKILLS[:half]:
            self._active_row(left, label, hk, on, sub)
        left.addStretch(1)
        for label, hk, on, sub in ACTIVE_SKILLS[half:]:
            self._active_row(right, label, hk, on, sub)
        right.addStretch(1)

        layout.addWidget(wrap)
        return card

    def _active_row(self, layout, label_text, default_hk, default_on, sub) -> None:
        key = self._key_for(label_text)

        row, h = self._row()
        cb = widgets.checkbox(label_text, checked=default_on)
        self.cfg[f"skill_{key}_enabled"] = cb
        h.addWidget(cb); h.addStretch(1)
        hk = widgets.HotkeyMenu(default_hk)
        self.cfg[f"skill_{key}_hotkey"] = hk
        h.addWidget(hk)
        layout.addWidget(row)

        if sub and sub[0] == "origin_helmet_hotkey":
            sub_w, sh = self._row()
            sh.addSpacing(18)
            sh.addWidget(widgets.label("原頭盔熱鍵:", secondary=True))
            hk2 = widgets.HotkeyMenu(sub[1])
            self.cfg[f"skill_{key}_origin_helmet"] = hk2
            sh.addWidget(hk2); sh.addStretch(1)
            layout.addWidget(sub_w)
