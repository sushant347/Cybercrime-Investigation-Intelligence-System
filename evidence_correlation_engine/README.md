# Evidence Correlation Engine

Relationship intelligence: what connects to what, and how strongly. Given a
case's extracted evidence, this engine decides which items are related, which
cases are related, which items form a campaign, and which identities look like
suspects — each with a written justification.

No machine learning in the scoring path. Every weight is deterministic and
every score decomposes into named factors with the concrete values behind them.

## Where this sits

```
evidence_ocr_engine  ──►  evidence_correlation_engine  ──►  timeline_report_engine
                                    ▲
                    threat_intelligence_system (optional)
```

It reads the OCR engine's storage tree **read-only** and imports exactly two
symbols from it (`EvidenceConfig`, `get_logger`). The OCR engine imports
nothing from here. Importing `ciis_correlation` puts the OCR engine on
`sys.path` automatically; `CIIS_ENGINE_ROOT` overrides its location.

## Layout

```
ciis_correlation/
├── core/               shared infrastructure, reused by the downstream engine
│   ├── config.py         InvestigationConfig — weights, bands, stages, paths
│   ├── data_access.py    CaseDataRepository — READ-ONLY gateway over storage
│   ├── repository.py     versioned case artifacts (never overwrites)
│   ├── audit.py          investigation_audit_log.csv (every module, every run)
│   └── maintenance.py    storage reset, case / evidence deletion
├── correlation/        weighted 12-factor evidence-pair correlation
├── crosscase.py        cross-case entity lookup over entities.csv
├── campaigns/          connected-component campaign clustering
├── suspects/           identity-anchor suspect scoring (6 components)
├── threat/             threat-intel providers (heuristics + optional ML)
├── evaluation/         accuracy measurement against gold labels
└── testing.py          synthetic case shared by both engines' test suites
```

Each analytical module is `models.py` (Pydantic contracts) + `service.py`.
Inputs come only through the data gateway; outputs go only through the
versioned repository.

`core/` is deliberately shared with `timeline_report_engine` rather than
duplicated, so there is exactly one definition of how a case is read, written
and audited.

## Installation

This module owns its third-party dependencies in `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

When copied outside this repository, also provide `evidence_ocr_engine` or set
`CIIS_ENGINE_ROOT` to it; the correlation engine intentionally reuses the
upstream evidence contracts instead of duplicating them.

## Scoring

Correlation weight is `type weight × value specificity`, summed over shared
values and squashed into a bounded confidence:

```
confidence = 1 − exp(−weight / 1.6)

NO_RELATIONSHIP < 0.05 ≤ WEAK < 0.30 ≤ MEDIUM < 0.55 ≤ STRONG < 0.80 ≤ VERY_STRONG
```

The type weight says how identifying a *kind* of entity is; the specificity —
learned unsupervised from the corpus in `correlation/specificity.py` — says how
identifying *this particular value* is. Without the second term, "both items
mention NPR 2,000" scored exactly like "both items share a wallet address",
which linked essentially every case to every other on round amounts alone.

Correlation has no ground truth to train against, so nothing here is
supervised. The per-factor breakdown persisted in every artifact is already the
feature vector a supervised ranker would consume, once investigators have
confirmed or rejected enough links to serve as labels.

## Threat intelligence

Three providers, chained, each optional:

1. `threat/heuristics.py` — offline, explainable URL/domain heuristics
2. `threat/ml_provider.py` — lazy adapter over `threat_intelligence_system`
3. a static indicator file at `storage/investigation/threat_intel_indicators.json`

```json
{"indicators": {"scam-domain.top": {"verdict": "malicious", "source": "PhishTank"}}}
```

When none is available the factor is reported as *unavailable*, never as
"no threat found".

## Tests

```bash
python -m pytest -q      # 103 tests
```

Runs against a synthetic case (`ciis_correlation/testing.py`) — no OCR
dependency, no fixtures on disk.

```bash
python scripts/run_table_6_4.py    # correlation accuracy vs gold labels
```

## Output

Artifacts land in `storage/investigation/<CASE_ID>/`, versioned rather than
overwritten:

```
correlation_analysis.json   cross_case_correlation.json
campaign_analysis.json      suspect_assessment.json
```
