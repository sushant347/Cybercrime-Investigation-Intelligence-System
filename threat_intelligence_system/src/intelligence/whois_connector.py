"""
WHOIS threat intelligence connector.

Retrieves domain registration data (registrar, dates, name-servers, DNSSEC,
registrant country) via the ``python-whois`` library and calculates domain age
in days from the creation date.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.intelligence.base_connector import BaseConnector, IntelligenceResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WhoisConnector(BaseConnector):
    """Connector for WHOIS registration lookups.

    Uses the ``python-whois`` (``whois``) library.  No API key is required,
    but the library itself must be installed.

    Returned data keys:
        registrar, creation_date, expiration_date, updated_date,
        domain_age_days, name_servers, registrant_country, dnssec, status.
    """

    def __init__(self) -> None:
        """Initialise the WHOIS connector and check library availability."""
        self._whois_available: bool = False
        try:
            import whois as _whois  # noqa: F401
            self._whois_available = True
        except ImportError:
            logger.warning("python-whois library not installed -- WHOIS connector unavailable")

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the connector identifier.

        Returns:
            ``'whois'``
        """
        return "whois"

    def is_available(self) -> bool:
        """Check whether the python-whois library is installed.

        Returns:
            ``True`` if the library is importable, ``False`` otherwise.
        """
        return self._whois_available

    def query(self, domain: str) -> IntelligenceResult:
        """Perform a WHOIS lookup for *domain*.

        Args:
            domain: The domain to investigate (e.g. ``'example.com'``).

        Returns:
            ``IntelligenceResult`` containing parsed WHOIS registration data.
        """
        if not self.is_available():
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={},
                success=False,
                error_message="python-whois library not installed",
            )

        try:
            import whois  # type: ignore[import-untyped]

            raw = whois.whois(domain)
            data = self._parse_whois(raw)

            logger.info(
                "WHOIS query for %s: age=%s days, registrar=%s",
                domain,
                data.get("domain_age_days", "N/A"),
                data.get("registrar", "N/A"),
            )

            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data=data,
                success=True,
            )

        except Exception as exc:
            logger.warning("WHOIS query failed for %s: %s", domain, exc)
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
    def _normalise_date(raw_date: Any) -> str | None:
        """Convert a raw WHOIS date value to ISO 8601 string.

        ``python-whois`` sometimes returns a list of ``datetime`` objects or
        a single ``datetime``.  This helper normalises both cases.

        Args:
            raw_date: Raw date value from the WHOIS record.

        Returns:
            ISO 8601 date string, or ``None`` if parsing fails.
        """
        if raw_date is None:
            return None

        if isinstance(raw_date, list):
            raw_date = raw_date[0] if raw_date else None

        if isinstance(raw_date, datetime):
            return raw_date.isoformat()

        if isinstance(raw_date, str):
            return raw_date

        return str(raw_date) if raw_date is not None else None

    @staticmethod
    def _calculate_domain_age(creation_date: Any) -> int | None:
        """Calculate the domain age in days from a raw creation date.

        Args:
            creation_date: Raw creation date from WHOIS (datetime, list, or str).

        Returns:
            Age in days as an integer, or ``None`` if calculation is impossible.
        """
        if creation_date is None:
            return None

        if isinstance(creation_date, list):
            creation_date = creation_date[0] if creation_date else None

        if creation_date is None:
            return None

        try:
            if isinstance(creation_date, datetime):
                created = creation_date
            elif isinstance(creation_date, str):
                from dateutil.parser import parse as dateutil_parse
                created = dateutil_parse(creation_date)
            else:
                return None

            # Make timezone-aware for comparison
            now = datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            delta = now - created
            return max(int(delta.total_seconds() / 86400), 0)

        except Exception:
            return None

    @classmethod
    def _parse_whois(cls, raw: Any) -> dict[str, Any]:
        """Extract and normalise fields from a raw WHOIS response.

        Args:
            raw: The ``whois.whois()`` return object.

        Returns:
            Flat dictionary of normalised WHOIS intelligence values.
        """
        creation_date_raw = getattr(raw, "creation_date", None)
        expiration_date_raw = getattr(raw, "expiration_date", None)
        updated_date_raw = getattr(raw, "updated_date", None)

        # Name servers may be a list or a single string
        name_servers_raw = getattr(raw, "name_servers", None)
        if isinstance(name_servers_raw, list):
            name_servers = sorted({ns.lower() for ns in name_servers_raw if ns})
        elif isinstance(name_servers_raw, str):
            name_servers = [name_servers_raw.lower()]
        else:
            name_servers = []

        # Status may be a list or a single string
        status_raw = getattr(raw, "status", None)
        if isinstance(status_raw, list):
            status = status_raw
        elif isinstance(status_raw, str):
            status = [status_raw]
        else:
            status = []

        return {
            "registrar": getattr(raw, "registrar", None),
            "creation_date": cls._normalise_date(creation_date_raw),
            "expiration_date": cls._normalise_date(expiration_date_raw),
            "updated_date": cls._normalise_date(updated_date_raw),
            "domain_age_days": cls._calculate_domain_age(creation_date_raw),
            "name_servers": name_servers,
            "registrant_country": getattr(raw, "country", None),
            "dnssec": getattr(raw, "dnssec", None),
            "status": status,
        }
