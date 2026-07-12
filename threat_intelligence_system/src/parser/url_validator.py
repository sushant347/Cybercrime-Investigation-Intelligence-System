"""
URL validation module for the Phishing URL Detection Engine.

Provides comprehensive URL validation including scheme verification,
IP address detection, punycode analysis, unicode character detection,
URL shortener identification, and structural integrity checks.
"""

import ipaddress
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import tldextract

from src.config.settings import get_settings
from src.utils.helpers import normalize_url
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """
    Result of URL validation containing detailed validation metadata.

    Captures whether a URL is structurally valid and enriches the result
    with boolean flags for scheme type, IP usage, encoding, shortener
    detection, and malformation indicators.

    Attributes:
        is_valid: Whether the URL passed all validation checks.
        url: The original raw URL string that was validated.
        normalized_url: The URL after normalization processing.
        validation_errors: List of human-readable validation error messages.
        has_scheme: Whether the URL contains an explicit scheme prefix.
        scheme: The detected or inferred URL scheme (e.g., 'http', 'https').
        is_http: Whether the scheme is plain HTTP.
        is_https: Whether the scheme is HTTPS.
        is_ip_address: Whether the hostname is an IP address (IPv4 or IPv6).
        is_ipv4: Whether the hostname is an IPv4 address.
        is_ipv6: Whether the hostname is an IPv6 address.
        is_punycode: Whether the hostname uses punycode encoding (xn-- prefix).
        is_unicode: Whether the URL contains non-ASCII unicode characters.
        is_url_shortener: Whether the hostname belongs to a known URL shortener.
        is_malformed: Whether the URL has structural integrity issues.
        is_data_uri: Whether the URL is a data: URI scheme.
    """

    is_valid: bool = False
    url: str = ""
    normalized_url: str = ""
    validation_errors: list[str] = field(default_factory=list)
    has_scheme: bool = False
    scheme: str = ""
    is_http: bool = False
    is_https: bool = False
    is_ip_address: bool = False
    is_ipv4: bool = False
    is_ipv6: bool = False
    is_punycode: bool = False
    is_unicode: bool = False
    is_url_shortener: bool = False
    is_malformed: bool = False
    is_data_uri: bool = False


class URLValidator:
    """
    Comprehensive URL validator for phishing URL detection.

    Performs multi-faceted validation of URLs including scheme verification,
    IP-based hostname detection, internationalized domain name analysis,
    URL shortener identification, and structural integrity checking.

    The validator aggregates results into a ``ValidationResult`` dataclass
    that downstream components (parser, feature extractors) can consume.

    Usage:
        >>> validator = URLValidator()
        >>> result = validator.validate("https://example.com/path")
        >>> print(result.is_valid)
        True
    """

    def __init__(self) -> None:
        """Initialize URLValidator with settings from the application config."""
        settings = get_settings()
        self._url_shorteners: list[str] = list(settings.threat.url_shorteners)
        logger.debug(
            "URLValidator initialized with %d known shortener domains",
            len(self._url_shorteners),
        )

    def validate(self, url: str) -> ValidationResult:
        """
        Perform comprehensive validation on a URL string.

        Runs all sub-validation checks (scheme, IP, punycode, unicode,
        shortener, malformation) and produces a consolidated result.

        Args:
            url: The raw URL string to validate.

        Returns:
            ValidationResult populated with all validation metadata.
        """
        result = ValidationResult(url=url)

        if not url or not url.strip():
            result.validation_errors.append("URL is empty or whitespace-only")
            result.is_malformed = True
            logger.warning("Validation failed: empty URL provided")
            return result

        url = url.strip()
        result.url = url

        # Check for data URI before normalization
        if url.lower().startswith("data:"):
            result.is_data_uri = True
            result.has_scheme = True
            result.scheme = "data"
            result.normalized_url = url
            result.validation_errors.append("URL is a data URI")
            logger.debug("Data URI detected: %s", url[:50])
            return result

        # Normalize the URL
        try:
            result.normalized_url = normalize_url(url)
        except Exception as exc:
            result.validation_errors.append(f"Normalization failed: {exc}")
            result.is_malformed = True
            logger.error("URL normalization failed for '%s': %s", url, exc)
            return result

        # Parse the normalized URL
        try:
            parsed = urlparse(result.normalized_url)
        except Exception as exc:
            result.validation_errors.append(f"URL parsing failed: {exc}")
            result.is_malformed = True
            logger.error("URL parsing failed for '%s': %s", url, exc)
            return result

        # Run individual checks
        self._check_scheme(url, parsed, result)
        hostname = parsed.hostname or ""
        if hostname:
            self._check_ip_address(hostname, result)
            self._check_punycode(hostname, result)
            self._check_url_shortener(hostname, result)
        else:
            result.validation_errors.append("No hostname could be extracted")

        self._check_unicode(url, result)
        self._check_malformed(url, parsed, result)

        # Determine overall validity
        result.is_valid = len(result.validation_errors) == 0

        logger.debug(
            "Validation complete for '%s': valid=%s, errors=%d",
            url[:80],
            result.is_valid,
            len(result.validation_errors),
        )
        return result

    def _check_scheme(
        self,
        raw_url: str,
        parsed: "urlparse",
        result: ValidationResult,
    ) -> None:
        """
        Validate and classify the URL scheme.

        Checks whether the raw URL explicitly includes a scheme prefix
        and categorizes it as HTTP, HTTPS, or other.

        Args:
            raw_url: The original URL string before normalization.
            parsed: The parsed URL components from urllib.parse.urlparse.
            result: The ValidationResult to populate with scheme data.
        """
        scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+\-.]*)(://)", raw_url)
        if scheme_match:
            result.has_scheme = True
            result.scheme = scheme_match.group(1).lower()
        else:
            result.has_scheme = False
            result.scheme = (parsed.scheme or "http").lower()

        result.is_http = result.scheme == "http"
        result.is_https = result.scheme == "https"

        if result.scheme not in ("http", "https", "ftp", "ftps"):
            result.validation_errors.append(
                f"Unusual scheme detected: {result.scheme}"
            )

    def _check_ip_address(self, hostname: str, result: ValidationResult) -> None:
        """
        Detect whether the hostname is an IP address.

        Checks for both IPv4 and IPv6 addresses using the stdlib
        ``ipaddress`` module. Handles bracket-enclosed IPv6 literals.

        Args:
            hostname: The extracted hostname component.
            result: The ValidationResult to populate with IP address flags.
        """
        # Strip IPv6 brackets if present
        clean_host = hostname.strip("[]")

        # Try IPv4
        try:
            ipaddress.IPv4Address(clean_host)
            result.is_ip_address = True
            result.is_ipv4 = True
            return
        except (ipaddress.AddressValueError, ValueError):
            pass

        # Try IPv6
        try:
            ipaddress.IPv6Address(clean_host)
            result.is_ip_address = True
            result.is_ipv6 = True
            return
        except (ipaddress.AddressValueError, ValueError):
            pass

    def _check_punycode(self, hostname: str, result: ValidationResult) -> None:
        """
        Detect punycode-encoded internationalized domain names.

        Punycode domains start with 'xn--' in one or more labels and
        are commonly used in homograph phishing attacks.

        Args:
            hostname: The extracted hostname component.
            result: The ValidationResult to populate with the punycode flag.
        """
        labels = hostname.lower().split(".")
        if any(label.startswith("xn--") for label in labels):
            result.is_punycode = True

    def _check_unicode(self, url: str, result: ValidationResult) -> None:
        """
        Detect non-ASCII unicode characters in the URL.

        URLs containing non-ASCII characters may indicate internationalized
        domain name abuse or homograph attacks.

        Args:
            url: The raw URL string.
            result: The ValidationResult to populate with the unicode flag.
        """
        try:
            url.encode("ascii")
        except UnicodeEncodeError:
            result.is_unicode = True

    def _check_url_shortener(self, hostname: str, result: ValidationResult) -> None:
        """
        Check if the hostname belongs to a known URL shortener service.

        Compares the hostname and registered domain against the configured
        list of known URL shortener domains.

        Args:
            hostname: The extracted hostname component.
            result: The ValidationResult to populate with the shortener flag.
        """
        hostname_lower = hostname.lower()

        # Direct hostname match
        if hostname_lower in self._url_shorteners:
            result.is_url_shortener = True
            return

        # Extract registered domain for comparison
        try:
            extracted = tldextract.extract(hostname_lower)
            registered = f"{extracted.domain}.{extracted.suffix}".lower()
            if registered in self._url_shorteners:
                result.is_url_shortener = True
        except Exception as exc:
            logger.debug("tldextract failed for shortener check: %s", exc)

    def _check_malformed(
        self,
        raw_url: str,
        parsed: "urlparse",
        result: ValidationResult,
    ) -> None:
        """
        Validate the overall structural integrity of the URL.

        Checks for missing hostnames, excessive length, suspicious
        character patterns, and other structural anomalies that
        indicate malformation.

        Args:
            raw_url: The original URL string.
            parsed: The parsed URL components from urllib.parse.urlparse.
            result: The ValidationResult to populate with malformation data.
        """
        hostname = parsed.hostname or ""

        # No hostname
        if not hostname:
            result.is_malformed = True
            result.validation_errors.append("Missing hostname in URL")
            return

        # Excessive URL length (>2048 commonly considered max)
        if len(raw_url) > 2048:
            result.validation_errors.append(
                f"URL length ({len(raw_url)}) exceeds 2048 characters"
            )

        # Hostname with consecutive dots
        if ".." in hostname:
            result.is_malformed = True
            result.validation_errors.append("Hostname contains consecutive dots")

        # Hostname starting or ending with hyphen
        labels = hostname.split(".")
        for label in labels:
            if label.startswith("-") or label.endswith("-"):
                result.is_malformed = True
                result.validation_errors.append(
                    f"Hostname label '{label}' starts or ends with a hyphen"
                )
                break

        # Port validation
        if parsed.port is not None:
            if not (1 <= parsed.port <= 65535):
                result.is_malformed = True
                result.validation_errors.append(
                    f"Invalid port number: {parsed.port}"
                )

        # Multiple @ symbols (credential confusion)
        netloc = parsed.netloc or ""
        if netloc.count("@") > 1:
            result.is_malformed = True
            result.validation_errors.append(
                "Multiple '@' symbols in netloc (possible credential abuse)"
            )

        # Null bytes
        if "\x00" in raw_url:
            result.is_malformed = True
            result.validation_errors.append("URL contains null bytes")

        # Check for whitespace in the middle (excluding leading/trailing)
        stripped = raw_url.strip()
        if re.search(r"\s", stripped):
            result.is_malformed = True
            result.validation_errors.append("URL contains embedded whitespace")
