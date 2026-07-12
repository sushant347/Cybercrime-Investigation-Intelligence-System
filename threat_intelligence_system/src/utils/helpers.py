"""
Shared utility functions for the Phishing URL Detection Engine.

Provides URL normalization, timing decorators, safe HTTP requests,
and other cross-cutting helper functions.
"""

import functools
import hashlib
import re
import time
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse, unquote

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize a URL to a canonical form for deduplication and comparison.

    Normalization steps:
    1. Strip whitespace
    2. Decode percent-encoded characters
    3. Add scheme if missing (default: http://)
    4. Lowercase the scheme and hostname
    5. Remove default ports (80 for http, 443 for https)
    6. Remove trailing slash from path (unless it IS the path)
    7. Remove fragment

    Args:
        url: Raw URL string.

    Returns:
        Normalized URL string.

    Example:
        >>> normalize_url("  HTTP://WWW.EXAMPLE.COM:80/Path?q=1#frag  ")
        'http://www.example.com/Path?q=1'
    """
    url = url.strip()

    if not url:
        return ""

    # Decode percent-encoded characters
    url = unquote(url)

    # Add scheme if missing
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", url):
        url = "http://" + url

    try:
        parsed = urlparse(url)
    except Exception:
        return url

    # Lowercase scheme and hostname
    scheme = (parsed.scheme or "http").lower()
    hostname = (parsed.hostname or "").lower()

    # Reconstruct netloc (handle port)
    port = parsed.port
    default_ports = {"http": 80, "https": 443}
    if port and port == default_ports.get(scheme):
        port = None

    # Handle IPv6 hostnames (bracket wrapping)
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    if port:
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    # Preserve username:password if present
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo += f":{parsed.password}"
        netloc = f"{userinfo}@{netloc}"

    # Normalize path
    path = parsed.path
    if path and path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Remove fragment, preserve query
    normalized = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))

    return normalized


def ensure_scheme(url: str) -> str:
    """
    Ensure a URL has a scheme prefix.

    If the URL has no scheme, prepend 'http://'.

    Args:
        url: URL string that may or may not have a scheme.

    Returns:
        URL string guaranteed to have a scheme.
    """
    url = url.strip()
    if not url:
        return url
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", url):
        return "http://" + url
    return url


def url_hash(url: str) -> str:
    """
    Generate a SHA-256 hash of a normalized URL.

    Useful for deduplication and quick lookups.

    Args:
        url: URL string to hash.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def timing_decorator(func: Callable) -> Callable:
    """
    Decorator that logs the execution time of a function.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with timing instrumentation.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.debug(
            "%s.%s completed in %.3f seconds",
            func.__module__,
            func.__qualname__,
            elapsed,
        )
        return result
    return wrapper


def safe_request(
    url: str,
    method: str = "GET",
    timeout: int = 10,
    max_retries: int = 3,
    **kwargs: Any,
) -> requests.Response | None:
    """
    Make an HTTP request with retry logic and error handling.

    Args:
        url: Target URL.
        method: HTTP method (GET, POST, etc.).
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        **kwargs: Additional arguments passed to requests.request().

    Returns:
        Response object on success, None on failure.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            logger.warning(
                "Request to %s timed out (attempt %d/%d)",
                url, attempt, max_retries,
            )
        except requests.exceptions.HTTPError as e:
            logger.warning(
                "HTTP error for %s: %s (attempt %d/%d)",
                url, e, attempt, max_retries,
            )
            if e.response is not None and e.response.status_code < 500:
                # Client error -- don't retry
                return None
        except requests.exceptions.ConnectionError:
            logger.warning(
                "Connection error for %s (attempt %d/%d)",
                url, attempt, max_retries,
            )
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Request error for %s: %s (attempt %d/%d)",
                url, e, attempt, max_retries,
            )
            return None

        if attempt < max_retries:
            wait = 2 ** (attempt - 1)
            time.sleep(wait)

    logger.error("All %d attempts failed for %s", max_retries, url)
    return None


def chunked_iterable(iterable: list, chunk_size: int) -> list[list]:
    """
    Split an iterable into chunks of the specified size.

    Args:
        iterable: List to split.
        chunk_size: Maximum size of each chunk.

    Returns:
        List of sub-lists.
    """
    return [iterable[i:i + chunk_size] for i in range(0, len(iterable), chunk_size)]


def safe_division(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Perform division with zero-division protection.

    Args:
        numerator: The numerator.
        denominator: The denominator.
        default: Value to return if denominator is zero.

    Returns:
        Result of division, or default if denominator is zero.
    """
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value to the specified range.

    Args:
        value: Value to clamp.
        min_val: Minimum bound.
        max_val: Maximum bound.

    Returns:
        Clamped value.
    """
    return max(min_val, min(max_val, value))
