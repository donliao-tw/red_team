"""Theme constants + Qt stylesheet generator.

Designed to match the previous CustomTkinter look (rounded cards, blue
accent) while running natively on Qt for snappy switching. Supports a
runtime-switchable dark/light theme and 3 font-size levels.
"""
from __future__ import annotations

import pathlib


FAMILY_UI = "Inter Variable"  # bundled — closest open-source SF Pro alternative
FAMILY_UI_FALLBACK_CJK = "Noto Sans TC"  # Latin → Inter; CJK → Noto (PingFang-like)
FAMILY_UI_FALLBACK_OS = "Microsoft JhengHei UI"
FAMILY_MONO = "Cascadia Mono"


# ─────────────── Asset paths ───────────────
_ASSETS = pathlib.Path(__file__).parent / "assets"
ARROW_DOWN_PNG = (_ASSETS / "arrow_down.png").as_posix()
CHECK_PNG = (_ASSETS / "check.png").as_posix()


def load_bundled_fonts() -> list[str]:
    """Register all .ttf files in assets/fonts/ with QFontDatabase.

    Lets us ship Inter (and any future font) inside the project without
    polluting the system font folder. Returns the list of family names
    that became available, useful for debugging.
    """
    from PySide6 import QtGui

    fonts_dir = _ASSETS / "fonts"
    if not fonts_dir.exists():
        return []
    families: list[str] = []
    for ttf in fonts_dir.glob("*.ttf"):
        font_id = QtGui.QFontDatabase.addApplicationFont(str(ttf))
        if font_id != -1:
            families.extend(QtGui.QFontDatabase.applicationFontFamilies(font_id))
    return families


def ensure_icons() -> None:
    """Render the dropdown arrow and checkbox tick as PNGs at startup.

    Qt6's SVG plugin isn't bundled with PySide6 by default, so url()
    rules with .svg silently render nothing. We use QPainter instead.
    """
    from PySide6 import QtCore, QtGui

    arrow_path = _ASSETS / "arrow_down.png"
    check_path = _ASSETS / "check.png"
    _ASSETS.mkdir(parents=True, exist_ok=True)

    if not arrow_path.exists():
        pix = QtGui.QPixmap(10, 6)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QColor("#e0e0e0"))
        p.setPen(QtCore.Qt.NoPen)
        poly = QtGui.QPolygon([
            QtCore.QPoint(0, 0),
            QtCore.QPoint(10, 0),
            QtCore.QPoint(5, 6),
        ])
        p.drawPolygon(poly)
        p.end()
        pix.save(str(arrow_path), "PNG")

    if not check_path.exists():
        pix = QtGui.QPixmap(14, 14)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("white"))
        pen.setWidth(2)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen)
        path = QtGui.QPainterPath()
        path.moveTo(2.5, 7.5)
        path.lineTo(5.5, 10.5)
        path.lineTo(11.5, 4)
        p.drawPath(path)
        p.end()
        pix.save(str(check_path), "PNG")


# ─────────────── Palettes ───────────────
_DARK = {
    "bg_app":        "#242424",
    "bg_card":       "#2b2b2b",
    "bg_subpanel":   "#353535",
    "bg_input":      "#1c1c1c",
    "border":        "#3a3a3a",
    "border_light":  "#4a4a4a",
    "text_primary":   "#f0f0f0",
    "text_secondary": "#bababa",
    "text_tertiary":  "#7a7a7a",
    "accent":         "#1f6aa5",
    "accent_hover":   "#1a5a8d",
    "destructive":    "#c0392b",
    "destructive_hover": "#a83226",
    "scrollbar":      "#4a4a4a",
    "scrollbar_hover": "#5a5a5a",
    "groove":         "rgba(255, 255, 255, 0.08)",
    "nav_hover":      "rgba(255, 255, 255, 0.06)",
    "nav_active":     "rgba(255, 255, 255, 0.10)",
    "secondary_hover": "rgba(255, 255, 255, 0.05)",
    "item_hover":     "rgba(255, 255, 255, 0.07)",
    "tooltip_bg":     "#2e2e2e",
    "help_bg":        "#3a3a3a",
    "help_hover":     "#4a4a4a",
}

_LIGHT = {
    "bg_app":        "#f2f2f2",
    "bg_card":       "#ffffff",
    "bg_subpanel":   "#ececec",
    "bg_input":      "#ffffff",
    "border":        "#d8d8d8",
    "border_light":  "#c0c0c0",
    "text_primary":   "#1a1a1a",
    "text_secondary": "#555555",
    "text_tertiary":  "#909090",
    "accent":         "#1f6aa5",
    "accent_hover":   "#185285",
    "destructive":    "#c0392b",
    "destructive_hover": "#a83226",
    "scrollbar":      "#c0c0c0",
    "scrollbar_hover": "#a0a0a0",
    "groove":         "rgba(0, 0, 0, 0.10)",
    "nav_hover":      "rgba(0, 0, 0, 0.05)",
    "nav_active":     "rgba(0, 0, 0, 0.08)",
    "secondary_hover": "rgba(0, 0, 0, 0.04)",
    "item_hover":     "rgba(0, 0, 0, 0.05)",
    "tooltip_bg":     "#fafafa",
    "help_bg":        "#dedede",
    "help_hover":     "#cccccc",
}


# Module-level state — pages that need to read colors directly (e.g. for
# inline setStyleSheet on a single label) read these. Kept in sync by
# apply_theme() below.
_PALETTE = dict(_DARK)
THEME = "dark"
FONT_DELTA = 2  # default = "medium" (the most readable starting point)


def _expose() -> None:
    """Republish the active palette as module attributes."""
    g = globals()
    for k, v in _PALETTE.items():
        g[k.upper()] = v


_expose()


def set_theme(theme: str) -> None:
    """Switch the active palette. Call ``apply()`` afterwards."""
    global _PALETTE, THEME
    THEME = theme
    _PALETTE = dict(_DARK if theme == "dark" else _LIGHT)
    _expose()


def set_font_delta(delta: int) -> None:
    """Set the font-size adjustment (small=0, medium=2, large=4)."""
    global FONT_DELTA
    FONT_DELTA = delta


def make_qss() -> str:
    """Return the QSS for the current theme + font-delta state."""
    c = _PALETTE
    d = FONT_DELTA

    return f"""
* {{
    color: {c['text_primary']};
    font-family: "{FAMILY_UI}", "{FAMILY_UI_FALLBACK_CJK}", "{FAMILY_UI_FALLBACK_OS}";
    outline: none;
}}

QMainWindow, QDialog {{ background-color: {c['bg_app']}; }}

/* Frameless main-window shell + custom title bar. */
QFrame#appShell {{
    background-color: {c['bg_app']};
    border: 1px solid {c['border']};
}}
QFrame#titleBar {{
    background-color: #1a1a1a;
    border-bottom: 1px solid {c['border']};
}}
QLabel#titleBarLabel {{
    color: {c['text_secondary']};
    font-family: "{FAMILY_MONO}";
    font-size: {10 + d}pt;
    font-weight: bold;
}}
QPushButton#titleBtn {{
    background-color: transparent;
    border: none;
    color: {c['text_secondary']};
    font-size: {11 + d}pt;
    padding: 0;
}}
QPushButton#titleBtn:hover {{
    background-color: rgba(255, 255, 255, 0.08);
    color: {c['text_primary']};
}}
QPushButton#titleBtn[role="close"]:hover {{
    background-color: #e74c3c;
    color: white;
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QToolTip {{
    background-color: {c['tooltip_bg']};
    color: {c['text_primary']};
    border: 1px solid {c['border_light']};
    padding: 6px 10px;
    border-radius: 4px;
}}

/* Sidebar */
QFrame#sidebar {{
    background-color: {c['bg_app']};
    border-right: 1px solid {c['border']};
}}
QLabel#logo {{
    font-family: "{FAMILY_MONO}";
    font-size: {22 + d}pt;
    font-weight: bold;
}}
QLabel#logoSub {{ color: {c['text_tertiary']}; font-size: {10 + d}pt; }}
QPushButton#navBtn {{
    background-color: transparent;
    border: none; border-radius: 8px;
    padding: 12px 16px;
    text-align: left;
    font-size: {13 + d}pt;
    color: {c['text_primary']};
}}
QPushButton#navBtn:hover {{ background-color: {c['nav_hover']}; }}
QPushButton#navBtn[active="true"] {{ background-color: {c['nav_active']}; }}
QLabel#status {{ color: {c['text_secondary']}; font-size: {10 + d}pt; }}

/* Page header */
QLabel#pageTitle {{ font-size: {22 + d}pt; font-weight: bold; }}
QLabel#pageSubtitle {{ color: {c['text_secondary']}; font-size: {11 + d}pt; }}

/* Cards / sub-panels */
QFrame#card {{ background-color: {c['bg_card']}; border-radius: 10px; }}
QFrame#subpanel {{ background-color: {c['bg_subpanel']}; border-radius: 8px; }}

/* Dashboard cards on the main page */
QFrame#dashCard {{
    background-color: {c['bg_card']};
    border-radius: 12px;
    border: 1px solid transparent;
}}
QFrame#dashCard:hover {{
    background-color: {c['bg_subpanel']};
    border: 1px solid {c['accent']};
}}
QLabel#dashCardIcon {{ font-size: {28 + d}pt; background: transparent; }}
QLabel#dashCardName {{
    font-size: {16 + d}pt;
    font-weight: bold;
    background: transparent;
}}
QLabel#dashCardDesc {{
    color: {c['text_secondary']};
    font-size: {10 + d}pt;
    background: transparent;
}}
QLabel#cardTitle {{ color: {c['text_tertiary']}; font-size: {10 + d}pt; }}
QLabel#hint {{ color: {c['text_tertiary']}; font-size: {10 + d}pt; }}
QLabel#secondary {{ color: {c['text_secondary']}; }}

/* Buttons */
QPushButton {{
    background-color: {c['accent']};
    border: none; border-radius: 6px;
    padding: 6px 14px;
    color: white;
    font-size: {12 + d}pt;
}}
QPushButton:hover {{ background-color: {c['accent_hover']}; }}
QPushButton:disabled {{ background-color: {c['border_light']}; color: {c['text_tertiary']}; }}
QPushButton#destructive {{ background-color: {c['destructive']}; }}
QPushButton#destructive:hover {{ background-color: {c['destructive_hover']}; }}
QPushButton#secondary {{
    background-color: transparent;
    border: 1px solid {c['border_light']};
    color: {c['text_primary']};
}}
QPushButton#secondary:hover {{ background-color: {c['secondary_hover']}; }}
QPushButton#help {{
    background-color: {c['help_bg']};
    color: {c['text_secondary']};
    border-radius: 12px;
    padding: 0;
    font-weight: bold;
    font-size: {12 + d}pt;
    min-width: 24px; max-width: 24px;
    min-height: 24px; max-height: 24px;
}}
QPushButton#help:hover {{ background-color: {c['help_hover']}; }}

/* Inputs */
QLineEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {c['text_primary']};
    selection-background-color: {c['accent']};
    font-size: {10 + d}pt;
}}
QLineEdit:focus {{ border: 1px solid {c['accent']}; }}

QPlainTextEdit, QTextEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 6px;
    color: {c['text_primary']};
    selection-background-color: {c['accent']};
    font-size: {10 + d}pt;
}}

/* ComboBox */
QComboBox {{
    background-color: {c['accent']};
    border: none; border-radius: 4px;
    padding: 4px 8px;
    color: white;
    min-height: 22px;
    font-size: {10 + d}pt;
}}
QComboBox:hover {{ background-color: {c['accent_hover']}; }}
QComboBox::drop-down {{
    border: none;
    width: 14px;
    subcontrol-position: right center;
    margin-right: 4px;
}}
QComboBox::down-arrow {{
    image: url({ARROW_DOWN_PNG});
    width: 10px; height: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border_light']};
    border-radius: 4px;
    outline: none;
    padding: 4px;
    min-width: 60px;
}}
QComboBox QAbstractItemView::item {{
    padding: 5px 10px;
    border-radius: 3px;
    min-height: 22px;
    color: {c['text_primary']};
    font-size: {10 + d}pt;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {c['accent']};
    color: white;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {c['item_hover']};
}}

/* CheckBox / Radio */
QCheckBox {{
    spacing: 8px;
    color: {c['text_primary']};
    background-color: transparent;
    font-size: {10 + d}pt;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c['border_light']};
    border-radius: 3px;
    background-color: {c['bg_input']};
}}
QCheckBox::indicator:hover {{ border: 1px solid {c['accent']}; }}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border: 1px solid {c['accent']};
    image: url({CHECK_PNG});
}}

QRadioButton {{
    spacing: 8px;
    color: {c['text_primary']};
    background-color: transparent;
    font-size: {10 + d}pt;
}}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {c['border_light']};
    border-radius: 9px;
    background-color: {c['bg_input']};
}}
QRadioButton::indicator:hover {{ border: 2px solid {c['accent']}; }}
QRadioButton::indicator:checked {{
    background-color: {c['accent']};
    border: 4px solid {c['bg_app']};
    width: 12px; height: 12px;
}}

/* Slider */
QSlider::groove:horizontal {{
    height: 4px;
    background: {c['groove']};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {c['accent']};
    width: 14px; height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    border: 2px solid {c['bg_card']};
}}
QSlider::handle:horizontal:hover {{ background: {c['accent_hover']}; }}

/* Scroll */
QScrollArea {{ background-color: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {c['scrollbar']};
    border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['scrollbar_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; background: transparent;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {c['scrollbar']};
    border-radius: 5px; min-width: 24px;
}}

/* ─── Compact main panel ─── */

/* Function row — compact dark-grey pill toggles + shared gear. */
QFrame#funcRow {{ background-color: transparent; }}
QPushButton#funcMain {{
    background-color: #3a3f4a;
    border: 1px solid #4d525d;
    color: {c['text_primary']};
    font-size: {14 + d}pt;
    border-radius: 5px;
    padding: 0;
    text-align: center;
    min-height: 40px;
}}
QPushButton#funcMain:hover {{ background-color: #454a55; }}
QPushButton#funcMain:checked {{
    background-color: #d97706;
    border: 1px solid #d97706;
    color: white;
}}
QPushButton#funcMain:checked:hover {{ background-color: #b86305; }}
QPushButton#funcGear {{
    background-color: #3a3f4a;
    border: 1px solid #4d525d;
    color: {c['text_primary']};
    font-size: {13 + d}pt;
    border-radius: 5px;
    padding: 0;
}}
QPushButton#funcGear:hover {{ background-color: #454a55; }}

/* Progress bars — HP red, MP blue, generic falls back to accent. */
QProgressBar {{
    background-color: #1a1a1a;
    border: 1px solid {c['border']};
    border-radius: 3px;
}}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 2px; }}
QProgressBar#hpBar::chunk {{ background-color: #d94a4a; border-radius: 2px; }}
QProgressBar#mpBar::chunk {{ background-color: #3a8dd9; border-radius: 2px; }}
QLabel#progressText {{ color: {c['text_primary']}; font-size: {10 + d}pt; }}

/* Stats card — icon, primary value, secondary rate. */
QLabel#statIcon {{ font-size: {16 + d}pt; min-width: 26px; }}
QLabel#statPrimary {{
    font-family: "{FAMILY_MONO}";
    font-size: {13 + d}pt;
    font-weight: bold;
    color: {c['text_primary']};
}}
QLabel#statRate {{
    font-family: "{FAMILY_MONO}";
    font-size: {10 + d}pt;
    color: {c['text_tertiary']};
}}
QPushButton#resetBtn {{
    background-color: transparent;
    border: 1px solid {c['border_light']};
    border-radius: 5px;
    color: {c['text_primary']};
    font-size: {13 + d}pt;
    padding: 0;
}}
QPushButton#resetBtn:hover {{
    background-color: {c['secondary_hover']};
    border: 1px solid {c['accent']};
    color: {c['accent']};
}}
QLabel#warningHint {{ color: #f5a800; font-size: {9 + d}pt; }}
QLabel#banner {{ color: #f5a800; font-size: {9 + d}pt; padding: 2px 0; }}
QLabel#verLabel {{ color: {c['text_tertiary']}; font-size: {9 + d}pt; }}

/* Console log — green-on-black, monospace. */
QPlainTextEdit#consoleLog {{
    background-color: #1a1a1a;
    color: #6ce06c;
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 6px 8px;
    font-family: "{FAMILY_MONO}";
    font-size: {9 + d}pt;
    selection-background-color: {c['accent']};
}}

/* Inner tab bar (used inside 機器人設定). */
QTabWidget#innerTabs::pane {{
    border: 1px solid {c['border']};
    border-radius: 6px;
    background-color: {c['bg_card']};
    top: -1px;
}}
QTabWidget#innerTabs QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background-color: transparent;
    color: {c['text_secondary']};
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 4px;
    font-size: {11 + d}pt;
}}
QTabBar::tab:hover {{ background-color: {c['nav_hover']}; }}
QTabBar::tab:selected {{
    background-color: {c['bg_card']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-bottom: 1px solid {c['bg_card']};
}}

/* Footer icon button — bigger so emoji glyphs read clearly. */
QPushButton#footerIcon {{
    background-color: transparent;
    border: 1px solid {c['border_light']};
    border-radius: 6px;
    color: {c['text_primary']};
    font-size: {16 + d}pt;
    padding: 0;
}}
QPushButton#footerIcon:hover {{
    background-color: {c['secondary_hover']};
    border: 1px solid {c['accent']};
}}

/* Small icon-only button (refresh, etc.). */
QPushButton#iconBtn {{
    background-color: transparent;
    border: 1px solid {c['border_light']};
    border-radius: 4px;
    color: {c['text_primary']};
    font-size: {12 + d}pt;
    padding: 0;
}}
QPushButton#iconBtn:hover {{ background-color: {c['secondary_hover']}; }}
"""
