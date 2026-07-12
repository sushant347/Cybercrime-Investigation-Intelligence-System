"""
Tests for the URL resolver (src/parser/url_resolver.py).

Tests cover:
- ``is_shortener()`` correctly identifies known shortener domains.
- ``resolve()`` returns a ResolutionResult with correct structure.
- Non-shortener URLs are returned unchanged with ``was_resolved=False``.
- ``resolve_if_needed()`` returns the URL string directly.
- ``ResolutionResult.to_dict()`` includes all expected keys.
"""
from __future__ import annotations

import pytest

from src.parser.url_resolver import URLResolver, ResolutionResult


@pytest.fixture
def resolver() -> URLResolver:
    return URLResolver(timeout=5, max_redirects=5)


class TestIsShortener:
    def test_known_shortener_detected(self, resolver):
        assert resolver.is_shortener("https://bit.ly/abc123") is True

    def test_tinyurl_detected(self, resolver):
        assert resolver.is_shortener("https://tinyurl.com/xyz") is True

    def test_non_shortener_not_detected(self, resolver):
        assert resolver.is_shortener("https://www.google.com") is False

    def test_github_not_shortener(self, resolver):
        assert resolver.is_shortener("https://github.com/user/repo") is False

    def test_empty_string(self, resolver):
        assert resolver.is_shortener("") is False


class TestResolveNonShortener:
    def test_non_shortener_returns_unchanged(self, resolver):
        url = "https://www.example.com/page"
        result = resolver.resolve(url)
        assert result.resolved_url == url
        assert result.was_resolved is False
        assert result.original_url == url

    def test_non_shortener_no_error(self, resolver):
        url = "https://github.com/user/repo"
        result = resolver.resolve(url)
        assert result.error is None


class TestResolutionResult:
    def test_to_dict_keys(self, resolver):
        url = "https://example.com"
        result = resolver.resolve(url)
        d = result.to_dict()
        assert "original_url" in d
        assert "resolved_url" in d
        assert "was_resolved" in d
        assert "redirect_count" in d
        assert "resolution_chain" in d
        assert "error" in d
        assert "elapsed_seconds" in d

    def test_chain_contains_original(self, resolver):
        url = "https://www.google.com"
        result = resolver.resolve(url)
        assert url in result.resolution_chain

    def test_resolved_url_is_string(self, resolver):
        url = "https://github.com"
        result = resolver.resolve(url)
        assert isinstance(result.resolved_url, str)

    def test_redirect_count_non_negative(self, resolver):
        url = "https://www.example.com"
        result = resolver.resolve(url)
        assert result.redirect_count >= 0

    def test_elapsed_non_negative(self, resolver):
        url = "https://example.com"
        result = resolver.resolve(url)
        assert result.elapsed_seconds >= 0.0


class TestResolveIfNeeded:
    def test_returns_string(self, resolver):
        url = "https://www.google.com"
        result = resolver.resolve_if_needed(url)
        assert isinstance(result, str)

    def test_non_shortener_returns_same(self, resolver):
        url = "https://www.bbc.com/news"
        result = resolver.resolve_if_needed(url)
        assert result == url
