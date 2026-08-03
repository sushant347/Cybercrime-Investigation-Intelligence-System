"""Rule-based threat intelligence for URLs and domains (no model, no network).

Why this exists
---------------
The engine had exactly two ways to reach a threat verdict: a static indicator
file that ships empty, and the ML phishing classifier, which lives in a
separate project with a heavy dependency stack (xgboost/sklearn/…) that the
API process does not always have installed. When neither was present -- the
normal case -- ``intel_available`` was ``0`` and every threat panel in the
product was blank, on cases whose evidence was nothing but phishing links.

This provider closes that hole. It is deliberately *explainable* rather than
clever: every point of risk comes from a named rule, and the reasons are
written in the language an investigator would use in a statement of findings.
It requires no model, no data file, no network call, and it can never be
"unavailable", so a case always gets a threat verdict of some kind.

It is not a replacement for the classifier. When the ML provider is available
its verdict is preferred (see :class:`ChainedThreatIntelProvider`); the
heuristics then act as a floor, not a ceiling.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.modules.evidence.logger import get_logger

# --------------------------------------------------------------------------- #
# Rule inputs
# --------------------------------------------------------------------------- #

#: Brands whose names are impersonated in Nepali payment fraud, mapped to the
#: domains those brands actually use. A brand token appearing in a host that is
#: not one of the official domains is the single strongest signal available
#: without a model - it is how nearly every campaign in this corpus works
#: ("esewa-cashback-offer.xyz", "esewa-verify-kyc.com").
OFFICIAL_DOMAINS: Dict[str, Tuple[str, ...]] = {
    "esewa": ("esewa.com.np", "esewa.com", "merchant.esewa.com.np"),
    "khalti": ("khalti.com", "web.khalti.com", "admin.khalti.com"),
    "imepay": ("imepay.com.np", "ime.com.np"),
    "connectips": ("connectips.com",),
    "fonepay": ("fonepay.com",),
    "nabil": ("nabilbank.com",),
    "nicasia": ("nicasiabank.com",),
    "globalime": ("globalimebank.com",),
    "machhapuchchhre": ("machbank.com",),
    "nepalbank": ("nepalbank.com.np",),
    "rastriyabanijya": ("rbb.com.np",),
    "nrb": ("nrb.org.np",),
    "ntc": ("ntc.net.np",),
    "ncell": ("ncell.axiata.com", "ncell.com.np"),
    "facebook": ("facebook.com", "fb.com", "m.facebook.com"),
    "instagram": ("instagram.com",),
    "whatsapp": ("whatsapp.com", "wa.me"),
    "gmail": ("gmail.com", "mail.google.com"),
    "google": ("google.com", "google.com.np"),
}

#: Brands kept in :data:`OFFICIAL_DOMAINS` so their real domains are trusted,
#: but never treated as *impersonated*. A mail provider's name inside a host is
#: almost always OCR mangling an email address ("user21gmail.com" for
#: "user21@gmail.com"), not a look-alike site - flagging those buried the real
#: findings under noise.
NOT_IMPERSONATION_BRANDS = frozenset({"gmail", "google"})

#: TLDs with a well-documented abuse rate, heavily used by throwaway phishing
#: infrastructure. Presence alone is not a verdict - it is one weighted signal.
HIGH_RISK_TLDS = frozenset({
    "xyz", "top", "click", "link", "live", "vip", "online", "shop", "site",
    "icu", "cf", "tk", "ga", "gq", "ml", "buzz", "rest", "fit", "cam", "quest",
    "work", "surf", "monster", "cyou", "sbs", "lol", "bond",
})

#: Link shorteners: not malicious in themselves, but they hide the destination,
#: which in evidence terms means the link cannot be assessed at all.
URL_SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "is.gd", "rb.gy",
    "rebrand.ly", "shorturl.at", "ow.ly", "buff.ly", "tiny.cc", "bitly.com",
})

#: Words that betray the *purpose* of a phishing page. Split by where they
#: carry weight: a "verify" in the hostname is a stronger signal than in a path.
LURE_WORDS = (
    "verify", "verification", "kyc", "login", "signin", "secure", "security",
    "update", "confirm", "unlock", "suspend", "reactivate", "recover",
    "wallet", "otp", "password", "account", "billing", "refund",
)
REWARD_WORDS = (
    "cashback", "reward", "bonus", "prize", "lucky", "winner", "gift", "offer",
    "claim", "free", "lottery", "draw", "jackpot", "dashain", "tihar",
)

_IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_HEX_ISH = re.compile(r"^[0-9a-f]{8,}$", re.IGNORECASE)

#: Score thresholds. Chosen so that a single weak signal (a risky TLD, say)
#: never on its own produces a "malicious" verdict that an investigator would
#: have to defend in court, while brand impersonation - which is never
#: accidental - reaches it immediately.
MALICIOUS_AT = 70
SUSPICIOUS_AT = 35


def split_url(value: str) -> Tuple[str, str]:
    """Return ``(host, path_and_query)`` for a URL or bare domain."""
    text = (value or "").strip()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text, flags=re.IGNORECASE)
    host, _, rest = text.partition("/")
    if "@" in host:                      # user:pass@host - strip credentials
        host = host.rsplit("@", 1)[1]
    host = host.split("?", 1)[0].split(":", 1)[0]
    return host.lower(), ("/" + rest).lower() if rest else ""


def _registrable(host: str) -> str:
    """Best-effort registrable domain (last two labels, three for ``co.np``)."""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if labels[-2] in {"com", "co", "org", "net", "gov", "edu"} and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


class HeuristicThreatIntelProvider:
    """Explainable, dependency-free URL/domain risk scoring.

    Implements the same duck-typed interface as every other provider
    (``available`` / ``lookup`` / ``is_malicious``), so it drops into
    ``build_default_pipeline(threat_intel=…)`` unchanged.
    """

    source_name = "heuristics"

    def __init__(self, *, malicious_at: int = MALICIOUS_AT,
                 suspicious_at: int = SUSPICIOUS_AT) -> None:
        self._malicious_at = malicious_at
        self._suspicious_at = suspicious_at
        self._log = get_logger("investigation.threat_heuristics")
        self._cache: Dict[str, Optional[Dict[str, Any]]] = {}

    # ---------------------------------------------------------------- interface

    @property
    def available(self) -> bool:
        """Always true: the rules need no model, data file or network."""
        return True

    def lookup(self, value: str) -> Optional[Dict[str, Any]]:
        key = (value or "").strip().lower()
        if not key:
            return None
        if key not in self._cache:
            self._cache[key] = self._score(key)
        return self._cache[key]

    def is_malicious(self, value: str) -> bool:
        hit = self.lookup(value)
        return bool(hit) and hit.get("verdict") == "malicious"

    # ------------------------------------------------------------------ scoring

    def _score(self, value: str) -> Optional[Dict[str, Any]]:
        host, path = split_url(value)
        if not host or ("." not in host and not _IPV4.match(host)):
            return None

        score = 0
        reasons: List[str] = []
        trust: List[str] = []
        brand = ""

        # --- official domain: a decisive *negative* signal -----------------
        registrable = _registrable(host)
        for name, domains in OFFICIAL_DOMAINS.items():
            if host in domains or registrable in domains:
                trust.append(f"{host} is an official {name} domain")
                return self._verdict(host, 0, reasons, trust, brand=name,
                                     official=True)

        # --- brand impersonation ------------------------------------------
        host_words = re.sub(r"[^a-z0-9]+", "", host)
        for name in OFFICIAL_DOMAINS:
            if name in NOT_IMPERSONATION_BRANDS:
                continue
            if name in host_words:
                brand = name
                score += 55
                reasons.append(
                    f"hostname contains the brand '{name}' but is not an "
                    f"official {name} domain"
                )
                break

        # --- infrastructure signals ---------------------------------------
        tld = host.rsplit(".", 1)[-1]
        if _IPV4.match(host):
            score += 40
            reasons.append("the link points at a raw IP address, not a domain")
        elif tld in HIGH_RISK_TLDS:
            score += 25
            reasons.append(f"registered under '.{tld}', a TLD with a high abuse rate")

        if registrable in URL_SHORTENERS:
            score += 35
            reasons.append("URL shortener - the real destination is concealed")

        if host.startswith("xn--") or ".xn--" in host:
            score += 30
            reasons.append("punycode hostname (possible look-alike characters)")

        labels = host.split(".")
        if len(labels) >= 5:
            score += 15
            reasons.append(f"{len(labels)} sub-domain levels deep")
        if host.count("-") >= 3:
            score += 15
            reasons.append("hostname is built from many hyphenated words")
        if len(host) > 40:
            score += 10
            reasons.append("unusually long hostname")
        if _HEX_ISH.match(labels[0]):
            score += 10
            reasons.append("random-looking hostname label")

        # --- intent signals -------------------------------------------------
        haystack_host = host_words
        haystack_all = host_words + re.sub(r"[^a-z0-9]+", "", path)
        lures = sorted({w for w in LURE_WORDS if w in haystack_all})
        rewards = sorted({w for w in REWARD_WORDS if w in haystack_all})
        if lures:
            weight = 20 if any(w in haystack_host for w in lures) else 10
            score += weight
            reasons.append(
                "credential/verification wording in the link: "
                + ", ".join(lures[:4])
            )
        if rewards:
            weight = 20 if any(w in haystack_host for w in rewards) else 10
            score += weight
            reasons.append("reward/prize wording in the link: " + ", ".join(rewards[:4]))
        if lures and rewards:
            score += 10
            reasons.append("combines a reward offer with a verification request")

        if not reasons:
            trust.append("no risk signal matched")
        return self._verdict(host, score, reasons, trust, brand=brand)

    def _verdict(self, host: str, score: int, reasons: Sequence[str],
                 trust: Sequence[str], *, brand: str = "",
                 official: bool = False) -> Dict[str, Any]:
        score = max(0, min(100, score))
        if score >= self._malicious_at:
            verdict = "malicious"
        elif score >= self._suspicious_at:
            verdict = "suspicious"
        else:
            verdict = "benign"
        return {
            "verdict": verdict,
            "source": self.source_name,
            "risk_score": score,
            # Rules are deterministic: the confidence *is* how far the score
            # sits from the decision boundary, not a probability.
            "confidence": round(min(1.0, score / 100.0), 4),
            "risk_level": verdict,
            "prediction": "phishing" if verdict == "malicious" else verdict,
            "domain": host,
            "official_domain": official,
            "brand_impersonated": "" if official else brand,
            "reasons": list(reasons) or list(trust),
            "threat_signals": list(reasons),
            "trust_signals": list(trust),
        }


class ChainedThreatIntelProvider:
    """Consults several providers and keeps the most serious explained verdict.

    Order matters only for tie-breaks: an authoritative source (a curated
    indicator file, then the ML classifier) is preferred over the heuristics
    when both reach the same severity. A *more* serious verdict from a later
    provider still wins, because a miss by an upstream feed must not silence a
    rule that fired - and the winning verdict always carries the reasons of the
    provider that produced it, so the record stays explainable.
    """

    _SEVERITY = {"malicious": 3, "phishing": 3, "scam": 3, "fraud": 3,
                 "suspicious": 2, "benign": 1, "": 0}

    def __init__(self, *providers: Any) -> None:
        self._providers = [p for p in providers if p is not None]
        self._log = get_logger("investigation.threat_chain")

    @property
    def source_name(self) -> str:
        names = [getattr(p, "source_name", type(p).__name__)
                 for p in self._providers if self._is_available(p)]
        return "+".join(names) if names else "unavailable"

    @property
    def available(self) -> bool:
        return any(self._is_available(p) for p in self._providers)

    def lookup(self, value: str) -> Optional[Dict[str, Any]]:
        best: Optional[Dict[str, Any]] = None
        best_rank = -1
        for provider in self._providers:
            if not self._is_available(provider):
                continue
            try:
                hit = provider.lookup(value)
            except Exception:  # noqa: BLE001 - one bad provider must not abort
                self._log.exception("threat provider %s failed on %r",
                                    type(provider).__name__, value)
                continue
            if not hit:
                continue
            rank = self._SEVERITY.get(str(hit.get("verdict", "")).lower(), 0)
            if rank > best_rank:                     # strictly greater: earlier
                best, best_rank = hit, rank          # provider wins ties
        return best

    def is_malicious(self, value: str) -> bool:
        hit = self.lookup(value)
        return bool(hit) and self._SEVERITY.get(
            str(hit.get("verdict", "")).lower(), 0
        ) >= 3

    @staticmethod
    def _is_available(provider: Any) -> bool:
        try:
            return bool(getattr(provider, "available", False))
        except Exception:  # noqa: BLE001 - a lazy loader may raise
            return False
