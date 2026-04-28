"""USB device identity profiles for VID/PID spoofing.

Each profile is the set of values injected as compile-time `-D` flags by
arduino-cli. Add a profile by appending to PROFILES.

VID/PID values come from public USB-IF databases and the actual mice
themselves. A profile is "convincing" only if VID, PID, manufacturer
*and* product strings all match a real product the judge would expect.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    vid: int
    pid: int
    product: str
    manufacturer: str

    @property
    def vid_pid(self) -> str:
        return f"{self.vid:04X}:{self.pid:04X}"


PROFILES: dict[str, Profile] = {
    p.key: p
    for p in [
        Profile(
            key="stock_promicro",
            name="Stock (Pro Micro)",
            vid=0x2341,
            pid=0x8037,
            product="Pro Micro",
            manufacturer="Arduino LLC",
        ),
        Profile(
            key="logitech_g502",
            name="Logitech G502 HERO",
            vid=0x046D,
            pid=0xC08B,
            product="G502 HERO Gaming Mouse",
            manufacturer="Logitech",
        ),
        Profile(
            key="logitech_gpro",
            name="Logitech G Pro Wireless",
            vid=0x046D,
            pid=0xC088,
            product="G Pro Wireless Gaming Mouse",
            manufacturer="Logitech",
        ),
        Profile(
            key="razer_deathadder_v2",
            name="Razer DeathAdder V2",
            vid=0x1532,
            pid=0x0084,
            product="Razer DeathAdder V2",
            manufacturer="Razer",
        ),
        Profile(
            key="razer_basilisk_v2",
            name="Razer Basilisk V2",
            vid=0x1532,
            pid=0x0085,
            product="Razer Basilisk V2",
            manufacturer="Razer",
        ),
        Profile(
            key="microsoft_basic",
            name="Microsoft Basic Optical Mouse",
            vid=0x045E,
            pid=0x0040,
            product="Microsoft Basic Optical Mouse",
            manufacturer="Microsoft",
        ),
    ]
}


DEFAULT_KEY = "logitech_g502"


def get(key: str) -> Profile:
    return PROFILES[key]


def keys() -> list[str]:
    return list(PROFILES.keys())


def names() -> list[str]:
    return [p.name for p in PROFILES.values()]


def by_name(name: str) -> Profile:
    for p in PROFILES.values():
        if p.name == name:
            return p
    raise KeyError(name)
