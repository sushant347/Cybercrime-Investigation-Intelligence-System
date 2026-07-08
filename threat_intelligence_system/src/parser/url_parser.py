"""
URL parsing module for the Phishing URL Detection Engine.

Decomposes URLs into detailed structural components that feed into the
feature engineering pipeline.  Every parsed attribute is stored in an
immutable ``ParsedURL`` dataclass so that downstream extractors can
consume the data without re-parsing.
"""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlparse

import tldextract

from src.utils.helpers import ensure_scheme, normalize_url
from src.utils.exceptions import URLParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ParsedURL:
    """
    Structured representation of a fully parsed URL.

    This dataclass holds every decomposition product of a URL -- from
    the scheme down to individual path segments and query parameters --
    so that feature extractors never need to re-parse the original string.

    Attributes:
        raw_url: The original URL string before any processing.
        normalized_url: The URL after canonical normalization.
        scheme: URL scheme (e.g., 'http', 'https').
        hostname: Full hostname including subdomains (e.g., 'www.sub.example.com').
        registered_domain: Registered domain including the TLD (e.g., 'example.com').
        domain: Second-level domain label only (e.g., 'example').
        subdomain: Subdomain portion of the hostname (e.g., 'www.sub').
        suffix: Top-level domain / public suffix (e.g., 'com', 'co.uk').
        port: Explicit port number, or None if not specified.
        path: URL path component (e.g., '/dir/file.html').
        query: Raw query string (e.g., 'key=value&foo=bar').
        fragment: URL fragment / anchor (e.g., 'section-2').
        directory_depth: Number of directories in the path.
        filename: Terminal path component if it looks like a file.
        file_extension: Extension of the filename (e.g., 'html').
        query_params: Parsed query parameters as a multi-value dict.
        query_param_count: Number of distinct query parameter keys.
        subdomain_parts: Individual subdomain labels (e.g., ['www', 'sub']).
        subdomain_count: Number of subdomain labels.
        path_segments: Non-empty path segments split by '/'.
        path_segment_count: Number of path segments.
        has_port: Whether an explicit port was specified.
        has_query: Whether a query string is present.
        has_fragment: Whether a fragment is present.
        has_at_symbol: Whether the URL contains an '@' symbol.
        has_double_slash_in_path: Whether the path contains '//'.
        is_ip_based: Whether the hostname is an IP address.
        url_tokens: Tokens produced by splitting the URL on special characters.
    """

    raw_url: str = ""
    normalized_url: str = ""
    scheme: str = ""
    hostname: str = ""
    registered_domain: str = ""
    domain: str = ""
    subdomain: str = ""
    suffix: str = ""
    port: int | None = None
    path: str = ""
    query: str = ""
    fragment: str = ""
    directory_depth: int = 0
    filename: str = ""
    file_extension: str = ""
    query_params: dict[str, list[str]] = field(default_factory=dict)
    query_param_count: int = 0
    subdomain_parts: list[str] = field(default_factory=list)
    subdomain_count: int = 0
    path_segments: list[str] = field(default_factory=list)
    path_segment_count: int = 0
    has_port: bool = False
    has_query: bool = False
    has_fragment: bool = False
    has_at_symbol: bool = False
    has_double_slash_in_path: bool = False
    is_ip_based: bool = False
    url_tokens: list[str] = field(default_factory=list)


class URLParser:
    """
    Full-featured URL parser for the phishing detection pipeline.

    Decomposes a raw URL string into a rich ``ParsedURL`` dataclass
    containing hostname details (via ``tldextract``), path analysis,
    query parameter parsing, and tokenization.

    Usage:
        >>> parser = URLParser()
        >>> parsed = parser.parse("https://sub.example.com:8080/dir/file.html?q=1#top")
        >>> print(parsed.domain)
        'example'
        >>> print(parsed.subdomain_parts)
        ['sub']
    """

    # Pattern used to tokenize URLs by splitting on non-alphanumeric chars
    _TOKEN_PATTERN: re.Pattern = re.compile(r"[^a-zA-Z0-9]+")

    # Pattern to match IP-address hostnames (IPv4)
    _IPV4_PATTERN: re.Pattern = re.compile(
        r"^(\d{1,3}\.){3}\d{1,3}$"
    )

    # Pattern to match bracket-enclosed IPv6
    _IPV6_PATTERN: re.Pattern = re.compile(r"^\[.*\]$")

    def parse(self, url: str) -> ParsedURL:
        """
        Parse a URL string into a fully-populated ``ParsedURL``.

        The URL is first normalized, then decomposed using ``urllib.parse``
        and ``tldextract``.  All derived fields (tokens, segments, depths)
        are computed eagerly so downstream consumers see no parsing cost.

        Args:
            url: Raw URL string.

        Returns:
            ParsedURL with all fields populated.

        Raises:
            URLParsingError: If the URL cannot be parsed at all.
        """
        if not url or not url.strip():
            raise URLParsingError(url=url, reason="URL is empty or whitespace-only")

        raw_url = url.strip()

        try:
            url_with_scheme = ensure_scheme(raw_url)
            normalized = normalize_url(raw_url)
            parsed = urlparse(url_with_scheme)
        except Exception as exc:
            raise URLParsingError(
                url=raw_url,
                reason=f"stdlib parsing failed: {exc}",
            ) from exc

        # Extract domain parts via tldextract
        try:
            extracted = tldextract.extract(url_with_scheme)
        except Exception as exc:
            raise URLParsingError(
                url=raw_url,
                reason=f"tldextract failed: {exc}",
            ) from exc

        hostname = (parsed.hostname or "").lower()
        scheme = (parsed.scheme or "http").lower()
        domain = extracted.domain or ""
        subdomain = extracted.subdomain or ""
        suffix = extracted.suffix or ""
        registered_domain = extracted.registered_domain or ""

        # Port
        port = parsed.port
        has_port = port is not None

        # Path analysis
        path = parsed.path or ""
        path_segments = [seg for seg in path.split("/") if seg]
        path_segment_count = len(path_segments)
        directory_depth = self._compute_directory_depth(path)
        filename, file_extension = self._extract_filename(path)

        # Query analysis
        query = parsed.query or ""
        has_query = bool(query)
        try:
            query_params = parse_qs(query, keep_blank_values=True)
        except Exception:
            query_params = {}
        query_param_count = len(query_params)

        # Fragment
        fragment = parsed.fragment or ""
        has_fragment = bool(fragment)

        # Subdomain decomposition
        subdomain_parts = [part for part in subdomain.split(".") if part]
        subdomain_count = len(subdomain_parts)

        # Boolean checks
        has_at_symbol = "@" in raw_url
        has_double_slash_in_path = "//" in path

        # IP-based hostname detection
        is_ip_based = self._is_ip_hostname(hostname)

        # Tokenize the URL
        url_tokens = self._tokenize(url_with_scheme)

        parsed_url = ParsedURL(
            raw_url=raw_url,
            normalized_url=normalized,
            scheme=scheme,
            hostname=hostname,
            registered_domain=registered_domain,
            domain=domain,
            subdomain=subdomain,
            suffix=suffix,
            port=port,
            path=path,
            query=query,
            fragment=fragment,
            directory_depth=directory_depth,
            filename=filename,
            file_extension=file_extension,
            query_params=query_params,
            query_param_count=query_param_count,
            subdomain_parts=subdomain_parts,
            subdomain_count=subdomain_count,
            path_segments=path_segments,
            path_segment_count=path_segment_count,
            has_port=has_port,
            has_query=has_query,
            has_fragment=has_fragment,
            has_at_symbol=has_at_symbol,
            has_double_slash_in_path=has_double_slash_in_path,
            is_ip_based=is_ip_based,
            url_tokens=url_tokens,
        )

        logger.debug(
            "Parsed URL '%s' -> domain=%s, subdomain_count=%d, depth=%d",
            raw_url[:80],
            domain,
            subdomain_count,
            directory_depth,
        )

        return parsed_url

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_directory_depth(path: str) -> int:
        """
        Compute the directory depth of a URL path.

        Counts the number of '/' separated directory levels, excluding
        the trailing filename component.

        Args:
            path: The URL path string (e.g., '/a/b/c/file.html').

        Returns:
            Integer depth of directories (e.g., 3 for '/a/b/c/file.html').
        """
        if not path or path == "/":
            return 0
        segments = [seg for seg in path.split("/") if seg]
        if not segments:
            return 0
        # If the last segment looks like a file, subtract 1
        last = segments[-1]
        if "." in last and not last.startswith("."):
            return max(0, len(segments) - 1)
        return len(segments)

    @staticmethod
    def _extract_filename(path: str) -> tuple[str, str]:
        """
        Extract filename and extension from a URL path.

        Uses ``PurePosixPath`` for platform-agnostic path decomposition.

        Args:
            path: The URL path string.

        Returns:
            Tuple of (filename, extension) where extension lacks the dot.
            Returns ('', '') when no file-like component is found.
        """
        if not path or path == "/":
            return "", ""

        posix = PurePosixPath(path)
        name = posix.name
        if not name:
            return "", ""

        # Only treat as filename if it contains a dot (e.g., file.html)
        if "." in name and not name.startswith("."):
            ext = posix.suffix.lstrip(".")
            return name, ext

        return "", ""

    def _is_ip_hostname(self, hostname: str) -> bool:
        """
        Determine if a hostname is an IP address.

        Handles IPv4 dotted-quad notation and bracket-enclosed IPv6
        literals.

        Args:
            hostname: The hostname string to evaluate.

        Returns:
            True if the hostname is an IP address.
        """
        if not hostname:
            return False
        if self._IPV4_PATTERN.match(hostname):
            return True
        if self._IPV6_PATTERN.match(hostname):
            return True
        # Bare IPv6 (rare in URLs but possible)
        if ":" in hostname and not hostname.startswith("["):
            return True
        return False

    def _tokenize(self, url: str) -> list[str]:
        """
        Tokenize a URL by splitting on special characters.

        Produces a list of alphanumeric tokens that downstream NLP
        and lexical feature extractors can consume.

        Args:
            url: The full URL string.

        Returns:
            List of non-empty lowercase tokens.
        """
        tokens = self._TOKEN_PATTERN.split(url)
        return [t.lower() for t in tokens if t]
