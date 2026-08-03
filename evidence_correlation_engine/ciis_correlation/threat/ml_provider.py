"""ML-backed threat-intelligence provider (adapter).

Wraps the standalone ``threat_intelligence_system`` phishing-URL classifier
behind the same duck-typed interface the investigation engine already uses for
:class:`ThreatIntelProvider` (``available`` / ``lookup`` / ``is_malicious``), so
it can be dropped into ``build_default_pipeline(threat_intel=…)`` with no change
to any Phase-2 service.

Design principles (mirroring the audit's risk notes):
* **No hard dependency.** The heavy ML stack (xgboost/sklearn/…) and the ML
  repo are imported *lazily* on first use. If they are missing, the model
  artifact is absent, or import fails, the adapter reports ``available == False``
  and every lookup returns ``None`` — the engine then falls back cleanly to the
  static indicator file. The Django process is never bloated at import time.
* **URLs only.** The classifier scores URLs, so non-URL entity values are
  ignored (``lookup`` returns ``None``).
* **Cached + offline by default.** Results are memoized per value; network-based
  enrichment (whois/DNS) is off by default to keep analysis fast and
  deterministic. Enable it explicitly if a deployment wants live enrichment.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from backend.modules.evidence.logger import get_logger


def _looks_like_url(value: str) -> bool:
    v = (value or "").strip().lower()
    if "://" in v:
        return True
    # bare domain / host with a dot and no spaces (e.g. "bad-domain.top/login").
    # Reject emails ("@" in the host) and pure numbers.
    head = v.split("/", 1)[0]
    if "@" in head:
        return False
    return " " not in v and "." in head and not v.isdigit()


def _registrable_domain(url: str) -> str:
    """Host part of a URL, without scheme, credentials, port or path.

    Not a public-suffix parse — the report shows the host an investigator
    would recognise ("nabil-verify.scam.top"), which is what matters here.
    """
    value = (url or "").strip()
    if "://" in value:
        value = value.split("://", 1)[1]
    host = value.split("/", 1)[0].split("?", 1)[0]
    if "@" in host:                     # strip user:pass@
        host = host.rsplit("@", 1)[1]
    return host.split(":", 1)[0].lower()   # drop any :port


class MLThreatIntelProvider:
    """Adapts the phishing-URL ML classifier to the ThreatIntelProvider API."""

    def __init__(
        self,
        system_root: Path,
        *,
        model_type: str = "xgboost",
        use_intelligence: bool = False,
        use_transformer: bool = False,
        use_ensemble: bool = False,
        use_rules: bool = True,
        malicious_risk_threshold: int = 70,
        suspicious_risk_threshold: int = 40,
    ) -> None:
        self._root = Path(system_root)
        self._model_type = model_type
        self._opts = dict(
            use_intelligence=use_intelligence,
            use_transformer=use_transformer,
            use_ensemble=use_ensemble,
            use_rules=use_rules,
        )
        self._malicious_threshold = malicious_risk_threshold
        self._suspicious_threshold = suspicious_risk_threshold
        self._log = get_logger("investigation.ml_threat_intel")
        self._predictor = None
        self._load_attempted = False
        self._load_failed = False

    # ------------------------------------------------------------- lazy loader
    def _get_predictor(self):
        if self._predictor is not None:
            return self._predictor
        if self._load_attempted:
            return None  # previous attempt failed; don't retry every call
        self._load_attempted = True
        try:
            if not self._root.is_dir():
                raise FileNotFoundError(f"ML system root not found: {self._root}")
            if str(self._root) not in sys.path:
                sys.path.insert(0, str(self._root))
            from src.prediction.predictor import PhishingPredictor  # heavy: lazy

            self._predictor = PhishingPredictor(
                model_type=self._model_type, **self._opts
            )
            self._log.info(
                "ML threat-intel loaded (model=%s, root=%s)",
                self._model_type,
                self._root,
            )
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            self._load_failed = True
            self._log.warning(
                "ML threat-intel unavailable (%s); falling back to static intel",
                exc,
            )
            self._predictor = None
        return self._predictor

    # ---------------------------------------------------------------- interface
    @property
    def available(self) -> bool:
        """True once the classifier has successfully loaded (lazy)."""
        return self._get_predictor() is not None

    def lookup(self, value: str) -> Optional[Dict[str, Any]]:
        """Classify a URL value; ``None`` for non-URLs or when unavailable."""
        if not value or not _looks_like_url(value):
            return None
        return self._classify(value.strip())

    def is_malicious(self, value: str) -> bool:
        hit = self.lookup(value)
        return bool(hit) and str(hit.get("verdict", "")).lower() in {
            "malicious",
            "phishing",
        }

    # ------------------------------------------------------------------ helper
    @lru_cache(maxsize=2048)  # noqa: B019 - instance-bound cache is intended here
    def _classify(self, url: str) -> Optional[Dict[str, Any]]:
        predictor = self._get_predictor()
        if predictor is None:
            return None
        try:
            result = predictor.predict(url)
        except Exception as exc:  # noqa: BLE001 - one bad URL must not abort
            self._log.warning("ML prediction failed for %r: %s", url, exc)
            return None

        prediction = str(getattr(result, "prediction", "")).lower()
        risk = int(getattr(result, "risk_score", 0) or 0)
        if prediction == "phishing" or risk >= self._malicious_threshold:
            verdict = "malicious"
        elif prediction == "suspicious" or risk >= self._suspicious_threshold:
            verdict = "suspicious"
        else:
            verdict = "benign"
        return {
            "verdict": verdict,
            "source": f"ml:{getattr(result, 'model_type', self._model_type)}",
            "risk_score": risk,
            "confidence": round(float(getattr(result, "confidence", 0.0) or 0.0), 4),
            "risk_level": getattr(result, "risk_level", ""),
            "prediction": getattr(result, "prediction", ""),
            "model_version": getattr(result, "model_version", ""),
            # Investigator-facing detail. A verdict on its own is not evidence:
            # a report has to say *which domain* was judged and *why*, in terms
            # an investigator can put in front of a court. Everything below is
            # already computed by the classifier, so surfacing it is free.
            **self._investigator_detail(url, result),
        }

    def _investigator_detail(self, url: str, result: Any) -> Dict[str, Any]:
        """The subset of the classifier output worth putting in a report.

        Deliberately *not* everything the engine produces: SHAP contributions,
        raw feature vectors and ensemble weights are model diagnostics, not
        findings. Kept: the registrable domain, brand impersonation, the
        network-derived facts (domain age, registrar, SSL, SPF/DMARC, hosting)
        and the plain-language reasons.
        """
        # ``threat_intelligence`` is a *flat* dict keyed by connector prefix
        # (``whois_registrar``, ``dns_has_spf``, …), not a nested mapping.
        intel = getattr(result, "threat_intelligence", None) or {}

        def _clean(seq: Any, limit: int) -> list:
            return [str(x).strip() for x in list(seq or [])[:limit] if str(x).strip()]

        detail: Dict[str, Any] = {
            "domain": _registrable_domain(url),
            "trust_score": int(getattr(result, "trust_score", 0) or 0),
            "brand_impersonated": getattr(result, "brand_detected", None) or "",
            "official_domain": bool(getattr(result, "official_domain", False)),
            "ssl_status": getattr(result, "ssl_status", "") or "",
            "reasons": _clean(getattr(result, "reasons", []), 6),
            "threat_signals": _clean(getattr(result, "negative_indicators", []), 6),
            "trust_signals": _clean(getattr(result, "positive_indicators", []), 6),
        }
        # Network-derived facts: recorded only when the corresponding connector
        # actually succeeded, so an offline or rate-limited analysis omits the
        # field entirely rather than reporting a misleading zero/False.
        if intel.get("whois_success"):
            if intel.get("whois_domain_age_days") is not None:
                detail["domain_age_days"] = intel["whois_domain_age_days"]
            if intel.get("whois_registrar"):
                detail["registrar"] = str(intel["whois_registrar"])
        if intel.get("dns_success"):
            detail["spf_present"] = bool(intel.get("dns_has_spf"))
            detail["dmarc_present"] = bool(intel.get("dns_has_dmarc"))
        if intel.get("ssl_success") and intel.get("ssl_days_until_expiry") is not None:
            detail["ssl_days_left"] = intel["ssl_days_until_expiry"]
        if intel.get("geoip_success"):
            hosting = ", ".join(
                str(v) for v in (intel.get("geoip_asn_org"), intel.get("geoip_country")) if v
            )
            if hosting:
                detail["hosting"] = hosting
            if intel.get("geoip_ip_address"):
                detail["ip_address"] = str(intel["geoip_ip_address"])
        return detail
