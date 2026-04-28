"""機器人設定 — combat behaviour, teleport triggers, blacklists."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import widgets
from ._base import Page


DEFAULT_MOB_BLACKLIST = "史萊姆;魔法師;克特;黑長者;飛龍;巨大飛龍;卡士伯;巴土瑟;馬庫爾;西瑪;巨蟬女皇;死亡騎士"
DEFAULT_PICKUP_BLACKLIST = "箭;肉;+0 箭;+0 銀箭"


class BotSettingsPage(Page):
    title = "機器人設定"
    subtitle = "戰鬥模式、瞬移觸發、黑名單"

    def build(self) -> None:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        content = QtWidgets.QWidget()
        scroll.setWidget(content)

        cols = QtWidgets.QHBoxLayout(content)
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(16)

        col_a = QtWidgets.QVBoxLayout()
        col_a.setSpacing(12)
        col_b = QtWidgets.QVBoxLayout()
        col_b.setSpacing(12)

        col_a.addWidget(self._build_combat())
        col_a.addWidget(self._build_general())
        col_a.addWidget(self._build_surround())
        col_a.addStretch(1)

        col_b.addWidget(self._build_weapon())
        col_b.addWidget(self._build_pickup())
        col_b.addWidget(self._build_blacklist(), stretch=1)

        cols.addLayout(col_a, stretch=1)
        cols.addLayout(col_b, stretch=1)

        self.body_layout.addWidget(scroll, stretch=1)

        self.body_layout.addWidget(widgets.help_button(
            [
                "瞬捲熱鍵不管在哪一頁都請放在同一格上",
                "回捲熱鍵請於「技能設定 → 保護功能」中設定",
            ],
            label_text="使用注意事項（hover）",
        ))

    # ------------------------------------------------------------------ helpers

    def _row(self) -> tuple[QtWidgets.QWidget, QtWidgets.QHBoxLayout]:
        w = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        return w, layout

    # ------------------------------------------------------------------ cards

    def _build_combat(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("戰鬥模式")

        row, h = self._row()
        rb_m = widgets.radio("近戰", checked=True, value="melee")
        rb_r = widgets.radio("遠程", value="ranged")
        grp = QtWidgets.QButtonGroup(card)
        grp.addButton(rb_m); grp.addButton(rb_r)
        self.cfg["combat_type"] = grp
        h.addWidget(rb_m); h.addSpacing(20)
        h.addWidget(rb_r); h.addSpacing(28)

        h.addWidget(widgets.label("瞬移卷熱鍵:"))
        hk = widgets.HotkeyMenu("F8", paged=False)
        self.cfg["teleport_hotkey"] = hk
        h.addWidget(hk)
        h.addStretch(1)
        layout.addWidget(row)

        return card

    def _build_general(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("通用設定")

        # Row: 禮貌模式 | 掛機時不撿物
        row, h = self._row()
        cb1 = widgets.checkbox("禮貌模式", checked=True)
        cb2 = widgets.checkbox("掛機時不撿物")
        self.cfg["polite_mode"] = cb1
        self.cfg["idle_no_pickup"] = cb2
        h.addWidget(cb1); h.addSpacing(24)
        h.addWidget(cb2)
        h.addStretch(1)
        layout.addWidget(row)

        # Row: 負重回村(%) [82]
        row, h = self._row()
        cb = widgets.checkbox("負重回村(%):", checked=True)
        e = widgets.num_entry("82")
        self.cfg["weight_return_enabled"] = cb
        self.cfg["weight_return_pct"] = e
        h.addWidget(cb); h.addWidget(e)
        h.addStretch(1)
        layout.addWidget(row)

        # Row: 無經驗瞬移(秒) [60] (僅自由掛機有效)
        row, h = self._row()
        cb = widgets.checkbox("無經驗瞬移(秒):", checked=True)
        e = widgets.num_entry("60", width=64)
        self.cfg["noexp_teleport_enabled"] = cb
        self.cfg["noexp_teleport_secs"] = e
        h.addWidget(cb); h.addWidget(e); h.addSpacing(6)
        h.addWidget(widgets.hint("(僅自由掛機有效)"))
        h.addStretch(1)
        layout.addWidget(row)

        # Row: 貼身怪無視黑名單
        cb = widgets.checkbox("貼身怪無視黑名單")
        self.cfg["close_mob_ignore_blacklist"] = cb
        layout.addWidget(cb)

        # Row: 有玩家瞬移 + range/count
        row, h = self._row()
        cb = widgets.checkbox("有玩家瞬移，範圍(格):")
        self.cfg["teleport_on_player"] = cb
        h.addWidget(cb)
        e = widgets.num_entry("10")
        self.cfg["teleport_player_range"] = e
        h.addWidget(e); h.addSpacing(16)
        h.addWidget(widgets.label("數量:"))
        e = widgets.num_entry("1")
        self.cfg["teleport_player_count"] = e
        h.addWidget(e); h.addStretch(1)
        layout.addWidget(row)

        # Row: 有紫/紅人瞬移 + range
        row, h = self._row()
        cb = widgets.checkbox("有紫/紅人瞬移，範圍(格):", checked=True)
        self.cfg["teleport_on_purple"] = cb
        h.addWidget(cb)
        e = widgets.num_entry("3")
        self.cfg["teleport_purple_range"] = e
        h.addWidget(e); h.addStretch(1)
        layout.addWidget(row)

        # Row: 被包圍瞬移 + range/count
        row, h = self._row()
        cb = widgets.checkbox("被包圍瞬移，範圍(格):")
        self.cfg["surrounded_teleport"] = cb
        h.addWidget(cb)
        e = widgets.num_entry("1")
        self.cfg["surrounded_range"] = e
        h.addWidget(e); h.addSpacing(16)
        h.addWidget(widgets.label("數量:"))
        e = widgets.num_entry("5")
        self.cfg["surrounded_count"] = e
        h.addWidget(e); h.addStretch(1)
        layout.addWidget(row)

        return card

    def _build_surround(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("被包圍動作")

        defaults = [("P1-F5", 1, 3, 300), ("P1-F6", 1, 3, 300), ("P1-F7", 1, 3, 300)]
        for i, (hk_val, rng, cnt, cd) in enumerate(defaults, start=1):
            # Main row: checkbox + hotkey
            main, h = self._row()
            cb = widgets.checkbox(f"被包圍使用 #{i}")
            self.cfg[f"surround_use_{i}_enabled"] = cb
            h.addWidget(cb); h.addSpacing(8)
            hk = widgets.HotkeyMenu(hk_val)
            self.cfg[f"surround_use_{i}_hotkey"] = hk
            h.addWidget(hk); h.addStretch(1)
            layout.addWidget(main)

            # Sub row: 範圍 / 數量 / 冷卻
            sub, h = self._row()
            h.addSpacing(20)
            h.addWidget(widgets.label("範圍", secondary=True))
            e = widgets.num_entry(rng); self.cfg[f"surround_use_{i}_range"] = e
            h.addWidget(e); h.addSpacing(12)
            h.addWidget(widgets.label("數量", secondary=True))
            e = widgets.num_entry(cnt); self.cfg[f"surround_use_{i}_count"] = e
            h.addWidget(e); h.addSpacing(12)
            h.addWidget(widgets.label("冷卻(秒)", secondary=True))
            e = widgets.num_entry(cd, width=64); self.cfg[f"surround_use_{i}_cooldown"] = e
            h.addWidget(e); h.addStretch(1)
            layout.addWidget(sub)

        return card

    def _build_weapon(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("武器與安全")

        row, h = self._row()
        cb = widgets.checkbox("武器損壞時觸發回村")
        self.cfg["weapon_break_return"] = cb
        h.addWidget(cb); h.addSpacing(6)
        h.addWidget(widgets.hint("(腳本有修刀才有效)"))
        h.addStretch(1)
        layout.addWidget(row)

        cb = widgets.checkbox("掛機時發現武器損壞將周圍一格內玩家加入黑名單")
        cb.setWordWrap(True) if hasattr(cb, "setWordWrap") else None
        self.cfg["weapon_break_blacklist_nearby"] = cb
        layout.addWidget(cb)

        row, h = self._row()
        h.addWidget(widgets.label("黑名單玩家接近瞬移範圍(步):"))
        e = widgets.num_entry("15")
        self.cfg["blacklist_player_range_steps"] = e
        h.addWidget(e); h.addStretch(1)
        layout.addWidget(row)

        return card

    def _build_pickup(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("拾取 / 殺怪")
        row, h = self._row()

        h.addWidget(widgets.label("拾取允許距離:"))
        e = widgets.num_entry("3"); self.cfg["pickup_distance"] = e
        h.addWidget(e); h.addSpacing(20)

        h.addWidget(widgets.label("拾取超時(秒):"))
        e = widgets.num_entry("5"); self.cfg["pickup_timeout_secs"] = e
        h.addWidget(e); h.addSpacing(20)

        h.addWidget(widgets.label("殺怪超時(秒):"))
        e = widgets.num_entry("20"); self.cfg["kill_timeout_secs"] = e
        h.addWidget(e); h.addStretch(1)
        layout.addWidget(row)

        return card

    def _build_blacklist(self) -> QtWidgets.QFrame:
        card, layout = widgets.make_card("黑名單", expand=True)

        rows = [
            ("BOSS 黑名單", "以分號隔開（定點:10 格內回村;自由:10 格內瞬移）", "", "boss_blacklist"),
            ("怪物黑名單（不主動攻擊）", "以分號隔開", DEFAULT_MOB_BLACKLIST, "mob_blacklist"),
            ("玩家黑名單（接近就瞬移）", "以分號隔開", "", "player_blacklist"),
            ("拾取黑名單（不撿）", "以分號隔開", DEFAULT_PICKUP_BLACKLIST, "pickup_blacklist"),
        ]
        for label_text, hint_text, default, key in rows:
            layout.addWidget(widgets.label(label_text))
            layout.addWidget(widgets.hint(hint_text))
            box = widgets.textarea(default, height=72)
            self.cfg[key] = box
            layout.addWidget(box, stretch=1)
            layout.addSpacing(4)

        return card
