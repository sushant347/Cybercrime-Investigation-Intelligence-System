"""Advanced domain analysis with investigator-friendly explanations.

Adds subdomain depth, Shannon entropy / random-domain scoring, suspicious
TLD detection, Unicode/homograph attack detection, typosquatting and brand
impersonation checks. Every numeric signal is paired with a plain-English
sentence an investigator can quote in a report.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List

SUSPICIOUS_TLDS = frozenset({
    "top", "xyz", "icu", "cyou", "rest", "monster", "click", "link", "gq",
    "tk", "ml", "cf", "ga", "zip", "mov", "loan", "work", "country", "cam",
})

#: Brands most impersonated in Nepali/global phishing (extend freely).
PROTECTED_BRANDS = (
    "paypal", "google", "facebook", "microsoft", "apple", "amazon",
    "netflix", "instagram", "whatsapp", "esewa", "khalti", "imepay",
    "nabil", "nicasia", "globalime", "himalayanbank", "nepalbank",
)

_MIXED_SCRIPT = re.compile(r"[^\x00-\x7f]")


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = {ch: text.count(ch) for ch in set(text)}
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _edit_distance_leq(a: str, b: str, limit: int = 1) -> bool:
    """True when Levenshtein(a, b) <= limit (fast band check)."""
    if abs(len(a) - len(b)) > limit:
        return False
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        if min(current) > limit:
            return False
        previous = current
    return previous[-1] <= limit


@dataclass
class DomainAnalysis:
    """Signals + explanations for one domain."""

    domain: str
    subdomain_depth: int = 0
    entropy: float = 0.0
    random_domain_score: float = 0.0     # 0-1: likelihood of DGA-style name
    suspicious_tld: bool = False
    unicode_attack: bool = False
    homograph_suspect: bool = False
    impersonated_brand: str = ""
    typosquat_of: str = ""
    risk_points: int = 0                 # contribution to reputation penalty
    explanations: List[str] = field(default_factory=list)


class DomainAnalyzer:
    """Deterministic, offline domain analysis."""

    def analyze(self, domain: str) -> DomainAnalysis:
        result = DomainAnalysis(domain=domain.lower().rstrip("."))
        labels = result.domain.split(".")
        core = labels[-2] if len(labels) >= 2 else labels[0]
        tld = labels[-1] if len(labels) >= 2 else ""

        result.subdomain_depth = max(0, len(labels) - 2)
        if result.subdomain_depth >= 3:
            result.risk_points += 10
            result.explanations.append(
                "The address hides its real identity behind an unusually deep "
                "chain of subdomains - a common trick to make a fake site look official.")

        result.entropy = round(_entropy(core), 2)
        result.random_domain_score = round(
            min(1.0, max(0.0, (result.entropy - 2.6) / 1.6)), 2)
        if result.random_domain_score >= 0.6 and len(core) >= 8:
            result.risk_points += 15
            result.explanations.append(
                "The domain name contains a highly random character structure, "
                "which is commonly associated with automatically generated "
                "phishing or malware domains.")

        if tld in SUSPICIOUS_TLDS:
            result.suspicious_tld = True
            result.risk_points += 15
            result.explanations.append(
                f"The site uses the '.{tld}' ending, a low-cost domain zone "
                "frequently abused for phishing campaigns.")

        if _MIXED_SCRIPT.search(result.domain):
            result.unicode_attack = True
            result.homograph_suspect = True
            result.risk_points += 20
            result.explanations.append(
                "The address contains non-Latin characters designed to look like "
                "ordinary letters - a homograph attack that visually imitates a "
                "legitimate website.")
        else:
            folded = unicodedata.normalize("NFKC", result.domain)
            if folded != result.domain:
                result.homograph_suspect = True
                result.risk_points += 10

        flattened = core.replace("-", "")
        for brand in PROTECTED_BRANDS:
            if brand == flattened or brand == core:
                break  # exact brand domain: not impersonation of itself
            if brand in flattened and core != brand:
                result.impersonated_brand = brand
                result.risk_points += 30
                result.explanations.append(
                    f"The domain embeds the brand name '{brand}' although it is "
                    "not the brand's official domain - a strong sign of brand "
                    "impersonation.")
                break
            if _edit_distance_leq(flattened, brand, 1) and flattened != brand:
                result.typosquat_of = brand
                result.risk_points += 30
                result.explanations.append(
                    f"The domain is only one letter away from '{brand}' - a "
                    "typosquatting pattern that catches users who mistype the "
                    "real address.")
                break

        return result
