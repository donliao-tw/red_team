# SOP-001 — Arduino Flash & VID/PID Spoof

**Status:** in development
**Owner:** donliao
**Last updated:** 2026-04-25

## Goal

One-click GUI flow that takes any Pro Micro / Leonardo class Arduino (ATmega32U4) and flashes it with our HID Absolute Mouse firmware while injecting a chosen vendor's USB VID / PID at compile time. The judge's detection software, which runs on the same machine as the game, must see a vanilla Logitech / Razer / Microsoft mouse — not "Arduino LLC".

The procedure must be repeatable for any new board the user plugs in: detect → pick profile → click flash → done.

## Why this architecture

| Decision | Reason |
|---|---|
| **External Arduino over `SendInput` / driver injection** | Judge can hook Raw Input and trivially distinguish synthetic events from real HID reports. A real USB HID device produces real reports — indistinguishable at OS level. |
| **VID/PID spoof at compile time, not runtime** | The USB descriptor is set in the bootloader-handoff handshake. It cannot be changed without a re-flash. Doing it at compile time means one firmware = one identity. |
| **`HID-Project` library's `AbsoluteMouse`** | Default `Mouse.move()` is *relative* and is mangled by Windows mouse acceleration — destroys click precision. Absolute Mouse uses HID Digitizer descriptor and lets us send `(x, y)` directly. Critical for RPG accuracy. |
| **Portable `arduino-cli` instead of Arduino IDE** | Scriptable, no GUI, all data lives under `tools/` so the project folder is movable. No admin install required. |
| **Build properties to override VID/PID/strings** | `arduino-cli compile --build-property "build.vid=0x046D" ...` injects `-DUSB_VID=0x046D` to the compiler. No need to mutate `boards.txt`. |

## Pipeline

```
[GUI: 機器人設定]
  │
  ├─ 偵測 ──→ pyserial.tools.list_ports + WMI VID/PID query → 顯示 COM 埠 + 目前 VID:PID
  │
  ├─ 選 profile ──→ profiles.py: Logitech G502 / Razer DeathAdder / Stock / 自訂
  │
  ├─ 編譯 ──→ arduino-cli compile \
  │              --fqbn arduino:avr:leonardo \
  │              --build-property "build.vid=0x{vid}" \
  │              --build-property "build.pid=0x{pid}" \
  │              --build-property "build.usb_product=\"{product}\"" \
  │              --build-property "build.usb_manufacturer=\"{manufacturer}\"" \
  │              firmware/hid_mouse
  │
  ├─ 軟重置 ──→ open serial @ 1200bps → close (進 bootloader)
  │
  └─ 燒錄 ──→ arduino-cli upload --fqbn arduino:avr:leonardo --port {COM}
```

## Steps to reproduce

### 1. One-time environment setup

Already done in this repo, but if starting from scratch:

```powershell
# Download arduino-cli portable
Invoke-WebRequest `
  -Uri 'https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip' `
  -OutFile 'tools/arduino-cli.zip'
Expand-Archive tools/arduino-cli.zip tools/

# Use portable data dirs (see tools/arduino-cli.yaml)
.\tools\arduino-cli.exe --config-file tools\arduino-cli.yaml core update-index
.\tools\arduino-cli.exe --config-file tools\arduino-cli.yaml core install arduino:avr
.\tools\arduino-cli.exe --config-file tools\arduino-cli.yaml lib install "HID-Project"
```

### 2. Plug in board, detect

GUI → 機器人設定 → board dropdown auto-populates from `pyserial.tools.list_ports.comports()`.

A Pro Micro in normal (non-bootloader) mode shows VID `2341` PID `8037`; in bootloader mode the PID flips (e.g. `0036`). Both must be supported by the detector.

### 3. Pick profile

Profiles live in `flasher/profiles.py`. Start with:

| Profile | VID | PID | USB Product | USB Manufacturer |
|---|---|---|---|---|
| Stock (Pro Micro) | 0x2341 | 0x8037 | "Pro Micro" | "Arduino LLC" |
| Logitech G502 HERO | 0x046D | 0xC08B | "G502 HERO Gaming Mouse" | "Logitech" |
| Razer DeathAdder V2 | 0x1532 | 0x0084 | "Razer DeathAdder V2" | "Razer" |
| Custom | user-entered | user-entered | user-entered | user-entered |

### 4. Flash

GUI calls into `flasher/flash.py:flash()`:

1. Run `arduino-cli compile` with build-property overrides → produces `.hex`.
2. Soft-reset board: open `COM<n>` at 1200 baud, close after 50ms. Pro Micro re-enumerates as bootloader.
3. Wait up to 5s for the new COM port (bootloader has a different one).
4. Run `arduino-cli upload --port <bootloader-com>`.
5. Wait for board to re-enumerate as the new VID/PID. Update GUI status.

### 5. Verify

```powershell
Get-PnpDevice -PresentOnly | Where-Object FriendlyName -match "USB 序列|HID-compliant" |
  Select-Object FriendlyName, InstanceId
```

The `InstanceId` should now show the spoofed VID (e.g. `VID_046D`).

Optional smoke test: in GUI, click "測試移動" — cursor should jump to centre of screen and back.

## Known gotchas

- **Bootloader window is short.** Pro Micro bootloader sits for ~8 seconds after soft-reset, then auto-jumps back to user firmware. If the upload takes longer than that, it will fail. Keep `--upload-port` discovery fast.
- **VID/PID change requires reboot of game machine on Windows occasionally.** Windows caches HID device class info; sometimes the new VID isn't recognized until USB stack is reset (unplug → replug usually enough).
- **`AbsoluteMouse.moveTo(x, y)` uses 0–32767 range,** not pixel coordinates. We must scale: `hid_x = (pixel_x / screen_w) * 32767`.
- **`build.usb_manufacturer` requires escaped quotes** on Windows because of cmd argument parsing. The Python wrapper handles this with `subprocess` list-form args.
- **Board "bricks".** If you flash a firmware that crashes immediately, the board never enumerates. Recovery: short the `RST` pin to GND twice within ~1s to force the bootloader.

## Files

- [firmware/hid_mouse/hid_mouse.ino](../firmware/hid_mouse/hid_mouse.ino) — the firmware
- [flasher/profiles.py](../flasher/profiles.py) — VID/PID database
- [flasher/board.py](../flasher/board.py) — board detection & soft-reset
- [flasher/flash.py](../flasher/flash.py) — compile + upload pipeline
- [flasher/pages/environment_settings.py](../flasher/pages/environment_settings.py) — GUI page (環境設定)
- [tools/arduino-cli.yaml](../tools/arduino-cli.yaml) — portable arduino-cli config
