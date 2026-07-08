"""Research-grade URL canonicalisation for duplicate detection.

Normalises scheme, host case, IDN/punycode, default ports, query-parameter
order and duplicates, fragments, unicode (NFC) and trailing slashes. Two
visually different spellings of the same URL canonicalise identically, which
makes cross-evidence correlation and cache hits reliable.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_DEFAULT_PORTS = {"http": 80, "https": 443, "ftp": 21}


def normalize_url(url: str) -> str:
    """Canonicalise ``url`` (never raises; returns best effort)."""
    try:
        candidate = unicodedata.normalize("NFC", url.strip())
        if "://" not in candidate:
            candidate = "http://" + candidate
        parts = urlsplit(candidate)

        scheme = parts.scheme.lower()
        host = parts.hostname or ""
        try:  # IDN -> punycode, lowercase
            host = host.encode("idna").decode("ascii").lower()
        except (UnicodeError, AttributeError):
            host = host.lower()

        netloc = host
        if parts.port and parts.port != _DEFAULT_PORTS.get(scheme):
            netloc = f"{host}:{parts.port}"

        path = parts.path or "/"
        while "//" in path:
            path = path.replace("//", "/")
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/") or "/"

        # Sort query params and drop exact duplicates (keeps first value).
        seen = set()
        params = []
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            if (key, val) not in seen:
                seen.add((key, val))
                params.append((key, val))
        query = urlencode(sorted(params))

        return urlunsplit((scheme, netloc, path, query, ""))  # fragment dropped
    except Exception:  # noqa: BLE001 - normalisation must never crash intake
        return url.strip()


def normalize_domain(domain: str) -> str:
    """Canonical domain form (lowercase punycode, no trailing dot)."""
    host = domain.strip().rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except (UnicodeError, AttributeError):
        return host
