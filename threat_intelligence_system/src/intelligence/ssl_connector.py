"""
SSL / TLS certificate threat intelligence connector.

Connects to a domain on port 443 and inspects the server certificate to
extract issuer details, validity dates, Subject Alternative Names (SANs),
self-signed status, and other cryptographic metadata.
"""

from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from typing import Any

from src.intelligence.base_connector import BaseConnector, IntelligenceResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_SSL_PORT = 443
_DEFAULT_TIMEOUT = 10


class SSLConnector(BaseConnector):
    """Connector for TLS certificate analysis.

    Uses the Python standard-library ``ssl`` and ``socket`` modules -- no
    external dependencies or API keys required.

    Returned data keys:
        has_ssl, issuer, subject, serial_number, not_before, not_after,
        is_expired, days_until_expiry, is_self_signed, protocol_version,
        san_list, certificate_chain_length.
    """

    def __init__(self, timeout: int = _DEFAULT_TIMEOUT) -> None:
        """Initialise the SSL connector.

        Args:
            timeout: TCP connection timeout in seconds.
        """
        self._timeout: int = timeout

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the connector identifier.

        Returns:
            ``'ssl'``
        """
        return "ssl"

    def is_available(self) -> bool:
        """SSL inspection uses only the stdlib; always available.

        Returns:
            ``True``
        """
        return True

    def query(self, domain: str) -> IntelligenceResult:
        """Inspect the TLS certificate served by *domain*.

        Args:
            domain: The domain to investigate (e.g. ``'example.com'``).

        Returns:
            ``IntelligenceResult`` containing certificate metadata.
        """
        try:
            cert, cert_bin, protocol_version, chain_length, ssl_status = self._fetch_certificate(domain)

            if cert is None:
                logger.info("No SSL certificate found for %s", domain)
                return IntelligenceResult(
                    source=self.name,
                    domain=domain,
                    data={
                        "has_ssl": False,
                        "ssl_status": "INVALID",
                        "has_hsts": False,
                    },
                    success=True,
                )

            data = self._parse_certificate(cert, protocol_version, chain_length)
            
            # Check for HSTS (Strict-Transport-Security) header
            has_hsts = False
            try:
                from src.utils.helpers import safe_request
                resp = safe_request(f"https://{domain}", method="HEAD", timeout=2, max_retries=1)
                if resp is not None and "Strict-Transport-Security" in resp.headers:
                    has_hsts = True
            except Exception:
                pass
            data["has_hsts"] = has_hsts

            # Override/Determine SSL validation status
            is_expired = data.get("is_expired", False)
            is_self_signed = data.get("is_self_signed", False)
            if ssl_status == "INVALID" or is_expired or is_self_signed:
                data["ssl_status"] = "INVALID"
            else:
                data["ssl_status"] = "VALID"

            logger.info(
                "SSL query for %s: issuer=%s, expires=%s, self_signed=%s, status=%s, hsts=%s",
                domain,
                data.get("issuer", "N/A"),
                data.get("not_after", "N/A"),
                data.get("is_self_signed", "N/A"),
                data["ssl_status"],
                has_hsts,
            )

            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data=data,
                success=True,
            )

        except (socket.timeout, TimeoutError) as exc:
            logger.warning("SSL query timed out for %s: %s", domain, exc)
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={
                    "has_ssl": "unknown",
                    "ssl_status": "UNKNOWN",
                    "has_hsts": False,
                },
                success=False,
                error_message=f"Timeout: {exc}",
            )
        except (socket.gaierror, ConnectionRefusedError, ConnectionResetError) as exc:
            logger.warning("SSL connection refused/failed for %s: %s", domain, exc)
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={
                    "has_ssl": "unknown",
                    "ssl_status": "UNKNOWN",
                    "has_hsts": False,
                },
                success=False,
                error_message=f"Connection failed: {exc}",
            )
        except Exception as exc:
            logger.warning("SSL query failed for %s: %s", domain, exc)
            return IntelligenceResult(
                source=self.name,
                domain=domain,
                data={
                    "has_ssl": "unknown",
                    "ssl_status": "UNKNOWN",
                    "has_hsts": False,
                },
                success=False,
                error_message=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_certificate(
        self, domain: str
    ) -> tuple[dict[str, Any] | None, bytes | None, str | None, int, str]:
        """Open a TLS connection to *domain*:443 and retrieve the certificate.

        Args:
            domain: Target domain.

        Returns:
            Tuple of (parsed cert dict, DER bytes, protocol version string,
            chain length, verification status).
        """
        # Try 1: Connect with CERT_REQUIRED (standard validation)
        context = ssl.create_default_context()
        conn = context.wrap_socket(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            server_hostname=domain,
        )
        conn.settimeout(self._timeout)

        try:
            conn.connect((domain, _DEFAULT_SSL_PORT))
            cert = conn.getpeercert(binary_form=False) or {}
            cert_bin = conn.getpeercert(binary_form=True) or b""
            protocol_version = conn.version() or "unknown"
            
            chain_length = 1
            try:
                chain = getattr(conn, "get_verified_chain", lambda: None)()
                if chain:
                    chain_length = len(chain)
            except Exception:
                pass

            return cert if cert else None, cert_bin, protocol_version, chain_length, "VALID"

        except (ssl.SSLCertVerificationError, ssl.SSLError) as err:
            logger.info("SSL certification verification failed for %s: %s. Retrying with CERT_NONE.", domain, err)
            # Try 2: Connect with CERT_NONE (allow self-signed/expired)
            return self._fetch_certificate_unverified(domain)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _fetch_certificate_unverified(
        self, domain: str
    ) -> tuple[dict[str, Any] | None, bytes | None, str | None, int, str]:
        """Connect to domain:443 with check_hostname=False and CERT_NONE to get certificate details."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        conn = context.wrap_socket(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            server_hostname=domain,
        )
        conn.settimeout(self._timeout)

        try:
            conn.connect((domain, _DEFAULT_SSL_PORT))
            cert_bin = conn.getpeercert(binary_form=True) or b""
            protocol_version = conn.version() or "unknown"
            
            cert_dict = None
            if cert_bin:
                try:
                    cert_dict = ssl._ssl._test_decode_cert(cert_bin)
                except Exception:
                    # Fallback to minimal dict
                    cert_dict = {"subject": (), "issuer": ()}
                    
            return cert_dict, cert_bin, protocol_version, 1, "INVALID"
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _parse_certificate(
        cert: dict[str, Any],
        protocol_version: str | None,
        chain_length: int,
    ) -> dict[str, Any]:
        """Parse a ``getpeercert()`` dict into a flat intelligence payload.

        Args:
            cert: Certificate dict returned by ``SSLSocket.getpeercert()``.
            protocol_version: TLS protocol version string (e.g. ``'TLSv1.3'``).
            chain_length: Number of certificates in the chain.

        Returns:
            Flat dictionary of certificate intelligence values.
        """
        # Issuer / subject -- each is a tuple-of-tuples
        issuer_parts: list[str] = []
        for rdn in cert.get("issuer", ()):
            for attr_type, attr_value in rdn:
                issuer_parts.append(f"{attr_type}={attr_value}")
        issuer_str = ", ".join(issuer_parts) if issuer_parts else None

        subject_parts: list[str] = []
        for rdn in cert.get("subject", ()):
            for attr_type, attr_value in rdn:
                subject_parts.append(f"{attr_type}={attr_value}")
        subject_str = ", ".join(subject_parts) if subject_parts else None

        # Serial number
        serial_number: str | None = cert.get("serialNumber")

        # Validity dates
        not_before_raw: str | None = cert.get("notBefore")
        not_after_raw: str | None = cert.get("notAfter")

        not_before: str | None = None
        not_after: str | None = None
        is_expired: bool = False
        days_until_expiry: int | None = None

        ssl_date_fmt = "%b %d %H:%M:%S %Y %Z"

        if not_before_raw:
            try:
                nb_dt = datetime.strptime(not_before_raw, ssl_date_fmt).replace(
                    tzinfo=timezone.utc
                )
                not_before = nb_dt.isoformat()
            except ValueError:
                not_before = not_before_raw

        if not_after_raw:
            try:
                na_dt = datetime.strptime(not_after_raw, ssl_date_fmt).replace(
                    tzinfo=timezone.utc
                )
                not_after = na_dt.isoformat()
                now = datetime.now(timezone.utc)
                is_expired = na_dt < now
                days_until_expiry = int((na_dt - now).total_seconds() / 86400)
            except ValueError:
                not_after = not_after_raw

        # Self-signed heuristic: issuer == subject
        is_self_signed = issuer_str == subject_str if (issuer_str and subject_str) else False

        # Subject Alternative Names
        san_list: list[str] = []
        for san_type, san_value in cert.get("subjectAltName", ()):
            san_list.append(san_value)

        return {
            "has_ssl": True,
            "issuer": issuer_str,
            "subject": subject_str,
            "serial_number": serial_number,
            "not_before": not_before,
            "not_after": not_after,
            "is_expired": is_expired,
            "days_until_expiry": days_until_expiry,
            "is_self_signed": is_self_signed,
            "protocol_version": protocol_version,
            "san_list": san_list,
            "certificate_chain_length": chain_length,
        }
