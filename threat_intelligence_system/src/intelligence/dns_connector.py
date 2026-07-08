"""
DNS threat intelligence connector.

Resolves multiple DNS record types (A, AAAA, MX, NS, TXT, CNAME) for a domain
and checks for the presence of SPF, DMARC, and DKIM email-authentication
records using the ``dnspython`` library.
"""

from __future__ import annotations

from typing import Any

from src.intelligence.base_connector import BaseConnector, IntelligenceResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

# DNS record types to query
_RECORD_TYPES: list[str] = ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]


class DNSConnector(BaseConnector):
    """Connector for DNS record resolution.

    Uses the ``dnspython`` (``dns.resolver``) library.  No API key is required
    -- the connector is always considered available as long as the library is
    importable.

    Returned data keys:
        a_records, aaaa_records, mx_records, ns_records, txt_records,
        cname_records, has_spf, has_dmarc, has_dkim, record_count, ttl_values.
    """

    def __init__(self) -> None:
        """Initialise the DNS connector and verify library availability."""
        self._dns_available: bool = False
        try:
            import dns.resolver  # noqa: F401
            self._dns_available = True
        except ImportError:
            logger.warning("dnspython library not installed -- DNS connector unavailable")

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the connector identifier.

        Returns:
            ``'dns'``
        """
        return "dns"

    def is_available(self) -> bool:
        """DNS lookups require no API key; availability depends on ``dnspython``.

        Returns:
            ``True`` if the library is importable, ``False`` otherwise.
        """
        return self._dns_available

    def query(self, domain: str) -> IntelligenceResult:
        """Resolve DNS records for *domain*.

        Args:
            domain: The domain to investigate (e.g. ``'example.com'``).

        Returns:
            ``IntelligenceResult`` containing resolved DNS record data.
        """
        if not self.is_available():
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={},
                success=False,
                error_message="dnspython library not installed",
            )

        try:
            data = self._resolve_all(domain)
            logger.info(
                "DNS query for %s: %d total records, SPF=%s, DMARC=%s",
                domain,
                data.get("record_count", 0),
                data.get("has_spf", False),
                data.get("has_dmarc", False),
            )
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data=data,
                success=True,
            )
        except Exception as exc:
            logger.exception("DNS query failed for %s: %s", domain, exc)
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
    def _safe_resolve(
        resolver: Any,
        qname: str,
        rdtype: str,
    ) -> tuple[list[str], int | None]:
        """Resolve a single record type, swallowing expected DNS errors.

        Args:
            resolver: A ``dns.resolver.Resolver`` instance.
            qname: The query name (domain).
            rdtype: The DNS record type string (e.g. ``'A'``).

        Returns:
            A tuple of (list of record strings, TTL or None).
        """
        import dns.resolver
        import dns.rdatatype

        try:
            answers = resolver.resolve(qname, rdtype)
            records = [rdata.to_text() for rdata in answers]
            ttl = int(answers.rrset.ttl) if answers.rrset else None
            return records, ttl
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.resolver.Timeout,
            dns.rdatatype.UnknownRdatatype,
            Exception,
        ):
            return [], None

    @classmethod
    def _resolve_all(cls, domain: str) -> dict[str, Any]:
        """Resolve all record types and email-auth records for *domain*.

        Args:
            domain: The domain to investigate.

        Returns:
            Flat dictionary of resolved DNS intelligence values.
        """
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.timeout = 5.0
        resolver.lifetime = 10.0

        results: dict[str, Any] = {}
        ttl_values: dict[str, int] = {}
        total_records: int = 0

        # Standard record types
        type_key_map: dict[str, str] = {
            "A": "a_records",
            "AAAA": "aaaa_records",
            "MX": "mx_records",
            "NS": "ns_records",
            "TXT": "txt_records",
            "CNAME": "cname_records",
        }

        for rdtype in _RECORD_TYPES:
            records, ttl = cls._safe_resolve(resolver, domain, rdtype)
            key = type_key_map.get(rdtype, f"{rdtype.lower()}_records")
            results[key] = records
            total_records += len(records)
            if ttl is not None:
                ttl_values[rdtype] = ttl

        # SPF check (present in TXT records)
        txt_records: list[str] = results.get("txt_records", [])
        has_spf: bool = any("v=spf1" in rec.lower() for rec in txt_records)

        # DMARC check (_dmarc.domain TXT record)
        dmarc_records, _ = cls._safe_resolve(resolver, f"_dmarc.{domain}", "TXT")
        has_dmarc: bool = any("v=dmarc1" in rec.lower() for rec in dmarc_records)

        # DKIM check (default selector: default._domainkey.domain)
        has_dkim: bool = False
        for selector in ("default", "google", "selector1", "selector2", "k1"):
            dkim_records, _ = cls._safe_resolve(
                resolver, f"{selector}._domainkey.{domain}", "TXT"
            )
            if dkim_records:
                has_dkim = True
                break

        results["has_spf"] = has_spf
        results["has_dmarc"] = has_dmarc
        results["has_dkim"] = has_dkim
        results["record_count"] = total_records
        results["ttl_values"] = ttl_values

        return results
