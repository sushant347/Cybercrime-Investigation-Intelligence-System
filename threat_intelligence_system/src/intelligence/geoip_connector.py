"""
GeoIP threat intelligence connector.

Resolves a domain to an IP address, then enriches it with geographic and
network metadata.  The connector tries the ``geoip2`` MaxMind library first;
if that is unavailable or the database is missing it falls back to the free
``ip-api.com`` JSON endpoint.
"""

from __future__ import annotations

import socket
from typing import Any

from src.config.settings import get_settings
from src.intelligence.base_connector import BaseConnector, IntelligenceResult
from src.utils.helpers import safe_request
from src.utils.logger import get_logger

logger = get_logger(__name__)

_IP_API_URL = "http://ip-api.com/json"


class GeoIPConnector(BaseConnector):
    """Connector for IP geolocation and network intelligence.

    Resolution pipeline:
    1. ``socket.gethostbyname`` to obtain the A-record IP.
    2. ``geoip2`` (MaxMind GeoLite2 databases) if available.
    3. Free ``ip-api.com`` JSON API as a fallback.

    Returned data keys:
        ip_address, country, country_code, city, latitude, longitude,
        asn, asn_org, hosting_provider, is_hosting, is_proxy, is_vpn.
    """

    def __init__(self) -> None:
        """Initialise the GeoIP connector and probe for optional libraries."""
        self._settings = get_settings()
        self._geoip2_available: bool = False
        try:
            import geoip2  # noqa: F401
            self._geoip2_available = True
        except ImportError:
            logger.debug("geoip2 library not installed -- will use ip-api.com fallback")

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the connector identifier.

        Returns:
            ``'geoip'``
        """
        return "geoip"

    def is_available(self) -> bool:
        """GeoIP lookups always have a fallback; connector is always available.

        Returns:
            ``True``
        """
        return True

    def query(self, domain: str) -> IntelligenceResult:
        """Resolve *domain* to an IP and enrich with geolocation data.

        Args:
            domain: The domain to investigate (e.g. ``'example.com'``).

        Returns:
            ``IntelligenceResult`` containing geolocation / ASN metadata.
        """
        # Step 1 -- resolve domain to IP
        ip_address = self._resolve_ip(domain)
        if ip_address is None:
            logger.warning("Could not resolve IP for %s", domain)
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={"ip_address": None},
                success=False,
                error_message=f"Could not resolve IP for {domain}",
            )

        # Step 2 -- try geoip2
        if self._geoip2_available:
            data = self._query_geoip2(ip_address)
            if data is not None:
                data["ip_address"] = ip_address
                logger.info(
                    "GeoIP (geoip2) for %s (%s): country=%s, asn=%s",
                    domain, ip_address, data.get("country"), data.get("asn"),
                )
                return IntelligenceResult(
                    source=self.name,
                    domain=domain,
                    data=data,
                    success=True,
                )

        # Step 3 -- fallback to ip-api.com
        try:
            data = self._query_ip_api(ip_address)
            data["ip_address"] = ip_address
            logger.info(
                "GeoIP (ip-api) for %s (%s): country=%s, asn=%s",
                domain, ip_address, data.get("country"), data.get("asn"),
            )
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data=data,
                success=True,
            )
        except Exception as exc:
            logger.exception("GeoIP query failed for %s: %s", domain, exc)
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={"ip_address": ip_address},
                success=False,
                error_message=str(exc),
            )

    # ------------------------------------------------------------------
    # DNS resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_ip(domain: str) -> str | None:
        """Resolve *domain* to an IPv4 address using ``socket.gethostbyname``.

        Args:
            domain: Domain name string.

        Returns:
            IPv4 address string or ``None`` on failure.
        """
        try:
            return socket.gethostbyname(domain)
        except socket.gaierror:
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # geoip2 (MaxMind) path
    # ------------------------------------------------------------------

    def _query_geoip2(self, ip_address: str) -> dict[str, Any] | None:
        """Query the MaxMind GeoLite2 databases for *ip_address*.

        Tries City, ASN, and (optionally) Anonymous-IP databases.

        Args:
            ip_address: IPv4 or IPv6 address string.

        Returns:
            Dictionary of geolocation data, or ``None`` if databases are
            unavailable.
        """
        try:
            import geoip2.database  # type: ignore[import-untyped]

            data: dict[str, Any] = {
                "country": None,
                "country_code": None,
                "city": None,
                "latitude": None,
                "longitude": None,
                "asn": None,
                "asn_org": None,
                "hosting_provider": None,
                "is_hosting": False,
                "is_proxy": False,
                "is_vpn": False,
            }

            settings = self._settings
            db_dir = settings.paths.project_root / "data" / "geoip"

            # City database
            city_db = db_dir / "GeoLite2-City.mmdb"
            if city_db.exists():
                with geoip2.database.Reader(str(city_db)) as reader:
                    resp = reader.city(ip_address)
                    data["country"] = resp.country.name
                    data["country_code"] = resp.country.iso_code
                    data["city"] = resp.city.name
                    if resp.location:
                        data["latitude"] = resp.location.latitude
                        data["longitude"] = resp.location.longitude
            else:
                logger.debug("GeoLite2-City.mmdb not found at %s", city_db)

            # ASN database
            asn_db = db_dir / "GeoLite2-ASN.mmdb"
            if asn_db.exists():
                with geoip2.database.Reader(str(asn_db)) as reader:
                    resp = reader.asn(ip_address)
                    data["asn"] = resp.autonomous_system_number
                    data["asn_org"] = resp.autonomous_system_organization
                    data["hosting_provider"] = resp.autonomous_system_organization
            else:
                logger.debug("GeoLite2-ASN.mmdb not found at %s", asn_db)

            # Anonymous-IP database (optional)
            anon_db = db_dir / "GeoIP2-Anonymous-IP.mmdb"
            if anon_db.exists():
                with geoip2.database.Reader(str(anon_db)) as reader:
                    resp = reader.anonymous_ip(ip_address)
                    data["is_hosting"] = getattr(resp, "is_hosting_provider", False)
                    data["is_proxy"] = getattr(resp, "is_public_proxy", False) or getattr(
                        resp, "is_residential_proxy", False
                    )
                    data["is_vpn"] = getattr(resp, "is_anonymous_vpn", False)

            # If no city data was found, the databases may be missing entirely
            if data["country"] is None and data["asn"] is None:
                return None

            return data

        except Exception as exc:
            logger.debug("geoip2 lookup failed for %s: %s", ip_address, exc)
            return None

    # ------------------------------------------------------------------
    # ip-api.com fallback
    # ------------------------------------------------------------------

    def _query_ip_api(self, ip_address: str) -> dict[str, Any]:
        """Query the free ``ip-api.com`` JSON endpoint for *ip_address*.

        Args:
            ip_address: IPv4 or IPv6 address string.

        Returns:
            Dictionary of geolocation data.

        Raises:
            RuntimeError: If the API call fails.
        """
        url = f"{_IP_API_URL}/{ip_address}?fields=status,message,country,countryCode,city,lat,lon,as,org,hosting,proxy"

        response = safe_request(
            url,
            method="GET",
            timeout=self._settings.api.request_timeout,
            max_retries=2,
        )

        if response is None:
            raise RuntimeError(f"ip-api.com returned no response for {ip_address}")

        payload: dict[str, Any] = response.json()

        if payload.get("status") == "fail":
            raise RuntimeError(
                f"ip-api.com query failed: {payload.get('message', 'unknown error')}"
            )

        # Parse ASN number from the "as" field (e.g. "AS13335 Cloudflare, Inc.")
        as_field: str = payload.get("as", "")
        asn: int | None = None
        asn_org: str | None = None
        if as_field:
            parts = as_field.split(" ", 1)
            try:
                asn = int(parts[0].replace("AS", ""))
            except (ValueError, IndexError):
                pass
            asn_org = parts[1] if len(parts) > 1 else as_field

        return {
            "country": payload.get("country"),
            "country_code": payload.get("countryCode"),
            "city": payload.get("city"),
            "latitude": payload.get("lat"),
            "longitude": payload.get("lon"),
            "asn": asn,
            "asn_org": asn_org,
            "hosting_provider": payload.get("org"),
            "is_hosting": payload.get("hosting", False),
            "is_proxy": payload.get("proxy", False),
            "is_vpn": False,  # ip-api free tier does not differentiate VPN
        }
