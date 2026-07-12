"""Modular blacklist / threat-feed connectors (Strategy + Factory pattern).

Each connector is independent and supports ``enable()/disable()``, shared
TTL caching, per-request timeout, bounded retry and graceful fallback: a
dead feed is marked ``available=False`` and processing continues with
partial results - the engine never crashes on a network failure.

Feeds (all free/community): OpenPhish, PhishTank (public data file mirror),
URLHaus. Feed downloads are cached; an optional local feed file (offline
mode, e.g. for tests or air-gapped labs) is honoured first.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from .cache import TTLCache
from .normalizer import normalize_domain, normalize_url


@dataclass
class BlacklistResult:
    """Outcome of one connector check."""

    source: str
    available: bool
    listed: bool
    detail: str = ""


class BlacklistConnector(ABC):
    """Base class: cached, retried, timeout-bounded feed lookup."""

    name: str = "base"
    feed_url: str = ""

    def __init__(self, cache: Optional[TTLCache] = None,
                 timeout: float = 8.0, retries: int = 1,
                 local_feed: Optional[Path] = None) -> None:
        self._cache = cache or TTLCache(ttl_seconds=1800)
        self._timeout = timeout
        self._retries = retries
        self._local_feed = local_feed
        self._enabled = True

    # -------------------------------------------------------------- lifecycle
    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------ query
    def check(self, indicator: str) -> BlacklistResult:
        """Check one URL/domain against the feed (never raises)."""
        if not self._enabled:
            return BlacklistResult(self.name, False, False, "disabled")
        entries = self._entries()
        if entries is None:
            return BlacklistResult(self.name, False, False, "feed unavailable")
        listed, detail = self._match(indicator, entries)
        return BlacklistResult(self.name, True, listed, detail)

    # ---------------------------------------------------------------- internal
    def _entries(self) -> Optional[Set[str]]:
        cached = self._cache.get(f"feed:{self.name}")
        if cached is not None:
            return cached
        raw = self._load_local() or self._download()
        if raw is None:
            return None
        entries = self._parse(raw)
        self._cache.set(f"feed:{self.name}", entries)
        return entries

    def _load_local(self) -> Optional[str]:
        if self._local_feed and self._local_feed.exists():
            try:
                return self._local_feed.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return None
        return None

    def _download(self) -> Optional[str]:
        if not self.feed_url:
            return None
        try:
            import requests
        except ImportError:
            return None
        for attempt in range(self._retries + 1):
            try:
                response = requests.get(self.feed_url, timeout=self._timeout)
                if response.ok:
                    return response.text
            except Exception:  # noqa: BLE001 - graceful degradation by design
                if attempt < self._retries:
                    time.sleep(0.5 * (attempt + 1))
        return None

    def _parse(self, raw: str) -> Set[str]:
        return {
            normalize_url(line.strip())
            for line in raw.splitlines()
            if line.strip() and not line.startswith("#")
        }

    def _match(self, indicator: str, entries: Set[str]) -> tuple[bool, str]:
        url = normalize_url(indicator)
        domain = normalize_domain(url.split("://", 1)[-1].split("/", 1)[0])
        if url in entries:
            return True, "exact URL listed"
        for entry in entries:
            entry_host = entry.split("://", 1)[-1].split("/", 1)[0]
            if entry_host == domain:
                return True, f"domain listed ({entry_host})"
        return False, ""

    @abstractmethod
    def _identity(self) -> str:  # keeps subclasses non-trivial for the factory
        ...


class OpenPhishConnector(BlacklistConnector):
    name = "openphish"
    feed_url = "https://openphish.com/feed.txt"

    def _identity(self) -> str:
        return self.name


class PhishTankConnector(BlacklistConnector):
    name = "phishtank"
    feed_url = "http://data.phishtank.com/data/online-valid.csv"

    def _parse(self, raw: str) -> Set[str]:
        entries: Set[str] = set()
        for line in raw.splitlines()[1:]:
            parts = line.split(",")
            if len(parts) > 1 and parts[1].startswith("http"):
                entries.add(normalize_url(parts[1].strip('"')))
        return entries

    def _identity(self) -> str:
        return self.name


class URLHausConnector(BlacklistConnector):
    name = "urlhaus"
    feed_url = "https://urlhaus.abuse.ch/downloads/text/"

    def _identity(self) -> str:
        return self.name


class BlacklistEngine:
    """Runs every enabled connector; aggregates partial results (Factory)."""

    def __init__(self, connectors: Optional[List[BlacklistConnector]] = None,
                 cache: Optional[TTLCache] = None) -> None:
        shared = cache or TTLCache(ttl_seconds=1800)
        self.connectors: List[BlacklistConnector] = connectors if connectors is not None else [
            OpenPhishConnector(cache=shared),
            PhishTankConnector(cache=shared),
            URLHausConnector(cache=shared),
        ]

    def check(self, indicator: str) -> List[BlacklistResult]:
        return [connector.check(indicator) for connector in self.connectors]

    def hit_count(self, results: List[BlacklistResult]) -> int:
        return sum(1 for r in results if r.available and r.listed)
