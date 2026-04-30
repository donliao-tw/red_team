# Red Team Control Center

擬人化 AI 競賽用的外掛硬體控制平台 — 由一台外接 Arduino (ATmega32U4 / Pro Micro / Leonardo) 模擬成真實滑鼠，再搭配 PySide6 桌面 GUI 進行燒錄、設定與行為控制。

評審端的偵測軟體在 OS Raw Input 層只會看到一支「真的」USB HID 滑鼠，VID / PID 會在編譯時注入指定廠牌（Logitech / Razer / Microsoft …），無法用 `SendInput` 或驅動注入式作弊偵測辨識出來。

---

## 為什麼這樣設計

| 設計選擇 | 原因 |
|---|---|
| **外接 Arduino**，不用 `SendInput` | 評審可掛 Raw Input hook，輕易區分合成事件與真實 HID 報告。USB HID 裝置產生的是真實報告，OS 層無法分辨。 |
| **VID/PID 編譯時注入**，不在執行時偽造 | USB descriptor 是 bootloader 交握時設定的，無法在執行時改。編譯期注入＝一份韌體一個身分。 |
| **HID-Project `AbsoluteMouse`** | 預設 `Mouse.move()` 是相對位移、會被 Windows 滑鼠加速度毀掉精準度。Absolute Mouse 走 HID Digitizer descriptor，可以直接送 `(x, y)`，對 RPG 點擊精度至關重要。 |
| **可攜式 `arduino-cli`** | 可腳本化、無 GUI、所有資料夾在 `tools/` 之下，整個專案目錄可隨身攜帶，不需要管理員權限。 |
| **Build properties 覆寫 VID/PID/字串** | `arduino-cli compile --build-property "build.vid=0x046D" ...` 直接注入 `-DUSB_VID=0x046D` 給編譯器，不用動 `boards.txt`。 |

---

## 專案結構

```
red_team/
├── firmware/
│   └── hid_mouse/
│       └── hid_mouse.ino        # HID Absolute Mouse 韌體 + 序列協定
├── flasher/
│   ├── main.py                  # PySide6 程式入口
│   ├── board.py                 # COM 偵測 / 1200bps soft-reset / bootloader 等待
│   ├── flash.py                 # arduino-cli 編譯 + 上傳流程
│   ├── profiles.py              # VID/PID 廠牌資料庫
│   ├── style.py                 # QSS、字型、配色
│   ├── widgets.py               # 共用元件 (hotkey_menu / num_entry / textarea …)
│   ├── pages/
│   │   ├── _base.py             # 共用 make_card 等基底
│   │   ├── main_page.py
│   │   ├── bot_settings.py      # 機器人設定（戰鬥模式、黑名單、拾取…）
│   │   ├── skill_settings.py    # 技能設定（保護、Buff、計時、主動）
│   │   ├── hardware_settings.py
│   │   └── environment_settings.py  # 環境設定（Arduino 燒錄 UI）
│   └── assets/                  # 圖示、Inter 字型
├── tools/
│   └── arduino-cli.yaml         # 可攜式 arduino-cli 設定（資料夾全部在 tools/）
├── docs/
│   ├── SOP-001-arduino-flash.md # 燒錄 SOP（含 pipeline 圖、地雷區）
│   └── dev-log.md               # 開發紀錄（時間倒序）
├── requirements.txt
└── run.bat                      # 啟動入口（Windows）
```

> 💡 `tools/arduino-cli.exe`、`tools/arduino15/`、`tools/arduino-user/`、`firmware/*/build/` 都在 `.gitignore` 中，第一次取下來後依下方步驟自行下載。

---

## 系統需求

- Windows 10 / 11（韌體燒錄與 1200bps touch reset 在其他 OS 上行為不同）
- Python 3.10+
- 一塊 ATmega32U4 開發板 — Arduino Pro Micro、Leonardo 或同類
- USB-A / USB-C 線（支援資料傳輸，不只是充電）

---

## 安裝

### 1. clone & 安裝 Python 相依

```powershell
git clone https://github.com/donliao-tw/red_team.git
cd red_team
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` 目前列出：

```
customtkinter>=5.2.2   # 早期版本，現以 PySide6 為主
pyserial>=3.5
requests>=2.32
```

> ⚠️ `flasher/main.py` 已改用 PySide6，啟動前請確認環境已安裝 `PySide6`。

### 2. 下載可攜式 arduino-cli

```powershell
Invoke-WebRequest `
  -Uri 'https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip' `
  -OutFile 'tools/arduino-cli.zip'
Expand-Archive tools/arduino-cli.zip tools/

.\tools\arduino-cli.exe --config-file tools\arduino-cli.yaml core update-index
.\tools\arduino-cli.exe --config-file tools\arduino-cli.yaml core install arduino:avr
.\tools\arduino-cli.exe --config-file tools\arduino-cli.yaml lib install "HID-Project"
```

完成後 `tools/` 下會多出 `arduino-cli.exe`、`arduino15/`（核心快取，~150 MB）、`arduino-user/`（函式庫）。

---

## 啟動

```bat
run.bat
```

或：

```bash
python flasher/main.py
```

開啟後左側分頁：

- 🏠 **主畫面** — 狀態總覽
- 🤖 **機器人設定** — 戰鬥模式、被包圍動作、武器/安全、拾取、黑名單
- ✨ **技能設定** — 保護功能、自動 Buff、自定計時、主動技能
- 🔌 **硬體設定** — 滑鼠/鍵盤行為（人性化抖動等待擴充）
- ⚙️ **環境設定** — Arduino 燒錄區（板子下拉、profile 選擇、編譯/燒錄/Ping）

---

## 使用流程：燒錄一塊新板子

詳見 [docs/SOP-001-arduino-flash.md](docs/SOP-001-arduino-flash.md)。摘要：

1. 把 Pro Micro 接上電腦，到「環境設定」頁。
2. 從下拉選單挑廠牌 profile（預設 Logitech G502 HERO）。
3. 先點「僅編譯」確認 ELF 含正確 VID/PID 字串。
4. 點「編譯並燒錄」 — arduino-cli 會自己做 1200bps touch + bootloader 探測 + avrdude upload，**不要在 Python 端再做一次 soft-reset**（會雙重重置導致 `butterfly_recv` timeout）。
5. 重新插拔後到 Windows 裝置管理員確認 VID 已變（例：從 `VID_2341` 變 `VID_046D`）。
6. 在 GUI 點 Ping，韌體應回 `pong`。

### 內建 Profile

| Profile | VID | PID | Manufacturer | Product |
|---|---|---|---|---|
| Stock (Pro Micro) | 0x2341 | 0x8037 | Arduino LLC | Pro Micro |
| **Logitech G502 HERO** *(預設)* | 0x046D | 0xC08B | Logitech | G502 HERO Gaming Mouse |
| Logitech G Pro Wireless | 0x046D | 0xC088 | Logitech | G Pro Wireless Gaming Mouse |
| Razer DeathAdder V2 | 0x1532 | 0x0084 | Razer | Razer DeathAdder V2 |
| Razer Basilisk V2 | 0x1532 | 0x0085 | Razer | Razer Basilisk V2 |
| Microsoft Basic Optical Mouse | 0x045E | 0x0040 | Microsoft | Microsoft Basic Optical Mouse |

要新增廠牌：在 [flasher/profiles.py](flasher/profiles.py) 的 `PROFILES` 列表追加 `Profile(...)`。

---

## 韌體序列協定

`firmware/hid_mouse/hid_mouse.ino` — 115200 baud，行尾 `\n`。

| 指令 | 說明 | 回覆 |
|---|---|---|
| `M x y` | 移動到絕對位置 (x, y)，`0 ≤ x,y ≤ 32767` | `ok` / `err parse_x` / `err parse_y` / `err range` |
| `C` | 左鍵 click | `ok` |
| `R` | 右鍵 click | `ok` |
| `D` | 左鍵 press（持續按住） | `ok` |
| `U` | 左鍵 release | `ok` |
| `P` | Ping | `pong` |
| `V` | 韌體版本 | `hid_mouse v0.1` |

**座標轉換：** `AbsoluteMouse.moveTo(x, y)` 用 0–32767 範圍，**不是像素**。Python 端要：
`hid_x = round(pixel_x / screen_w * 32767)`。

---

## 已知坑

- **Bootloader 視窗只有 ~8 秒。** Pro Micro soft-reset 後若 8 秒內 avrdude 還沒接上，板子會跳回 user firmware，下次得重來。
- **不要雙重重置。** arduino-cli 的 avr platform 已經內建 1200bps touch；Python 端再做一次會打亂 bootloader 計時。
- **Windows HID 裝置類別會被快取。** 換完 VID/PID 偶爾要拔插一次 USB 才會被新驅動辨識。
- **`build.usb_manufacturer` 含空格** — 在 cmd 上要用反斜線跳脫，Python 子程序用 list-form args 即可避開。
- **板子被「磚」** — 若燒到一段一啟動就 crash 的韌體，板子會不再 enumerate。把 RST pin 在 1 秒內對 GND 短路兩次強制進 bootloader 即可救回。

---

## 開發紀錄

最新進度與決策見 [docs/dev-log.md](docs/dev-log.md)（時間倒序）。

---

## License

尚未指定；Inter 字型來源見 [flasher/assets/fonts/LICENSE-Inter.txt](flasher/assets/fonts/LICENSE-Inter.txt)。
