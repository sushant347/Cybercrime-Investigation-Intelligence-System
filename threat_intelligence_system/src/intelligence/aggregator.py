"""
Intelligence aggregator.

Orchestrates multiple ``BaseConnector`` instances, running each one against a
target domain and collecting the results into a single unified dictionary
keyed by connector name.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from src.intelligence.base_connector import BaseConnector, IntelligenceResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class IntelligenceAggregator:
    """Facade that coordinates all threat-intelligence connectors.

    When instantiated without an explicit list of connectors the aggregator
    creates all built-in connectors (VirusTotal, WHOIS, DNS, SSL, GeoIP).
    Connectors that are unavailable (e.g. missing API key) are still
    registered -- they will return graceful failure results.

    Now includes thread-safe query caching (v2.0) to prevent redundant lookups.

    Attributes:
        connectors: List of ``BaseConnector`` instances managed by this
            aggregator.
    """

    # Cache time-to-live: 1 hour (3600 seconds)
    _CACHE_TTL_SECONDS: int = 3600

    def __init__(self, connectors: list[BaseConnector] | None = None) -> None:
        """Initialise the aggregator.

        Args:
            connectors: Optional explicit list of connector instances.
                If ``None``, all default connectors are created automatically.
        """
        if connectors is not None:
            self.connectors: list[BaseConnector] = connectors
        else:
            self.connectors = self._create_default_connectors()

        # Cache store: domain -> (timestamp, results_dict)
        self._cache: dict[str, tuple[float, dict[str, IntelligenceResult]]] = {}
        self._cache_lock = threading.Lock()

        logger.info(
            "IntelligenceAggregator initialised with %d connectors: %s",
            len(self.connectors),
            ", ".join(c.name for c in self.connectors),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def gather(self, domain: str) -> dict[str, IntelligenceResult]:
        """Run every registered connector for *domain*, utilizing cache if fresh.

        Each connector is invoked independently; a failure in one connector
        does not affect the others.

        Args:
            domain: The target domain (e.g. ``'example.com'``).

        Returns:
            Dictionary mapping connector name -> ``IntelligenceResult``.
        """
        domain = domain.lower().strip()
        now = time.time()

        # Check cache
        with self._cache_lock:
            if domain in self._cache:
                timestamp, cached_results = self._cache[domain]
                if now - timestamp < self._CACHE_TTL_SECONDS:
                    logger.debug("Cache hit for domain: %s (age=%.1fs)", domain, now - timestamp)
                    return cached_results
                else:
                    logger.debug("Cache expired for domain: %s", domain)
                    del self._cache[domain]

        results: dict[str, IntelligenceResult] = {}

        for connector in self.connectors:
            try:
                logger.debug("Running connector '%s' for %s", connector.name, domain)
                result = connector.query(domain)
                results[connector.name] = result
            except Exception as exc:
                logger.exception(
                    "Unexpected error in connector '%s' for %s: %s",
                    connector.name, domain, exc,
                )
                results[connector.name] = IntelligenceResult(
                    source=connector.name,
                    domain=domain,
                    data={},
                    success=False,
                    error_message=f"Unexpected error: {exc}",
                )

        # Save to cache
        with self._cache_lock:
            self._cache[domain] = (now, results)

        return results

    def gather_dict(self, domain: str) -> dict[str, Any]:
        """Run every registered connector and return a flattened dictionary.

        This is a convenience wrapper around :meth:`gather` that merges all
        result ``data`` dicts into one flat mapping, with each key prefixed
        by the connector name (e.g. ``'virustotal_positives'``).  Top-level
        metadata (``success``, ``error_message``) is also included.

        Args:
            domain: The target domain.

        Returns:
            Flat dictionary of all intelligence values.
        """
        raw = self.gather(domain)
        flat: dict[str, Any] = {}

        for connector_name, result in raw.items():
            prefix = connector_name
            flat[f"{prefix}_success"] = result.success
            flat[f"{prefix}_error"] = result.error_message

            for key, value in result.data.items():
                flat[f"{prefix}_{key}"] = value

        return flat

    def get_available_connectors(self) -> list[str]:
        """Return names of connectors whose prerequisites are satisfied.

        Returns:
            List of connector name strings.
        """
        return [c.name for c in self.connectors if c.is_available()]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_default_connectors() -> list[BaseConnector]:
        """Instantiate all built-in connectors.

        Returns:
            List of default ``BaseConnector`` instances.
        """
        from src.intelligence.virustotal import VirusTotalConnector
        from src.intelligence.whois_connector import WhoisConnector
        from src.intelligence.dns_connector import DNSConnector
        from src.intelligence.ssl_connector import SSLConnector
        from src.intelligence.geoip_connector import GeoIPConnector

        connectors: list[BaseConnector] = []

        for cls in (VirusTotalConnector, WhoisConnector, DNSConnector, SSLConnector, GeoIPConnector):
            try:
                connectors.append(cls())
            except Exception as exc:
                logger.warning(
                    "Failed to instantiate connector %s: %s", cls.__name__, exc
                )

        return connectors
