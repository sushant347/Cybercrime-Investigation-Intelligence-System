"""
Length-based feature extraction for the Phishing URL Detection Engine.

Computes features derived from the string lengths of various URL
components.  Phishing URLs often exhibit anomalous lengths -- e.g.,
unusually long hostnames, deep paths, or verbose query strings.
"""

from typing import Any

from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.helpers import safe_division
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LengthFeatureExtractor(BaseFeatureExtractor):
    """
    Extract length-based features from parsed URLs.

    Measures the character count of the full URL and each of its
    structural components (hostname, domain, path, query, subdomain,
    filename, fragment, TLD, scheme) as well as aggregate path-segment
    statistics (max and average segment length).

    These features are strong phishing indicators because attackers
    frequently pad URLs with long random strings or deep directory
    structures to obscure the true destination.

    Usage:
        >>> extractor = LengthFeatureExtractor()
        >>> features = extractor.extract(parsed_url)
        >>> print(features["url_length"])
        57
    """

    _FEATURE_NAMES: list[str] = [
        "url_length",
        "hostname_length",
        "domain_length",
        "path_length",
        "query_length",
        "subdomain_length",
        "filename_length",
        "fragment_length",
        "tld_length",
        "scheme_length",
        "max_path_segment_length",
        "avg_path_segment_length",
    ]

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'length'.
        """
        return "length"

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Compute length features for every URL component.

        Args:
            parsed_url: A ``ParsedURL`` instance produced by ``URLParser``.

        Returns:
            Dictionary of 12 length-based features.
        """
        path_segments = parsed_url.path_segments
        segment_lengths = [len(seg) for seg in path_segments] if path_segments else []

        max_seg_len = max(segment_lengths) if segment_lengths else 0
        avg_seg_len = safe_division(
            sum(segment_lengths), len(segment_lengths), default=0.0
        )

        features: dict[str, Any] = {
            "url_length": len(parsed_url.normalized_url),
            "hostname_length": len(parsed_url.hostname),
            "domain_length": len(parsed_url.domain),
            "path_length": len(parsed_url.path),
            "query_length": len(parsed_url.query),
            "subdomain_length": len(parsed_url.subdomain),
            "filename_length": len(parsed_url.filename),
            "fragment_length": len(parsed_url.fragment),
            "tld_length": len(parsed_url.suffix),
            "scheme_length": len(parsed_url.scheme),
            "max_path_segment_length": max_seg_len,
            "avg_path_segment_length": round(avg_seg_len, 4),
        }

        logger.debug(
            "LengthFeatureExtractor: url_length=%d, hostname_length=%d",
            features["url_length"],
            features["hostname_length"],
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of length feature names.

        Returns:
            List of 12 feature name strings.
        """
        return list(self._FEATURE_NAMES)
