"""
Brand-impersonation feature extraction for the Phishing URL Detection Engine.

Detects whether a URL attempts to impersonate a well-known brand by
checking for brand names in domain, subdomain, and path components,
and computing Levenshtein-distance-based similarity scores.
"""

from typing import Any

import Levenshtein
import tldextract

from src.config.settings import get_settings
from src.feature_engineering.base import BaseFeatureExtractor
from src.parser.url_parser import ParsedURL
from src.utils.helpers import safe_division
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BrandFeatureExtractor(BaseFeatureExtractor):
    """
    Extract brand-impersonation features from parsed URLs.

    Phishing attackers frequently embed well-known brand names (e.g.,
    'paypal', 'apple', 'microsoft') in subdomains, paths, or slightly
    misspelled domains to trick victims.  This extractor detects such
    patterns by:
        1. Exact substring matching of brand names in multiple URL components.
        2. Levenshtein edit distance between the domain and each brand.
        3. Normalized similarity scoring.
        4. Typosquatting heuristic (edit distance 1-2 from a brand).
        5. Registered domain check against official brand domains configuration.

    Computes 6 numeric features + extra metadata features.
    """

    _FEATURE_NAMES: list[str] = [
        "brand_in_domain",
        "brand_in_subdomain",
        "brand_in_path",
        "brand_levenshtein_distance",
        "brand_similarity_score",
        "is_typosquatting",
    ]

    # Maximum edit distance to consider a domain as typosquatting
    _TYPOSQUATTING_THRESHOLD: int = 2

    # Brands with names at or below this length require token-boundary
    # matching (e.g. 'ups' must not match inside 'groups' or 'startups').
    _SHORT_BRAND_LENGTH: int = 4

    def __init__(self) -> None:
        """Initialize with the official brand domains registry from settings."""
        settings = get_settings()
        self._official_domains: dict[str, list[str]] = settings.threat.official_domains
        self._known_brands: list[str] = list(self._official_domains.keys())
        logger.debug(
            "BrandFeatureExtractor initialized with %d known brands",
            len(self._known_brands),
        )

    @property
    def name(self) -> str:
        """Return the extractor name.

        Returns:
            The string 'brand'.
        """
        return "brand"

    def _brand_matches(self, brand: str, text: str) -> bool:
        """Check whether *brand* appears in *text* as an impersonation signal.

        Brands longer than ``_SHORT_BRAND_LENGTH`` use plain substring
        matching (catches concatenations like 'paypalverify').  Short brand
        names require token-boundary matching -- the characters adjacent to
        the match must be non-alphabetic -- so that e.g. 'ups' does not
        match inside 'groups' or 'startups'.

        Args:
            brand: Lowercase brand keyword.
            text: Lowercase URL component to search.

        Returns:
            True if the brand is considered present in the text.
        """
        if not brand or not text:
            return False

        if len(brand) > self._SHORT_BRAND_LENGTH:
            return brand in text

        # Token-boundary matching for short brands
        start = 0
        while True:
            idx = text.find(brand, start)
            if idx == -1:
                return False
            before_ok = idx == 0 or not text[idx - 1].isalpha()
            after_idx = idx + len(brand)
            after_ok = after_idx >= len(text) or not text[after_idx].isalpha()
            if before_ok and after_ok:
                return True
            start = idx + 1

    def extract(self, parsed_url: ParsedURL) -> dict[str, Any]:
        """
        Compute brand-impersonation features for a parsed URL.

        Args:
            parsed_url: A ``ParsedURL`` instance.

        Returns:
            Dictionary of brand-impersonation features.
        """
        domain_lower = parsed_url.domain.lower()
        subdomain_lower = parsed_url.subdomain.lower()
        path_lower = parsed_url.path.lower()
        query_lower = parsed_url.query.lower()
        
        # Safe extraction of filename if it exists
        filename_lower = getattr(parsed_url, "filename", "").lower()

        # Extract registered domain safely using tldextract to prevent hostname-only false flags
        extracted = tldextract.extract(parsed_url.normalized_url)
        registered_domain = (extracted.registered_domain or "").lower()

        brand_detected = None
        brand_location = "none"
        official_domain_match = False

        brand_in_domain = False
        brand_in_subdomain = False
        brand_in_path = False

        # Scan for brand names
        for brand in self._known_brands:
            brand_official_list = self._official_domains.get(brand, [])

            # 1. Exact registered domain match check
            if registered_domain in brand_official_list:
                official_domain_match = True
                brand_detected = brand
                brand_location = "domain"
                break

            # 2. Impersonation checks (substring presence in non-official domains).
            #    Short brand names use token-boundary matching to avoid false
            #    positives such as 'ups' matching inside 'groups'.
            locations = []
            if self._brand_matches(brand, registered_domain):
                locations.append("domain")
                brand_in_domain = True
            if self._brand_matches(brand, subdomain_lower):
                locations.append("subdomain")
                brand_in_subdomain = True
            if self._brand_matches(brand, path_lower):
                locations.append("path")
                brand_in_path = True
            if self._brand_matches(brand, filename_lower):
                locations.append("filename")
            if self._brand_matches(brand, query_lower):
                locations.append("query")

            if locations:
                brand_detected = brand
                # Determine primary brand location (hierarchy: domain > subdomain > path > filename > query)
                for loc in ["domain", "subdomain", "path", "filename", "query"]:
                    if loc in locations:
                        brand_location = loc
                        break
                break

        # Find closest brand by Levenshtein distance to the second-level domain (SLD)
        closest_brand = ""
        min_distance = float("inf")

        for brand in self._known_brands:
            dist = Levenshtein.distance(domain_lower, brand)
            if dist < min_distance:
                min_distance = dist
                closest_brand = brand

        # Compute similarity score
        if min_distance == float("inf"):
            min_distance = -1
            brand_similarity_score = 0.0
        else:
            max_len = max(len(domain_lower), len(closest_brand), 1)
            brand_similarity_score = 1.0 - safe_division(
                min_distance, max_len, default=1.0
            )

        # Typosquatting: domain is very close to a brand but not exact and not in a brand
        is_typosquatting = (
            0 < min_distance <= self._TYPOSQUATTING_THRESHOLD
            and not brand_in_domain
        )

        # 3. Suppress all phishing brand features if it matches the official domain
        if official_domain_match:
            brand_in_domain = False
            brand_in_subdomain = False
            brand_in_path = False
            is_typosquatting = False
            brand_similarity_score = 0.0

        features: dict[str, Any] = {
            "brand_in_domain": int(brand_in_domain),
            "brand_in_subdomain": int(brand_in_subdomain),
            "brand_in_path": int(brand_in_path),
            "brand_levenshtein_distance": int(min_distance),
            "brand_similarity_score": round(brand_similarity_score, 4),
            "is_typosquatting": int(is_typosquatting),
            
            # New metadata features (v2.0)
            "brand_detected": brand_detected,
            "brand_location": brand_location,
            "brand_similarity": round(brand_similarity_score, 4) if brand_detected else 0.0,
            "official_domain_match": official_domain_match,
            "closest_brand": closest_brand,
        }

        logger.debug(
            "BrandFeatureExtractor: brand=%s location=%s official=%s typosquatting=%s",
            brand_detected,
            brand_location,
            official_domain_match,
            is_typosquatting,
        )

        return features

    def get_feature_names(self) -> list[str]:
        """
        Return the ordered list of numeric brand feature names.
        Does not include metadata features to maintain ML schema backward compatibility.

        Returns:
            List of 6 feature name strings.
        """
        return list(self._FEATURE_NAMES)
