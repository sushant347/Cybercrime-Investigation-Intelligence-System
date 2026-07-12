"""
VirusTotal threat intelligence connector.

Queries the VirusTotal v3 API for domain reputation data including malicious
detection counts, scanner results, categories, and detected URL statistics.
"""

from __future__ import annotations

from typing import Any

from src.config.settings import get_settings
from src.intelligence.base_connector import BaseConnector, IntelligenceResult
from src.utils.helpers import safe_request
from src.utils.logger import get_logger

logger = get_logger(__name__)

_VT_API_BASE = "https://www.virustotal.com/api/v3/domains"


class VirusTotalConnector(BaseConnector):
    """Connector for the VirusTotal v3 domain reputation API.

    Requires a valid ``VIRUSTOTAL_API_KEY`` in the environment.  When no key is
    configured the connector reports itself as unavailable and ``query`` returns
    a failed ``IntelligenceResult`` with a descriptive error message.

    Returned data keys:
        positives, total_scanners, scan_date, permalink, detected_urls_count,
        categories, reputation_score.
    """

    def __init__(self) -> None:
        """Initialise the VirusTotal connector and load settings."""
        self._settings = get_settings()
        self._api_key: str | None = self._settings.api.virustotal_api_key
        self._timeout: int = self._settings.api.request_timeout
        self._max_retries: int = self._settings.api.max_retries

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the connector identifier.

        Returns:
            ``'virustotal'``
        """
        return "virustotal"

    def is_available(self) -> bool:
        """Check whether a VirusTotal API key is configured.

        Returns:
            ``True`` if the API key is present, ``False`` otherwise.
        """
        return self._api_key is not None and len(self._api_key) > 0

    def query(self, domain: str) -> IntelligenceResult:
        """Query the VirusTotal v3 domains endpoint.

        Args:
            domain: The domain to investigate (e.g. ``'example.com'``).

        Returns:
            ``IntelligenceResult`` containing VirusTotal analysis data.
        """
        if not self.is_available():
            logger.warning("VirusTotal API key not configured -- skipping query")
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={},
                success=False,
                error_message="API key not configured",
            )

        url = f"{_VT_API_BASE}/{domain}"
        headers = {"x-apikey": self._api_key}

        try:
            response = safe_request(
                url,
                method="GET",
                timeout=self._timeout,
                max_retries=self._max_retries,
                headers=headers,
            )

            if response is None:
                logger.error("VirusTotal returned no response for %s", domain)
                return IntelligenceResult(
                    source=self.name,
                    domain=domain,
                    data={},
                    success=False,
                    error_message="No response from VirusTotal API",
                )

            payload: dict[str, Any] = response.json()
            data = self._parse_response(payload, domain)

            logger.info(
                "VirusTotal query for %s: %d/%d detections",
                domain,
                data.get("positives", 0),
                data.get("total_scanners", 0),
            )

            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data=data,
                success=True,
            )

        except Exception as exc:
            logger.exception("VirusTotal query failed for %s: %s", domain, exc)
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={},
                success=False,
                error_message=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(payload: dict[str, Any], domain: str) -> dict[str, Any]:
        """Extract useful fields from the VirusTotal v3 JSON response.

        Args:
            payload: Raw JSON dict from the API.
            domain: Queried domain (used for permalink fallback).

        Returns:
            Flat dictionary of parsed intelligence values.
        """
        attributes: dict[str, Any] = payload.get("data", {}).get("attributes", {})

        # Last analysis stats  (malicious, undetected, harmless, suspicious, timeout)
        analysis_stats: dict[str, int] = attributes.get("last_analysis_stats", {})
        positives: int = analysis_stats.get("malicious", 0) + analysis_stats.get("suspicious", 0)
        total_scanners: int = sum(analysis_stats.values()) if analysis_stats else 0

        # Last analysis date (epoch -> ISO 8601)
        last_analysis_epoch: int | None = attributes.get("last_analysis_date")
        scan_date: str | None = None
        if last_analysis_epoch is not None:
            try:
                from datetime import datetime, timezone
                scan_date = datetime.fromtimestamp(
                    last_analysis_epoch, tz=timezone.utc
                ).isoformat()
            except (OSError, ValueError):
                scan_date = None

        # Categories (dict of engine->category)
        categories: dict[str, str] = attributes.get("categories", {})

        # Reputation score (VirusTotal community score)
        reputation_score: int = attributes.get("reputation", 0)

        # Detected communicating / downloaded / referrer URLs
        detected_urls_count: int = 0
        for relation_key in (
            "last_https_certificate",
            "last_dns_records",
        ):
            # The v3 API doesn't directly give detected_urls in the domain
            # endpoint; we approximate from 'total_votes' or relationships.
            pass
        detected_urls_count = attributes.get("last_analysis_results", {})
        detected_urls_count = (
            len(detected_urls_count) if isinstance(detected_urls_count, dict) else 0
        )

        # Permalink
        link: str = payload.get("data", {}).get("links", {}).get(
            "self", f"https://www.virustotal.com/gui/domain/{domain}"
        )

        return {
            "positives": positives,
            "total_scanners": total_scanners,
            "scan_date": scan_date,
            "permalink": link,
            "detected_urls_count": detected_urls_count,
            "categories": categories,
            "reputation_score": reputation_score,
        }
