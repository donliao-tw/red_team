# Development Log

Chronological notes — what was done, what was decided, what was deferred.
Newest entries on top.

---

## 2026-04-30 (evening) — OCR pipeline + monitor wired into main panel

### What got done

Real game-state values now flow into the main panel widgets via a
read-only capture / OCR pipeline. **No game-process touch** anywhere in
the chain — Win32 ``EnumWindows`` for discovery, Windows.Graphics.Capture
(WGC) for the framebuffer, RapidOCR (ONNX-Runtime) for text, NumPy for
pixel masks. Anti-cheat-safe per CLAUDE.md.

#### New module: [flasher/capture.py](../flasher/capture.py)

- ``find_game_window(needle)`` — substring match via EnumWindows.
- ``grab_frame(needle)`` — one-shot WGC capture (~275 ms, used by the
  preview tool).
- ``FrameStreamer`` — persistent WGC session that pushes the latest
  frame into a thread-safe slot. Uses ``start_free_threaded()``,
  throttles PIL conversion to 10 Hz so we don't burn 480 MB/s memcpy
  at 60 Hz vsync. Reading ``latest()`` is sub-millisecond.
- ``hp_fill_ratio()`` / ``mp_fill_ratio()`` — per-bar pixel masks.
  HP mask: ``R > 80 ∧ R > 3·G ∧ R > 3·B``. Initial mask was ``R > 130``
  (too strict, missed deep red R≈125, fooled by gold trim). Y range
  also shifted from 815-833 to 824-840 so we sample pure red rows
  rather than the peach trim above.
- ``ocr_rois(img, rois)`` with per-ROI ``NO_UPSCALE_ROIS`` set — the
  orange ribbon (level / EXP) loses contrast under bicubic upscale,
  so OCR'd at native size. Other ROIs use 2× upscale to clear
  RapidOCR's detection floor.
- ``parse_hpmp()`` / ``parse_level_exp()`` — slash gets misread as
  '1', so "308/308" comes back as ['308','1308']. Strip the leading
  '1' when its length is len(cur)+1. EXP comes back split: ['79',
  '1664%'] → reconstruct as '79.1664%'.
- ``GameMonitor`` — two-rate poller:
  - **Fast loop (200 ms / 5 Hz)**: pixel-mask HP/MP, emit ``hp_changed``
    / ``mp_changed`` with ``round(max × ratio)``.
  - **Slow loop (2000 ms target)**: OCR every ROI, refresh max values,
    emit LV / EXP / Lawful. In practice the OCR pass takes ~10 s so
    polls run back-to-back.
  - Signals: hp/mp/level/exp/lawful/account/connection/window_size_wrong
    /poll_started/poll_finished.

#### Window-size enforcement

- ``EXPECTED_CLIENT_SIZE = (1280, 960)`` — anything else means the
  calibrated pixel positions are off, so OCR / pixel-mask read garbage.
- ``_try_attach`` checks ``GetClientRect`` and either swaps to the
  matching ROI / pixel-mask preset or emits ``window_size_wrong`` and
  refuses to start polling.
- Two ROI presets exist: ``ROI_1280x960`` (target) and ``ROI_1920x1032``
  (for the maximised state we calibrated against earlier).
- HP/MP pixel-mask boxes also have 1280 / 1920 variants
  (``HP_BAR_BOX_1280`` etc.).

#### Main-panel integration

- ``_wire_game_monitor()`` instantiates ``GameMonitor`` 150 ms after
  window paint, connects all signals to widget update slots.
- HP / MP bars show the pixel-mask reading at 5 Hz, then the exact
  OCR'd value when the slow OCR completes.
- New ``LV / EXP`` badge row above the HP bar — gold ``28``, light-blue
  ``79.1664%``. Defaults to ``—``; values land when slow OCR returns.
- Login dropdown auto-populates from the game window title (regex
  ``Login\s*\[([^\]]+)\]``); placeholder ``（等待偵測…）`` until then.
- Console log no longer carries hard-coded sample lines. ``SAMPLE_LOG``
  is empty — only real events (connection up / down) are appended.
- All initial widget values default to **``?``** instead of fake numbers
  (``1850 / 2000`` etc.) so it's visually obvious when no real reading
  has landed.
- ``LoadingOverlay`` — half-opacity black veil with ⧗ icon and
  ``讀取中…`` message, shown during the ~12 s startup window where the
  OCR model is loading + first capture is in flight. Dismissed on first
  ``poll_finished``. Doubles as the size-mismatch warning surface
  (``⚠ 遊戲視窗大小 1920×1032 / 請調整為 1280×960``).
- Window position pinned **left edge** (x = 20, y = vertical centre)
  rather than centred — game lives to the right.

#### Bug fixed: onnxruntime + Qt event loop deadlock

First-time RapidOCR initialisation **hangs forever** when invoked from
a daemon thread spawned under ``QApplication.exec()``. Reproduced
deterministically:

- Standalone script ``cap.ocr_rois(img)`` runs in 11 s. ✓
- Same call inside a ``threading.Thread`` started after
  ``QApplication.processEvents()`` runs — never returns.
- Pre-loading ``cap._get_ocr()`` on the main thread, then spawning the
  worker — runs to completion in 10 s. ✓

Fix: ``GameMonitor.start()`` calls ``_get_ocr()`` synchronously on the
main thread before any timer / worker fires. Costs ~800 ms one-shot at
launch.

#### Standalone debug tool: [flasher/capture_preview.py](../flasher/capture_preview.py)

A QDialog showing the latest captured frame with ROI overlays + OCR
readouts on the side. Use for ROI calibration. Auto-refresh toggle,
manual single-shot, opt-in OCR. Capture work runs on a worker thread,
results pushed back to the GUI via Qt signals so the dialog never
freezes.

### Known broken / pending — debug tonight

| Item | Status |
|---|---|
| **`ROI_1280x960` not yet calibrated** | Currently **derived** from the 1920×1032 boxes by simple bottom-/right-anchor translation. Lineage UI doesn't scale linearly between resolutions, so OCR returns nothing → all values stay ``?`` at 1280×960. **Need a real 1280×960 capture to fix coords.** |
| **`HP_BAR_BOX_1280` / `MP_BAR_BOX_1280` not yet calibrated** | Same problem. Pixel mask currently misses, HP bar stays empty. |
| OCR slow-pass latency | ~10 s/round (RapidOCR × 6 ROIs). Tolerable but could be parallelised. |
| Re-attach when game closes / restarts | Not handled — streamer dies silently if window is closed. |
| EXP rate / Gold rate / Time stopwatch | Stat-card rows still show ``?`` — need a tracker that diffs samples over time. |

### Next session

1. Capture a real 1280×960 frame (`samples/full_1280.png`).
2. Recalibrate `ROI_1280x960` and `HP_BAR_BOX_1280` / `MP_BAR_BOX_1280`
   against it. Confirm via `capture_preview.py`.
3. Verify pixel-mask responsiveness on partial HP at 1280×960.
4. Then: re-attach handler + stat trackers.

---

## 2026-04-30 — Main-panel UI redesign complete; next phase = field wiring

### What got done

The original sidebar+pages window became the **settings dialog**; a brand-new
compact runtime panel ([flasher/main.py](../flasher/main.py)) is now the main
window. Loosely modelled on Fa10TM3As — narrow, dense, dark, frameless.

#### Layout (top → bottom)
- **Title bar (custom dark)** — `RED TEAM` mono label, drag-to-move, double-click
  maximize, –/□/✕ controls (close hovers red). Replaces the OS title bar that
  used to clash with the dark body.
- **Login row** — `🔓 解除鎖定` icon button + `⚙` shortcut to 技能設定 + login
  dropdown + `↻` refresh. All icon-only with tooltips.
- **Config row** — `騎士.ini` combo + 讀取/儲存/新增.
- **HP / MP bars** — red HP, blue MP, glossy gradient fill.
- **Three function toggles + shared gear** — 🛡️ / 🤖 / 🧘, icon-only with hover
  tooltips. Single shared `⚙` opens 機器人設定 at the inner tab matching the
  most-recently-toggled feature.
  - 保護 starts checked by default and is **independent** (can stay on while
    others toggle).
  - 機器人 ↔ 娃娃 are **mutually exclusive** and **share active colour**
    (changing one updates the other; 保護 keeps its own colour).
  - **Right-click any toggle → `QColorDialog`** to pick a custom active colour.
- **Stats card** — three rows: 📖 EXP (light blue), 💰 gold (warm gold), ⏱
  time (light brown). Each row is icon + primary value + per-hour rate
  (right-aligned, dimmer). `↻` reset tucked into the bottom-right corner of
  the card; tooltip explains the upgrade/death reset reason. Numbers are Inter
  semibold (was Cascadia Mono bold — felt too chunky).
- **Console log** — green-on-black mono, with a `▾`/`▴` chevron above to
  collapse to ~5 lines (window auto-resizes to 580 px when collapsed,
  back to 800 px when expanded).
- **Footer** — 置頂 checkbox / 🪪 驗證資訊 / 🕵️ OCR 設定 / `Ver: 0.1.0`.

#### Settings dialog ([flasher/settings_dialog.py](../flasher/settings_dialog.py))
- `QDialog` wrapping the same sidebar + page stack the old MainWindow used.
  Sidebar entries: 機器人 / 技能 / 硬體 / 環境 (主畫面 dropped — that was the
  old dashboard, now replaced by the compact panel).
- Pages keep calling `self.app.set_status / set_font_size / set_theme /
  switch_page`; the dialog forwards those to the parent MainWindow so theme
  changes still propagate globally.

#### 機器人設定 page restructure ([flasher/pages/bot_settings.py](../flasher/pages/bot_settings.py))
- Inner `QTabWidget` with three tabs: **保護設定 / 自動設定 / 娃娃設定**.
- 自動設定 holds the original full bot_settings content (戰鬥模式 / 通用 /
  被包圍動作 / 武器與安全 / 拾取/殺怪 / 黑名單).
- 保護設定 + 娃娃設定 are placeholder cards for now — the icons in the main
  panel route here but the actual fields haven't been built.

#### Visual polish — metallic / 3D feel
- All buttons (funcMain, funcGear, secondary, iconBtn) use vertical
  qlineargradient with a lighter top edge + darker bottom for a polished
  metal look. `:pressed` flips the gradient to feel pushed in.
- Custom colours picked via right-click also gradient-ize: `_apply_checked_color`
  computes top/mid/bottom shades via `QColor.lighter()` / `.darker()`.
- HP / MP chunks have a 3-stop glossy gradient (looks like liquid in a tube).
- Stats card has a faint top-down sheen with subtle 1 px highlight on top
  edge, shadow on bottom.

### Files touched
- Rewrote [main.py](../flasher/main.py) (compact panel + TitleBar +
  FunctionButton with right-click colour picker).
- New [settings_dialog.py](../flasher/settings_dialog.py).
- Heavy QSS work in [style.py](../flasher/style.py) (gradients, title bar,
  func buttons, progress bar chunks, inner tabs, footer icons, reset button,
  stats labels).
- [bot_settings.py](../flasher/pages/bot_settings.py) restructured into three
  inner tabs.
- Deleted [pages/main_page.py](../flasher/pages/) (orphaned dashboard).
- Added [README.md](../README.md) and [run.sh](../run.sh) (Linux launcher).

### Verification
- Offscreen smoke test constructs every page (bot/skill/hardware/env) without
  errors.
- Mutual exclusion: 機器人 ↔ 娃娃 covered by assertions; 保護 stays
  independent. Most-recent activation order drives gear routing.
- Colour bind: 機器人 ↔ 娃娃 sync bidirectionally via `colorChanged` signal +
  same-value short-circuit; 保護 untouched.
- Log fold: max-height + window-height assertions both pass.
- Pushed to `origin/main` (`3d1de1c`). Switched remote from HTTPS to SSH so
  pushes work without a stored token.

### Next phase — field functionality (this is what's still placeholder)

The UI is essentially the final shape. Almost every field is currently
cosmetic and needs to be wired to real behaviour:

| Component | Current state | What it needs |
|---|---|---|
| `🔓 解除鎖定` | no-op icon button | license / panel-lock state machine |
| `⚙` next to unlock | works (jumps to 技能設定) | — |
| Login dropdown | hard-coded one entry | populate from saved accounts; selection persists |
| `↻` refresh (login) | no-op | re-detect connected accounts / re-validate license |
| `騎士.ini` combo + 讀取/儲存/新增 | dummy items, no I/O | hit a real json/ini load/save layer; `新增` should clone-from-template |
| HP / MP bars | static `1850/2000`, `320/500` | hook to game-memory reader or HP/MP-zone OCR |
| 🛡️ / 🤖 / 🧘 toggles | toggle state only | actually start/stop the corresponding bot loops |
| 機器人設定 → 保護設定 tab | placeholder card | port `保護功能` from 技能設定 (回捲熱鍵 / HP / MP 護身) |
| 機器人設定 → 娃娃設定 tab | placeholder card | new fields: 自動補血/補魔範圍, 跟團優先順序, etc. |
| 機器人設定 → 自動設定 tab | full UI, no I/O | persist values via the ini layer; emit to bot runtime |
| Stats card 📖 / 💰 / ⏱ | static `0.0000% / 0` | real exp/gold/time tracker, refreshed at ~1 Hz |
| `↻` reset (stats card) | no-op | zero counters + restart `time.monotonic()` |
| Console log | hard-coded sample lines | wire to a real event stream from the bot runtime |
| `🪪 驗證資訊` | static popup | show actual license server response (expiry, plan, etc.) |
| `🕵️ OCR 設定` | jumps to 環境設定 tab | the env tab itself still needs OCR model picker + capture-zone tool |
| 置頂 | works (Qt window flag) | — |

Settings persistence layer hasn't been written. Once that exists, every
field that has a `cfg` entry in the page can be auto-saved/loaded — the
`Page.serialize()` / `Page.apply()` plumbing is already in place.

### Decisions worth recording
- `tools/arduino-cli.yaml` still has Windows absolute paths from the original
  bootstrap. Linux GUI work doesn't need it (flash flow won't run here);
  defer fixing the YAML until someone needs to flash on Linux.
- `requirements.txt` is stale (lists `customtkinter`); the codebase is
  PySide6 + pyserial only. Bump when convenient.

---

## 2026-04-25 — Project bootstrap & SOP-001 begins

### Architecture decisions
- Confirmed external CV + Arduino HID approach for the human-like AI competition (see [project memory](../C:\Users\donli\.claude\projects\c--Users-donli-workspace-red-team\memory\project_human_like_ai_competition.md)).
- Target game genre: **RPG**. Latency tolerant, accuracy critical → emphasis on absolute mouse positioning, not reaction speed.
- Dropped initial HDMI capture / two-machine plan as over-engineered for the first iteration. Will start with single-machine DXGI Desktop Duplication; revisit if the judge's detector turns out to hook capture APIs.

### GUI shell
- Built CustomTkinter sidebar shell with three pages: 機器人設定 / 技能設定 / 環境設定.
- Iterated on look & feel: settled on **Microsoft JhengHei** (UI font), **Cascadia Mono** (logo / monospace), and a 3-tier text colour palette (`TEXT_PRIMARY` / `SECONDARY` / `TERTIARY`) with proper light/dark tuples — single greys washed out on one of the modes.
- Lazy-loaded pages (only the active page is constructed at startup) and centred-on-screen with `withdraw → geometry → deiconify` to remove startup flash.

### Arduino baseline
- Detected user's plugged-in Arduino: COM3, VID `2341` PID `8037`, ATmega32U4 (Pro Micro / Leonardo class). Already enumerates as HID mouse — has some prior sketch on it, will be overwritten by SOP-001.
- **VID `2341` = "Arduino LLC"** — flagged as the giveaway any savvy judge software will check first. SOP-001's spoofing step is the fix.

### Toolchain
- arduino-cli 1.4.1 portable installed under `tools/arduino-cli.exe`.
- Configured `tools/arduino-cli.yaml` with portable data dirs (`tools/arduino15/`, `tools/arduino-user/`) so the project folder stays self-contained.
- Hit a snag: empty `network.proxy: ""` in YAML caused arduino-cli to try to dial proxy `:0`. Removed the key entirely → works.
- AVR core install (~150MB) running in background.

### SOP-001 implementation
- Wrote firmware [firmware/hid_mouse/hid_mouse.ino](../firmware/hid_mouse/hid_mouse.ino) — HID-Project AbsoluteMouse + line-based serial protocol (`M x y` / `C` / `R` / `D` / `U` / `P` / `V`). Each cmd responds `ok` / `err <reason>` / `pong` etc., so the GUI's Ping button can verify the board is alive.
- Wrote [flasher/profiles.py](../flasher/profiles.py) — VID/PID database. Six entries to start: Stock Pro Micro, Logitech G502 / G Pro, Razer DeathAdder V2 / Basilisk V2, Microsoft Basic. Default = Logitech G502.
- Wrote [flasher/board.py](../flasher/board.py) — `list_serial_ports()`, `soft_reset()` (1200bps DTR/RTS-low touch), `wait_for_bootloader()` (poll for new COM port post-reset).
- Wrote [flasher/flash.py](../flasher/flash.py) — `compile_sketch(profile)` injects `--build-property build.vid/pid/usb_product/usb_manufacturer`. `flash_with_reset()` orchestrates compile → reset → wait → upload.
- Wrote [flasher/pages/bot_settings.py](../flasher/pages/bot_settings.py) — full UI: board dropdown, profile dropdown with VID/PID detail, four action buttons (編譯+燒錄 / 僅編譯 / 軟重置 / Ping), live log textbox. Background ops run on a `threading.Thread`, log lines are pushed to a `queue.Queue` and drained by `after()` polling — keeps the GUI responsive during the ~10s arduino-cli run.

### Verification checkpoints
- [✓] arduino-cli compile of hid_mouse with Logitech profile succeeds (exit 0).
- [✓] ELF binary contains literal strings `Logitech` and `G502` — confirms `--build-property` is being honoured.
- [ ] First real flash to the board (deferred until user is ready — could brick the existing sketch).
- [ ] Post-flash Windows Device Manager shows VID `046D` PID `C08B` instead of `2341:8037`.
- [ ] Post-flash Ping responds with `pong`.

### Known issues / deferred
- arduino-cli stdout has CP950-encoded summary lines (size info) that decode as garbage when forced through utf-8. Cosmetic only — real errors come through fine. Fix later if it bothers anyone.
- No "Cancel" / abort for an in-progress compile — would require killing the subprocess. Acceptable for now since the worst case is ~30s wait.
- No firmware version probing yet (`V` cmd works at runtime, but the GUI doesn't query it on connect). Add when useful.

### 機器人設定 / 技能設定 — 3-column layout
- User feedback: avoid scroll when window is at a reasonable size; only scroll when shrunk.
- Both pages now use a 3-column grid layout inside their `CTkScrollableFrame`. Each column is its own transparent frame that stacks cards via pack — gives clean independent column flow.
- 機器人設定 distribution:
  - Col A: 戰鬥模式 + 通用設定
  - Col B: 被包圍動作 + 武器與安全 + 拾取/殺怪
  - Col C: 黑名單 (full-height, expand=True so the textareas grow with the column)
- 技能設定 distribution:
  - Col A: 保護功能
  - Col B: 自動 Buff
  - Col C: 自定計時 + 主動技能
- Bumped default window size 1200×760 → **1400×820** and min 900×600 → **1100×680**. At default each column is ~340 px wide; min size still gives ~245 px which is enough for the longest labels.
- Replaced the per-page `_make_grid_card` helper in skill_settings.py with the shared `make_card` from `_base.py` — one card primitive everywhere now.

### 機器人設定 / 技能設定 — visual replication of reference UIs
- User provided two reference screenshots from an existing MMORPG bot config tool. Asked to copy the field set, design the layout myself.
- Extracted shared building blocks into [flasher/widgets.py](../flasher/widgets.py) — `hotkey_menu` (with paged P1–P3 + F1–F12 = 48 options), `num_entry`, `checkbox`, `radio`, `option_menu`, `textarea`, `percent_slider`, `hint`. Pages now keep their config state in `self.cfg: dict[str, Var]` for future load/save.
- Lifted `make_card()` from environment_settings.py into [_base.py](../flasher/pages/_base.py) so all pages share the card style (env_settings.py keeps its own copy for now — refactor TODO).
- [bot_settings.py](../flasher/pages/bot_settings.py) — full single-column layout in a CTkScrollableFrame: 戰鬥模式 / 通用設定 (8 mixed rows) / 被包圍動作 (3 hotkey rows) / 武器與安全 / 拾取-殺怪 / 黑名單 (4 textareas with sensible defaults) / footer hint.
- [skill_settings.py](../flasher/pages/skill_settings.py) — 保護功能 card on top (full width, sliders for HP/MP %), then a 3-column section for 自動施放 Buff (13 items) / 自定計時 (#1–#6 with 秒數) / 主動技能 (9 items, 使用力盾 has 原頭盔熱鍵 sub-field). Defaults match the reference screenshot's pre-checked items.
- Defaults preserved verbatim: 怪物黑名單 default list, 拾取黑名單 default list, all hotkey assignments, all percentage thresholds. The reference UI is the source of truth.

### Bug: first flash uploaded wrong firmware
- After clicking 編譯並燒錄 with Logitech G502 profile, the board still enumerated as `VID_2341 PID_8037` after a replug. So Windows cache wasn't to blame — the firmware actually flashed had Arduino LLC VID/PID baked in.
- Verified the COMPILE step was correct: ELF in `firmware/hid_mouse/build/` contained `Logitech` / `G502` strings AND the bytes `6D 04` / `8B C0` (LE-encoded VID/PID). Compile good.
- So the UPLOAD step didn't actually use that hex. Suspect: `arduino-cli upload --input-dir <dir>` in v1.4.1 silently re-compiled from sketch source (losing our `--build-property` overrides) instead of uploading the pre-built binaries in that dir.
- **Fix #1:** switched [flasher/flash.py](../flasher/flash.py) `upload()` to `--input-file <explicit-path-to-.ino.hex>` and added `--verbose` so avrdude output is visible in the log. Pre-flight check: function fails fast if the hex doesn't exist.
- **Fix #2:** after applying #1, second flash failed with avrdude `butterfly_recv(pgm, &c, 1) failed` (3 retries, ~10s, all timing out). Root cause: we were *double-resetting* the board. arduino-cli's avr `platform.txt` sets `use_1200bps_touch=true` so the upload command does its own 1200bps trigger + bootloader-port discovery. Our Python `soft_reset()` + `wait_for_bootloader()` ran *first*, putting the board in bootloader, then arduino-cli's touch ran on a port whose state had already shifted, the bootloader window expired before avrdude got there, hence the butterfly_recv timeouts. Removed the manual reset from `flash_with_reset()` — arduino-cli handles the whole timing-sensitive dance. The 軟重置 button stays for manual recovery.

### Reorganisation: Arduino UI moved 機器人設定 → 環境設定
- Initial misplacement — Arduino flashing is hardware/toolchain setup, conceptually 環境設定. User flagged it; moved.
- 機器人設定 reset to placeholder; will hold *bot behaviour* settings later (mouse curves, reaction-time jitter, plausible mistakes).
- Switched section layout from grid-based to **pack-based** stacking. Old grid had cards above the log getting compressed when window narrowed; pack respects each card's natural height and only the log expands.
- Action buttons rearranged from 1×4 to **2×2** so labels stay readable at small widths.

### Next
- User to run `run.bat`, navigate to **環境設定**, click 「僅編譯」 first, then 「編譯並燒錄」 with the board plugged in.
- After successful flash: verify VID/PID in Device Manager, run Ping test from GUI.
- Then move on to SOP-002 (likely: Python-side serial client + smoke-test moves).
