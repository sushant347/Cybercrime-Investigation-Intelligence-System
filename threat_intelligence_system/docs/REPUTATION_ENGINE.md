# Threat Reputation Engine — Developer & API Documentation

*An additive, backward-compatible extension of the Threat Intelligence System. Nothing in the existing prediction pipeline, APIs or JSON contracts was changed — this package (`src/reputation/`) is consumed alongside `PhishingPredictor`, never in place of it.*

## 1. What this extension adds

| Capability | Module | Notes |
|---|---|---|
| Multi-source reputation scoring (0–100) | `reputation_engine.py` | Aggregates blacklists + domain analysis + existing WHOIS/DNS/SSL/GeoIP/VirusTotal |
| Automatic IOC type detection | `ioc.py` | url, domain, email, ipv4, ipv6, md5, sha1, sha256, phone, btc/eth wallet, telegram, whatsapp |
| Research-grade URL canonicalisation | `normalizer.py` | scheme/host/IDN/punycode/port/query/fragment/unicode/trailing-slash |
| Advanced domain analysis | `domain_analysis.py` | subdomain depth, entropy/random-domain score, suspicious TLD, homograph/unicode attack, typosquatting, brand impersonation |
| Modular blacklist connectors | `blacklists.py` | OpenPhish, PhishTank, URLHaus; `enable/disable`, cache, timeout, retry, graceful fallback |
| TTL + LRU caching | `cache.py` | Shared across connectors; avoids duplicate network requests |
| Investigator report generator | `report.py` | Merges existing `PredictionResult` + reputation into sectioned JSON/CLI report |

## 2. Architecture (Strategy + Factory + Facade + Repository, with DI)

```text
                         indicator (any IOC string)
                                    │
                          ┌─────────▼──────────┐
                          │   detect_ioc()     │  ioc.py — classifies type
                          └─────────┬──────────┘
                                    │
                 ┌──────────────────▼───────────────────┐
                 │        ReputationEngine.analyze       │  facade + thread pool
                 │  (timeouts, TTL cache, partial ok)    │
                 └───┬──────────────┬───────────────┬────┘
                     │              │               │
          ┌──────────▼───┐  ┌───────▼───────┐  ┌────▼─────────────────┐
          │ BlacklistEng │  │ DomainAnalyzer│  │ IntelligenceAggregator│ (existing, DI)
          │ (Strategy +  │  │ (entropy,     │  │ WHOIS/DNS/SSL/GeoIP/VT │
          │  Factory)    │  │  typosquat,   │  │  — unchanged           │
          │ OpenPhish    │  │  homograph,   │  └────────────────────────┘
          │ PhishTank    │  │  brand)       │
          │ URLHaus      │  └───────────────┘
          └──────┬───────┘
                 │ shared TTLCache (cache.py)
                 ▼
        Reputation Score 0–100 + reasons + signals + recommendations
                 │
                 ▼
     ReportGenerator.build(prediction?, reputation)  →  ThreatReport (JSON / CLI)
```

Every collaborator is injected through the constructor (`ReputationEngine(blacklists=…, domain_analyzer=…, intelligence=…, cache=…)`), so each part is independently testable and replaceable. The default `intelligence` is the existing `IntelligenceAggregator`, resolved lazily and degrading to `None` if its optional libraries are absent.

## 3. Sequence (a single `analyze` call)

```text
caller → ReputationEngine.analyze(indicator)
        → detect_ioc(indicator)                         → IOC(type)
        → cache.get(rep:type:indicator)                 → hit? return
        → ThreadPool:
            ├─ BlacklistEngine.check(indicator)          [each connector: cache→local→download→match]
            ├─ DomainAnalyzer.analyze(domain)            [entropy, typosquat, homograph, brand]
            └─ IntelligenceAggregator.gather_dict(domain)[WHOIS/DNS/SSL/GeoIP/VT, cached]
        → combine into score (start 100, subtract penalties, add intel bonuses, clamp 0-100)
        → attach reasons / positive / negative / recommendations
        → cache.set(...) ; return expanded JSON
```

If any source times out or raises, it is recorded under `sources_unavailable` and the score is computed from whatever succeeded — **the call never crashes**.

## 4. API

```python
from src.reputation import ReputationEngine, ReportGenerator

# 1. Reputation only (works fully offline; degrades gracefully online)
engine = ReputationEngine()                     # or inject custom collaborators
rep = engine.analyze("http://esewa-verify-login.top/account")
print(rep["reputation_score"], rep["reputation_level"])   # e.g. 55 suspicious
for reason in rep["reasons"]:
    print("-", reason)

# 2. Combined investigator report (existing PredictionResult stays untouched)
from src.prediction.predictor import PhishingPredictor
prediction = PhishingPredictor(model_type="xgboost").predict(url)   # unchanged API
report = ReportGenerator().build(
    indicator=url,
    prediction=prediction,                     # accepts PredictionResult or dict; optional
    reputation=engine.analyze(url),
    evidence_refs=["CASE_0001/EVID_00001"],    # link back to OCR-extracted entities
)
print(report.to_cli())                         # formatted investigator report
report_json = report.to_dict()                 # expanded JSON (see below)
```

### Reputation JSON contract (new, additive)

`indicator, normalized, ioc_type, reputation_score (0–100), reputation_level (trusted/neutral/suspicious/hostile), blacklists[] {source, available, listed, detail}, domain_analysis {subdomain_depth, entropy, random_domain_score, suspicious_tld, unicode_attack, homograph_suspect, impersonated_brand, typosquat_of, risk_points, explanations[]}, network_intelligence{…}, reasons[], positive_signals[], negative_signals[], recommendations[], sources_available[], sources_unavailable[], processing_time_ms`.

### ThreatReport JSON contract (new, additive)

`summary, threat_reputation{reputation_score, reputation_level, ioc_type, reasons[]}, ml_prediction{…existing PredictionResult, verbatim…}, threat_intelligence{…}, indicators{indicator, normalized, ioc_type, blacklists[], domain_analysis{}}, positive_signals[], negative_signals[], risk_factors[], recommendations[], evidence_references[], investigator_notes, sources_available[], sources_unavailable[], processing_time_ms`.

The existing `PredictionResult.to_json()` (prediction, risk/trust/confidence, reasons, positive indicators, threat-intelligence details, decision breakdown, feature importance) is embedded **verbatim** under `ml_prediction` — no field renamed, none removed.

## 5. Scoring model (Reputation Score)

Starts at 100 and subtracts penalties, then adds intelligence bonuses, clamped to 0–100:

- Blacklist hit: −45 per listing (cap −70) — a listed indicator reads *hostile*.
- Domain signals (cap −60): suspicious TLD −15, brand impersonation −30, typosquat −30, homograph/unicode −20, deep subdomains −10, high random-domain score −15.
- Intelligence bonuses (cap +15): established domain age, SPF, DMARC, valid SSL.

Levels: ≥85 trusted, 60–84 neutral, 35–59 suspicious, <35 hostile. Thresholds and penalties are constants at the top of the respective modules and can be tuned for the evaluation study.

## 6. Graceful degradation & performance

Connectors try a local feed file first (offline/test mode), then a cached download, then a bounded-retry live fetch. Missing `requests`, dead feeds, DNS failures and timeouts all resolve to `available=False` with processing continuing. All lookups run in a `ThreadPoolExecutor` with a hard per-call timeout; WHOIS/DNS/GeoIP/SSL/feed responses are TTL+LRU cached so repeated lookups within a case are free.

## 7. Backward-compatibility guarantees

No existing file was modified. `PhishingPredictor`, `PredictionResult`, the intelligence connectors and their JSON all behave exactly as before. Every new capability is opt-in: import from `src.reputation` only if you want it. The reputation package has **no hard dependency** on scikit-learn/XGBoost/tldextract — it runs (and its 29 tests pass) with the standard library plus optional `requests`.

## 8. Tests

`tests/test_reputation.py` — 29 offline tests: IOC detection (15 cases), URL normalisation/IDN, domain analysis (typosquat, brand, homograph, entropy), blacklist lifecycle + dead-feed degradation, TTL/LRU cache expiry+eviction, full-engine JSON contract, hostile/clean scoring, non-URL IOC partial results, report generator JSON+CLI, and prediction-optional backward compatibility. Run: `pytest tests/test_reputation.py`.
