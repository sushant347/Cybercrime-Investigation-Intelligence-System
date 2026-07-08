"""
URL resolver for expanding shortened URLs.

The ``URLResolver`` follows redirects for URLs served by known URL-shortening
services and returns the final destination URL, enabling the detection engine
to analyse the true target rather than the obfuscated shortener link.

Fallback: When the resolver cannot follow a redirect (network error, timeout,
or the service is not reachable), the original URL is returned unchanged so
that analysis can still proceed.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass (lightweight, no dependency on heavy data classes)
# ---------------------------------------------------------------------------

class ResolutionResult:
    """Outcome of a URL resolution attempt.

    Attributes:
        original_url: The input URL (possibly shortened).
        resolved_url: The final destination URL after following all redirects.
        was_resolved: ``True`` when the URL was actually followed.
        redirect_count: Number of HTTP redirects followed.
        resolution_chain: Ordered list of all URLs traversed (including the
            original and the final destination).
        error: Error message if resolution failed, otherwise ``None``.
        elapsed_seconds: Time taken for the resolution request.
    """

    def __init__(
        self,
        original_url: str,
        resolved_url: str,
        was_resolved: bool = False,
        redirect_count: int = 0,
        resolution_chain: Optional[list[str]] = None,
        error: Optional[str] = None,
        elapsed_seconds: float = 0.0,
    ) -> None:
        self.original_url = original_url
        self.resolved_url = resolved_url
        self.was_resolved = was_resolved
        self.redirect_count = redirect_count
        self.resolution_chain = resolution_chain or [original_url]
        self.error = error
        self.elapsed_seconds = elapsed_seconds

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {
            "original_url": self.original_url,
            "resolved_url": self.resolved_url,
            "was_resolved": self.was_resolved,
            "redirect_count": self.redirect_count,
            "resolution_chain": self.resolution_chain,
            "error": self.error,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

class URLResolver:
    """Follow HTTP redirects to expand shortened or obfuscated URLs.

    The resolver only attempts to follow redirects when the URL's hostname
    matches a known URL-shortening service (configurable via
    ``settings.threat.url_shorteners``).  For non-shortener URLs the original
    URL is returned immediately as a no-op.

    ``URLResolver`` uses a ``HEAD`` request by default (less bandwidth) and
    falls back to ``GET`` if the server does not honour ``HEAD``.

    Usage::

        resolver = URLResolver()
        result = resolver.resolve("https://bit.ly/abc123")
        print(result.resolved_url)  # https://example.com/real-destination
        print(result.was_resolved)  # True

    Attributes:
        timeout: HTTP request timeout in seconds.
        max_redirects: Maximum number of redirects to follow.
        url_shorteners: Set of known shortener hostnames.
    """

    # User-agent string to avoid being blocked by shorteners
    _USER_AGENT = (
        "Mozilla/5.0 (compatible; PhishingURLDetectionEngine/1.0; "
        "+https://github.com/ciis-project)"
    )

    def __init__(
        self,
        timeout: int = 10,
        max_redirects: int = 10,
    ) -> None:
        """Initialise the URL resolver.

        Args:
            timeout: HTTP request timeout in seconds.
            max_redirects: Maximum number of HTTP redirects to follow before
                aborting (prevents redirect loops).
        """
        settings = get_settings()
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.url_shorteners: set[str] = set(settings.threat.url_shorteners)

        logger.debug(
            "URLResolver initialised: timeout=%ds, max_redirects=%d, "
            "known shorteners=%d",
            timeout,
            max_redirects,
            len(self.url_shorteners),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_shortener(self, url: str) -> bool:
        """Check whether a URL uses a known URL-shortening service.

        Args:
            url: URL string to check.

        Returns:
            ``True`` if the URL's hostname (or parent domain) is in the
            known shortener list.
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url if "://" in url else f"http://{url}")
            hostname = (parsed.hostname or "").lower()
            return any(
                hostname == s or hostname.endswith("." + s)
                for s in self.url_shorteners
            )
        except Exception:
            return False

    def resolve(self, url: str) -> ResolutionResult:
        """Expand a (possibly shortened) URL to its final destination.

        Only follows redirects for URLs served by known shortening services.
        For other URLs, returns immediately with ``was_resolved=False``.

        Args:
            url: The URL to resolve.

        Returns:
            ``ResolutionResult`` with the resolved (or original) URL.
        """
        if not self.is_shortener(url):
            logger.debug("URL is not a known shortener, skipping resolution: %s", url[:60])
            return ResolutionResult(
                original_url=url,
                resolved_url=url,
                was_resolved=False,
            )

        logger.info("Resolving shortened URL: %s", url[:60])
        return self._follow_redirects(url)

    def resolve_if_needed(self, url: str) -> str:
        """Convenience wrapper: return the resolved URL string directly.

        If resolution fails or the URL is not a shortener, the original URL
        is returned unchanged.

        Args:
            url: URL string to resolve.

        Returns:
            Resolved (or original) URL string.
        """
        return self.resolve(url).resolved_url

    # ------------------------------------------------------------------
    # Internal redirect-following logic
    # ------------------------------------------------------------------

    def _follow_redirects(self, url: str) -> ResolutionResult:
        """Follow HTTP redirects and return the final destination.

        First attempts a ``HEAD`` request (less bandwidth).  If the server
        responds with a 405 Method Not Allowed the method falls back to
        ``GET`` with ``stream=True`` so the response body is not downloaded.

        Args:
            url: Starting URL to resolve.

        Returns:
            ``ResolutionResult`` with chain and metadata.
        """
        start = time.perf_counter()
        chain: list[str] = [url]

        session = requests.Session()
        session.max_redirects = self.max_redirects
        session.headers.update({"User-Agent": self._USER_AGENT})

        try:
            # Try HEAD first to avoid downloading response bodies
            response = session.head(
                url,
                allow_redirects=True,
                timeout=self.timeout,
            )

            if response.status_code == 405:
                # Server does not allow HEAD — fall back to GET with streaming
                response = session.get(
                    url,
                    allow_redirects=True,
                    timeout=self.timeout,
                    stream=True,
                )
                response.close()

            # Capture the redirect chain
            for r in response.history:
                if r.headers.get("Location"):
                    chain.append(r.headers["Location"])

            final_url = response.url
            if final_url not in chain:
                chain.append(final_url)

            redirect_count = len(response.history)
            elapsed = time.perf_counter() - start

            was_resolved = final_url.rstrip("/") != url.rstrip("/")

            logger.info(
                "Resolved %s → %s (%d redirects in %.2fs)",
                url[:50],
                final_url[:50],
                redirect_count,
                elapsed,
            )

            return ResolutionResult(
                original_url=url,
                resolved_url=final_url,
                was_resolved=was_resolved,
                redirect_count=redirect_count,
                resolution_chain=chain,
                elapsed_seconds=elapsed,
            )

        except requests.exceptions.TooManyRedirects as exc:
            elapsed = time.perf_counter() - start
            error_msg = f"Too many redirects (>{self.max_redirects}): {exc}"
            logger.warning("Resolution failed for %s: %s", url[:60], error_msg)
            return ResolutionResult(
                original_url=url,
                resolved_url=url,
                was_resolved=False,
                resolution_chain=chain,
                error=error_msg,
                elapsed_seconds=elapsed,
            )

        except requests.exceptions.Timeout as exc:
            elapsed = time.perf_counter() - start
            error_msg = f"Request timed out after {self.timeout}s: {exc}"
            logger.warning("Resolution timed out for %s", url[:60])
            return ResolutionResult(
                original_url=url,
                resolved_url=url,
                was_resolved=False,
                resolution_chain=chain,
                error=error_msg,
                elapsed_seconds=elapsed,
            )

        except requests.exceptions.ConnectionError as exc:
            elapsed = time.perf_counter() - start
            error_msg = f"Connection error: {exc}"
            logger.warning("Connection error resolving %s: %s", url[:60], exc)
            return ResolutionResult(
                original_url=url,
                resolved_url=url,
                was_resolved=False,
                resolution_chain=chain,
                error=error_msg,
                elapsed_seconds=elapsed,
            )

        except Exception as exc:
            elapsed = time.perf_counter() - start
            error_msg = f"Unexpected error: {exc}"
            logger.exception("Unexpected resolution error for %s", url[:60])
            return ResolutionResult(
                original_url=url,
                resolved_url=url,
                was_resolved=False,
                resolution_chain=chain,
                error=error_msg,
                elapsed_seconds=elapsed,
            )

        finally:
            session.close()
