# Development Log

Chronological notes — what was done, what was decided, what was deferred.
Newest entries on top.

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
