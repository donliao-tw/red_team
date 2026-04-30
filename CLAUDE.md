# Project notes for AI assistants

This file is loaded as project memory by Claude Code. It is the orientation
doc when pulling this repo on a new machine — read it before doing anything
substantial. It captures **decisions and context that aren't derivable from
the code** (the why, not the what).

> Authoritative sources of truth, in order:
> 1. Current source tree — for *what exists*.
> 2. [docs/dev-log.md](docs/dev-log.md) — for *what happened in each session* (newest first).
> 3. This file — for *what's still placeholder, what to do next, and ground rules*.
> 4. [README.md](README.md) — for *user-facing setup*.

---

## What this project is

A Linux-developed PySide6 desktop control panel for a "human-like AI
competition" gaming bot. Output to the game is via an **external Arduino
HID mouse** (firmware in `firmware/hid_mouse/`); the UI panel runs on the
same machine as the game. Architecture, USB VID/PID spoofing, and the
flashing pipeline are all in [docs/SOP-001-arduino-flash.md](docs/SOP-001-arduino-flash.md).

**Why this matters for design choices:**
- The bot must be **undetectable to in-game anti-cheat / contest judges**.
  Anything that hooks the game process — `ReadProcessMemory`,
  `WriteProcessMemory`, DLL injection, kernel hooks — is off-limits.
  Game-state input therefore comes from **screen capture + OCR / CV**,
  not memory reading. Output goes through real USB HID reports from the
  Arduino, not `SendInput`.
- The judge's detector will check USB VID/PID, so the firmware spoofs
  Logitech / Razer / Microsoft identities at compile time.

If a future request would require memory reading, push back and propose
a CV / OCR alternative.

---

## Current state (as of 2026-04-30)

**UI: essentially done.** Compact main panel + settings dialog + frameless
dark title bar. See dev-log entry 2026-04-30 for the full layout map and
verification.

**Field functionality: almost entirely placeholder.** The next phase is
wiring widgets to real behaviour. See the "Field wiring" punch list at the
bottom of this doc, kept here (not in dev-log) so it stays the canonical
to-do across sessions.

**Verified-passing assertions** (run via offscreen Qt):
- All four settings pages (bot / skill / hardware / env) construct OK
- Mutual exclusion: 機器人 ↔ 娃娃 swap correctly; 保護 stays independent
- Most-recently-toggled feature drives the shared gear's tab routing
- 機器人 ↔ 娃娃 active colour sync (bidirectional, no signal loop)
- Console-log fold/expand cycles min/max height correctly

---

## Architecture cheatsheet

```
flasher/
├── main.py               ← entry point. MainWindow = compact runtime panel
│                          (frameless, custom TitleBar, login row, HP/MP bars,
│                           three icon toggles + shared gear, stats card,
│                           foldable log, footer). Holds a lazy-created
│                           SettingsDialog for all detailed configuration.
├── settings_dialog.py    ← QDialog with sidebar + page stack (the "old"
│                          MainWindow shape). Forwards set_status /
│                          set_font_size / set_theme back to MainWindow.
├── style.py              ← All QSS. Dark theme + Light theme palettes,
│                          gradients, FONT_DELTA for font-size levels.
├── widgets.py            ← Shared form primitives (HotkeyMenu, num_entry,
│                          checkbox, radio, percent_slider, hint, help_button,
│                          textarea, make_card).
└── pages/
    ├── _base.py          ← Page base class. Sub-classes override build();
    │                      pages keep state in self.cfg, with serialize()
    │                      / apply() already implemented for save/load.
    ├── bot_settings.py   ← Inner QTabWidget (3 tabs):
    │                       - 保護設定 — placeholder (port from skill page later)
    │                       - 自動設定 — full content (戰鬥/通用/被包圍/武器/拾取/黑名單)
    │                       - 娃娃設定 — placeholder
    ├── skill_settings.py ← 保護功能 + 自動 Buff + 自定計時 + 主動技能
    ├── hardware_settings.py
    └── environment_settings.py  ← Arduino flash UI lives here
```

The compact main panel's icon ⚙ (the shared one) routes to **bot page →
matching inner tab** based on which toggle was last activated. The login
row's separate ⚙ jumps to **skill page** as a shortcut.

Pages talk to the parent window via `self.app` — that's MainWindow when
opened directly (legacy), and SettingsDialog when opened from the main
panel. Both expose `switch_page / set_font_size / set_theme / set_status`.

---

## Conventions established by user feedback

These are direct corrections from the user; do not relitigate them.

| Decision | Reason |
|---|---|
| **No bullet-dot `·` separators between data points** | Read as amateur. Use whitespace + typographic hierarchy (size + weight + colour). |
| **Tooltips, not text labels, for icons** | The user wants minimal panels; descriptions belong in hover. |
| **Inter (proportional) for stat numbers, not Cascadia Mono** | Mono bold felt "wide" / chunky. Inter semibold reads cleaner. |
| **Stats values colour-coded** | EXP light blue `#7fb8e6`, gold warm `#e6c14a`, time light brown `#c4a577`. |
| **active button colour ≠ light blue** | Default is amber `#d97706`; right-click any toggle to override. |
| **保護 independent**, **機器人 ↔ 娃娃 mutually exclusive AND share colour** | Protect is an always-on auxiliary; the other two are primary modes. |
| **Frameless window with custom dark title bar** | The OS title bar (white on Linux GTK) clashed with the dark body. |
| **Right-click toggles → QColorDialog** | User wants to choose their own active colour. Already implemented. |
| **Metallic gradients across buttons / cards / bars** | Single-flat-colour design felt monotone. Brushed-metal feel established. |

If the user asks for something that contradicts one of these, ask before
flipping it — they may have changed their mind, or you may have misread.

---

## Things to NOT do

- Don't use `customtkinter`. The codebase is PySide6-only despite what
  `requirements.txt` says (the file is stale; bumping it is on the to-do).
- Don't read game memory. Anti-cheat detection. Use OCR / CV.
- Don't use `SendInput` for mouse output. Use the Arduino HID path.
- Don't bring back the dashboard `pages/main_page.py` — it was deleted on
  purpose; the compact panel replaces it.
- Don't push to `main` without the user's explicit go-ahead. (User has
  been giving it explicitly each time so far.)
- Remote is SSH (`git@github.com:donliao-tw/red_team.git`). HTTPS won't
  push without a token; don't switch back.

---

## Local environment notes

- User develops on **Linux X11** (XDG_SESSION_TYPE=x11). Frameless window
  works fine. Wayland might behave differently — untested.
- A working `.venv/` is set up in the repo root with `PySide6 + pyserial`
  installed. `.venv/` is gitignored. Use `.venv/bin/python` for scripts /
  smoke tests, or just `./run.sh` to launch.
- Arduino flashing path requires `tools/arduino-cli.exe` (Windows). The
  Linux flash flow has not been wired (would need a Linux arduino-cli
  binary plus path tweaks in `flasher/flash.py:16`). Defer until needed.
- `tools/arduino-cli.yaml` still has Windows absolute paths from the
  initial bootstrap. Ignore unless someone needs to flash on Linux.

---

## Smoke test recipe

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
import sys; sys.path.insert(0, 'flasher')
from PySide6 import QtWidgets, QtGui
import style
app = QtWidgets.QApplication(sys.argv)
style.load_bundled_fonts(); style.ensure_icons()
app.setStyleSheet(style.make_qss())
app.setFont(QtGui.QFont(style.FAMILY_UI, 10 + style.FONT_DELTA))
from main import MainWindow
w = MainWindow(); w.show(); app.processEvents()
w.grab().save('/tmp/preview.png', 'PNG')
print('OK')
"
```

This catches import-time errors and lets you eyeball the layout via
`/tmp/preview.png`. Use it before claiming a UI change works — the user
can't see your tool calls, only the final preview.

---

## Field wiring — canonical to-do

The UI is the final shape. Almost every field is currently cosmetic and
needs to be wired to real behaviour. Owner is the user; this list is
maintained here so any session can pick up where the last left off.
**Update this table as items get done.**

| Component | State | What's needed |
|---|---|---|
| 🔓 解除鎖定 (login row) | no-op | License / panel-lock state machine |
| ⚙ 技能設定 shortcut (login row) | done | — |
| Login dropdown | hard-coded one entry | Populate from saved accounts; persist selection |
| ↻ refresh (login row) | no-op | Re-detect connected accounts / re-validate license |
| `騎士.ini` combo + 讀取/儲存/新增 | dummy items, no I/O | Hit a real json/ini load/save layer; `新增` clones from template |
| HP / MP bars | static numbers | Hook to HP/MP-zone OCR (NOT memory reading) |
| 🛡️ / 🤖 / 🧘 toggles | toggle state only | Actually start/stop the corresponding bot loops |
| 機器人設定 → 保護設定 tab | placeholder card | Port `保護功能` content from 技能設定 (回捲熱鍵 / HP / MP 護身) |
| 機器人設定 → 娃娃設定 tab | placeholder card | New fields: 自動補血/補魔範圍, 跟團優先順序, etc. |
| 機器人設定 → 自動設定 tab | full UI, no I/O | Persist values via the ini layer; emit to bot runtime |
| Stats card 📖 / 💰 / ⏱ | static `0.0000% / 0` | Real exp/gold/time tracker, refreshed at ~1 Hz |
| ↻ reset (stats card) | no-op | Zero counters + restart `time.monotonic()` |
| Console log | hard-coded sample lines | Wire to a real event stream from the bot runtime |
| 🪪 驗證資訊 | static popup | Show actual license server response (expiry, plan) |
| 🕵️ OCR 設定 | jumps to env tab | The env tab itself still needs OCR model picker + capture-zone tool |
| 置頂 checkbox | done | — |
| Settings persistence layer | not started | One json/ini file; uses `Page.serialize() / apply()` already in base class |

Open questions to resolve with the user before / during this phase:
- One single config file vs per-page files?
- OCR engine choice (Tesseract / PaddleOCR / cloud)?
- How is the bot runtime (the loop that consumes settings) going to live —
  same process, subprocess, or separate?
