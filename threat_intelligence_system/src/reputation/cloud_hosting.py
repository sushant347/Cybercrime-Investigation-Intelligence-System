"""Cloud-hosting awareness for phishing reputation (additive, offline).

Legitimate services (GitHub Pages, Netlify, Vercel, Firebase, S3, ...) host
enormous amounts of benign content, so being cloud-hosted is NOT malicious by
itself. This detector therefore:

* identifies the hosting provider from the URL,
* classifies the URL as cloud-hosted (informational), and
* raises suspicion ONLY when cloud hosting is combined with phishing signals
  (login/financial keywords, brand impersonation, suspicious paths/subdomains).

Every finding is explainable. The detector is pure/offline (no network) and
never raises - it degrades to "not cloud-hosted" on any parsing problem.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

#: provider name -> host-suffix fingerprints that identify it.
CLOUD_PROVIDERS: Dict[str, tuple] = {
    "GitHub Pages": ("github.io", "githubusercontent.com"),
    "Netlify": ("netlify.app", "netlify.com"),
    "Vercel": ("vercel.app",),
    "Firebase": ("web.app", "firebaseapp.com"),
    "Backblaze": ("backblazeb2.com",),
    "Dropbox": ("dropbox.com", "dropboxusercontent.com"),
    "Google Drive": ("drive.google.com", "docs.google.com"),
    "Cloudflare Pages": ("pages.dev",),
    "Azure Blob": ("blob.core.windows.net", "azurewebsites.net", "azureedge.net"),
    "Amazon S3": ("s3.amazonaws.com", "amazonaws.com"),
    "DigitalOcean Spaces": ("digitaloceanspaces.com",),
    "Render": ("onrender.com",),
    "Railway": ("up.railway.app", "railway.app"),
    "CloudFront": ("cloudfront.net",),
    "Weebly": ("weebly.com",),
    "Glitch": ("glitch.me",),
}

#: Phishing-context signals that make cloud hosting suspicious.
_LOGIN_WORDS = ("login", "signin", "sign-in", "log-in", "account", "verify",
                "verification", "secure", "auth", "authenticate", "session",
                "password", "credential", "unlock", "confirm", "webscr")
_FINANCIAL_WORDS = ("bank", "paypal", "wallet", "esewa", "khalti", "imepay",
                    "payment", "billing", "invoice", "refund", "card", "otp",
                    "swift", "transfer")
_BRAND_WORDS = ("paypal", "google", "facebook", "microsoft", "apple", "amazon",
                "netflix", "instagram", "whatsapp", "office365", "outlook",
                "esewa", "khalti", "imepay", "nabil", "nicasia")

_HOST = re.compile(r"^(?:https?://)?([^/:?#]+)", re.IGNORECASE)


@dataclass
class CloudHostingResult:
    """Explainable cloud-hosting assessment for one URL."""

    is_cloud_hosted: bool = False
    provider: str = ""
    suspicious_context: bool = False
    risk_points: int = 0          # only > 0 when cloud + phishing signals
    signals: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CloudHostingDetector:
    """Detects cloud hosting and its phishing context (rule-based, explainable)."""

    def __init__(self, brands: Optional[tuple] = None) -> None:
        self._brands = brands or _BRAND_WORDS

    def analyze(self, url: str, domain_analysis: Optional[Dict[str, Any]] = None
                ) -> CloudHostingResult:
        """Assess whether ``url`` is cloud-hosted and, if so, how suspicious."""
        result = CloudHostingResult()
        host = self._host(url)
        if not host:
            return result

        provider = self._provider_for(host)
        if not provider:
            return result  # not a recognised cloud host - stays benign here

        result.is_cloud_hosted = True
        result.provider = provider
        result.reasons.append(
            f"Hosted on {provider}, a legitimate cloud/hosting service "
            "(benign by itself).")

        lowered = url.lower()
        # Contextual phishing signals - each is explainable.
        if any(w in lowered for w in _LOGIN_WORDS):
            result.signals.append("login/credential keywords in URL")
        if any(w in lowered for w in _FINANCIAL_WORDS):
            result.signals.append("financial keywords in URL")
        brand = next((b for b in self._brands if b in lowered), "")
        if brand:
            result.signals.append(f"brand name '{brand}' embedded in URL")
        # Reuse existing domain-analysis findings when supplied (no re-compute).
        if domain_analysis:
            if domain_analysis.get("impersonated_brand"):
                result.signals.append(
                    f"brand impersonation of '{domain_analysis['impersonated_brand']}'")
            if domain_analysis.get("typosquat_of"):
                result.signals.append(
                    f"typosquatting of '{domain_analysis['typosquat_of']}'")
            if int(domain_analysis.get("subdomain_depth") or 0) >= 3:
                result.signals.append("deep subdomain nesting")

        if result.signals:
            result.suspicious_context = True
            # Weight scales with the number of independent phishing signals.
            result.risk_points = min(35, 12 + 8 * (len(result.signals) - 1))
            result.reasons.append(
                "Cloud hosting combined with phishing signals ("
                + "; ".join(result.signals)
                + ") - legitimate services are abused to host credential-harvesting "
                "pages; treat with elevated suspicion.")
        else:
            result.reasons.append(
                "No phishing signals alongside the cloud host - no added suspicion.")
        return result

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _host(url: str) -> str:
        match = _HOST.match(url.strip())
        return match.group(1).lower() if match else ""

    @staticmethod
    def _provider_for(host: str) -> str:
        for provider, suffixes in CLOUD_PROVIDERS.items():
            if any(host == s or host.endswith("." + s) or host.endswith(s)
                   for s in suffixes):
                return provider
        return ""
