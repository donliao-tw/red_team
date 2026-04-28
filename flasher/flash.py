"""Compile and upload pipeline wrapping arduino-cli.

All operations are synchronous — call from a background thread and pipe
log lines back to the GUI via ``on_log``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import board
from profiles import Profile

ROOT = Path(__file__).resolve().parent.parent
ARDUINO_CLI = ROOT / "tools" / "arduino-cli.exe"
ARDUINO_CONFIG = ROOT / "tools" / "arduino-cli.yaml"
SKETCH_DIR = ROOT / "firmware" / "hid_mouse"
BUILD_DIR = SKETCH_DIR / "build"
FQBN = "arduino:avr:leonardo"

LogFn = Callable[[str], None]


def _base_cmd() -> list[str]:
    return [str(ARDUINO_CLI), "--config-file", str(ARDUINO_CONFIG)]


def compile_sketch(profile: Profile, *, on_log: LogFn = print) -> bool:
    """Compile firmware/hid_mouse with VID/PID/strings from ``profile``.

    Returns True on success. Stream stdout+stderr through ``on_log`` so
    the GUI can show progress.
    """
    cmd = _base_cmd() + [
        "compile",
        "--fqbn", FQBN,
        "--build-property", f"build.vid=0x{profile.vid:04X}",
        "--build-property", f"build.pid=0x{profile.pid:04X}",
        "--build-property", f'build.usb_product="{profile.product}"',
        "--build-property", f'build.usb_manufacturer="{profile.manufacturer}"',
        "--build-path", str(BUILD_DIR),
        str(SKETCH_DIR),
    ]
    return _run_streaming(cmd, on_log)


def upload(port: str, *, on_log: LogFn = print) -> bool:
    """Upload the most-recently compiled binary to ``port``.

    Uses --input-file with an explicit path because arduino-cli 1.4.1's
    --input-dir was silently re-compiling the sketch from source on this
    machine (losing our --build-property VID/PID overrides).

    Caller is responsible for soft_reset() + wait_for_bootloader() if
    they want auto-bootloader handling; this just runs avrdude.
    """
    hex_file = BUILD_DIR / "hid_mouse.ino.hex"
    if not hex_file.exists():
        on_log(f"[失敗] 找不到編譯產物 {hex_file}")
        return False
    cmd = _base_cmd() + [
        "upload",
        "--fqbn", FQBN,
        "--port", port,
        "--input-file", str(hex_file),
        "--verbose",
    ]
    return _run_streaming(cmd, on_log)


def flash_with_reset(profile: Profile, current_port: str, *, on_log: LogFn = print) -> bool:
    """End-to-end: compile, then let arduino-cli handle 1200bps + upload.

    arduino-cli's avr platform.txt sets `use_1200bps_touch=true`, so the
    upload command itself triggers the bootloader and discovers the new
    COM port. Doing it manually in Python on top of that double-resets
    and misses the bootloader window — so we *don't* soft-reset here.
    The 軟重置 button still exists in the GUI for manual recovery.
    """
    on_log(f"== 編譯 (profile = {profile.name}, VID:PID = {profile.vid_pid}) ==")
    if not compile_sketch(profile, on_log=on_log):
        on_log("[失敗] 編譯錯誤")
        return False

    on_log(f"== 燒錄 → {current_port} (arduino-cli 自動處理 1200bps 觸發) ==")
    if not upload(current_port, on_log=on_log):
        on_log("[失敗] 上傳錯誤")
        return False

    on_log("[成功] 燒錄完成")
    return True


def _run_streaming(cmd: list[str], on_log: LogFn) -> bool:
    on_log("$ " + " ".join(_quote(c) for c in cmd))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        on_log(f"[失敗] 找不到執行檔: {e}")
        return False

    assert proc.stdout is not None
    for line in proc.stdout:
        on_log(line.rstrip())
    proc.wait()
    return proc.returncode == 0


def _quote(s: str) -> str:
    return f'"{s}"' if " " in s else s
