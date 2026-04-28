"""Board detection and Pro Micro / Leonardo bootloader handling."""
from __future__ import annotations

import time
from dataclasses import dataclass

import serial
import serial.tools.list_ports as list_ports


# ATmega32U4 boards we know how to flash. (vid, pid) — both runtime and
# bootloader entries; bootloader PIDs are listed so detection works in
# both states.
KNOWN_BOARDS = {
    (0x2341, 0x8036): ("Arduino Leonardo", "leonardo"),
    (0x2341, 0x0036): ("Arduino Leonardo (bootloader)", "leonardo"),
    (0x2341, 0x8037): ("Arduino Pro Micro", "leonardo"),
    (0x2341, 0x0037): ("Arduino Pro Micro (bootloader)", "leonardo"),
    (0x1B4F, 0x9205): ("SparkFun Pro Micro 5V", "leonardo"),
    (0x1B4F, 0x9206): ("SparkFun Pro Micro 5V (bootloader)", "leonardo"),
    (0x1B4F, 0x9203): ("SparkFun Pro Micro 3.3V", "leonardo"),
    (0x1B4F, 0x9204): ("SparkFun Pro Micro 3.3V (bootloader)", "leonardo"),
}


@dataclass
class BoardInfo:
    port: str
    description: str
    vid: int
    pid: int
    serial_number: str
    manufacturer: str

    @property
    def vid_pid(self) -> str:
        return f"{self.vid:04X}:{self.pid:04X}"

    @property
    def known(self) -> tuple[str, str] | None:
        return KNOWN_BOARDS.get((self.vid, self.pid))

    @property
    def is_bootloader(self) -> bool:
        match = self.known
        return bool(match and "bootloader" in match[0])

    @property
    def label(self) -> str:
        match = self.known
        product = match[0] if match else (self.description or "Unknown device")
        return f"{self.port} — {product} ({self.vid_pid})"


def list_serial_ports() -> list[BoardInfo]:
    boards: list[BoardInfo] = []
    for p in list_ports.comports():
        if p.vid is None or p.pid is None:
            continue
        boards.append(BoardInfo(
            port=p.device,
            description=p.description or "",
            vid=p.vid,
            pid=p.pid,
            serial_number=p.serial_number or "",
            manufacturer=p.manufacturer or "",
        ))
    return boards


def list_known_boards() -> list[BoardInfo]:
    return [b for b in list_serial_ports() if b.known is not None]


def soft_reset(port: str) -> None:
    """Trigger Pro Micro / Leonardo bootloader by opening then closing
    the serial port at 1200 baud — the standard auto-reset trick.
    """
    try:
        s = serial.Serial(port, baudrate=1200)
        try:
            s.dtr = False
            s.rts = False
        except Exception:
            pass
        time.sleep(0.05)
        s.close()
    except serial.SerialException:
        # Port may have already disappeared as the board reset — fine.
        pass
    time.sleep(0.5)


def wait_for_bootloader(
    *,
    known_before: set[str],
    timeout: float = 8.0,
    poll_interval: float = 0.2,
) -> str | None:
    """Poll for a *new* serial port that appeared after soft_reset().

    The Pro Micro bootloader enumerates as a different COM port than the
    application firmware. We watch for any newcomer, then sanity-check
    that it matches a known bootloader VID/PID.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        ports_now = list_serial_ports()
        for b in ports_now:
            if b.port not in known_before and b.is_bootloader:
                return b.port
        # Fallback: any new port at all (covers spoofed bootloader VIDs).
        for b in ports_now:
            if b.port not in known_before:
                return b.port
        time.sleep(poll_interval)
    return None
