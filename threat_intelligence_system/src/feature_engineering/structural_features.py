"""
Structural feature extraction for the Phishing URL Detection Engine.

Captures the structural properties of a URL -- subdomain depth,
directory depth, presence/absence of optional URL components -- that
are strong indicators of phishing activity.
"""

from typing import Any

from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StructuralFeatureExtractor(BaseFeatureExtractor):
    """
    Extract structural features from parsed URLs.

    Structural features describe the *shape* of a URL rather than
    its character content.  Key indicators include:
        - Deep subdomain nesting (e.g., ``a.b.c.example.com``).
        - Deep directory paths.
        - Presence of ports, query strings, fragments, or ``@`` symbols.
        - Use of ``www`` prefix.

    Computes 11 binary and integer features.

    Usage:
        >>> extractor = StructuralFeatureExtractor()
        >>> features = extractor.extract(parsed_url)
        >>> print(features["subdomain_count"])
        2
    """

    _FEATURE_NAMES: list[str] = [
        "subdomain_count",
        "directory_depth",
        "has_port",
        "has_query",
        "has_fragment",
        "has_at_symbol",
        "has_double_slash",
        "query_param_count",
        "has_file_extension",
        "path_segment_count",
        "has_www",
    ]

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'structural'.
        """
        return "structural"

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Compute structural features for a parsed URL.

        Args:
            parsed_url: A ``ParsedURL`` instance.

        Returns:
            Dictionary of 11 structural features.
        """
        has_www = parsed_url.hostname.startswith("www.")

        features: dict[str, Any] = {
            "subdomain_count": parsed_url.subdomain_count,
            "directory_depth": parsed_url.directory_depth,
            "has_port": int(parsed_url.has_port),
            "has_query": int(parsed_url.has_query),
            "has_fragment": int(parsed_url.has_fragment),
            "has_at_symbol": int(parsed_url.has_at_symbol),
            "has_double_slash": int(parsed_url.has_double_slash_in_path),
            "query_param_count": parsed_url.query_param_count,
            "has_file_extension": int(bool(parsed_url.file_extension)),
            "path_segment_count": parsed_url.path_segment_count,
            "has_www": int(has_www),
        }

        logger.debug(
            "StructuralFeatureExtractor: subdomain_count=%d, depth=%d, has_port=%d",
            features["subdomain_count"],
            features["directory_depth"],
            features["has_port"],
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of structural feature names.

        Returns:
            List of 11 feature name strings.
        """
        return list(self._FEATURE_NAMES)
