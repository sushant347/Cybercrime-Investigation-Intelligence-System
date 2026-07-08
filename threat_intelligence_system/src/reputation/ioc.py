"""IOC (Indicator of Compromise) type detection.

Automatically classifies an indicator string so the reputation engine can
route it: url | domain | email | ipv4 | ipv6 | md5 | sha1 | sha256 | phone |
btc_wallet | eth_wallet | telegram | whatsapp | unknown.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

_PATTERNS = [
    ("url", re.compile(r"^(?:https?://|www\.)", re.I)),
    ("email", re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")),
    ("md5", re.compile(r"^[a-fA-F0-9]{32}$")),
    ("sha1", re.compile(r"^[a-fA-F0-9]{40}$")),
    ("sha256", re.compile(r"^[a-fA-F0-9]{64}$")),
    ("eth_wallet", re.compile(r"^0x[a-fA-F0-9]{40}$")),
    ("btc_wallet", re.compile(r"^(?:bc1[ac-hj-np-z02-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")),
    ("telegram", re.compile(r"^@[A-Za-z][A-Za-z0-9_]{4,31}$|^(?:https?://)?t\.me/", re.I)),
    ("whatsapp", re.compile(r"^(?:https?://)?wa\.me/\+?\d{8,15}$", re.I)),
    ("phone", re.compile(r"^\+?[\d][\d\-\s]{6,15}\d$")),
    ("domain", re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$", re.I)),
]


@dataclass(frozen=True)
class IOC:
    """A classified indicator."""

    value: str
    ioc_type: str


def detect_ioc(value: str) -> IOC:
    """Classify one indicator string (never raises)."""
    candidate = value.strip()
    try:
        ipaddress.IPv4Address(candidate)
        return IOC(candidate, "ipv4")
    except ValueError:
        pass
    try:
        if ":" in candidate:
            ipaddress.IPv6Address(candidate)
            return IOC(candidate, "ipv6")
    except ValueError:
        pass
    for ioc_type, pattern in _PATTERNS:
        if pattern.search(candidate):
            return IOC(candidate, ioc_type)
    return IOC(candidate, "unknown")
