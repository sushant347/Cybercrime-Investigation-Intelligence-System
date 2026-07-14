# CIIS Phase 2 — Intelligent Cybercrime Investigation Platform

Additive package turning the forensic pipeline into an investigation
platform. **No existing module was modified.** No machine learning — every
score is deterministic, weighted, and carries a complete explanation.

## Architecture

Clean Architecture, DI throughout, Repository Pattern, configuration-driven
(`config.py`; `INVESTIGATION_*` env overrides; zero hardcoded values in
services).

```
investigation/
├── config.py           InvestigationConfig (weights, bands, stage rules, paths)
├── data_access.py      CaseDataRepository — READ-ONLY gateway over all
│                       existing storage + ThreatIntelProvider (optional file)
├── repository.py       Versioned case-level JSON/MD outputs (never overwrites)
├── audit.py            investigation_audit_log.csv (every module, every run)
├── pipeline.py         InvestigationPipeline + build_default_pipeline()
├── correlation/        M1 explainable weighted correlation (12 factors)
├── graph/              M2 typed relationship graph (12 node / 5+1 edge types)
├── campaigns/          M3 connected-component campaign clustering
├── suspects/           M4 identity-anchor suspect scoring (6 components)
├── timeline/           M5 attack-stage timeline intelligence
├── analytics/          M6 case/entity/threat/quality statistics
├── reporting/          M7 finding-referenced forensic report (MD + JSON)
└── prioritization/     M8 weighted case priority
```

Each module = `models.py` (Pydantic contracts) + `service.py`. Inputs come
only through the data gateway; outputs go only through the versioned
repository. Tests: `tests/investigation/` (synthetic case, no OCR deps).

## Data flow

```
existing storage (read-only)                storage/investigation/<CASE_ID>/
  evidence.csv ─┐                             correlation_analysis.json  (M1)
  entities.csv ─┤                             graph.json                 (M2)
  json/CASE.json├─ CaseDataRepository ──► M1 ─ graph_statistics.json      (M2)
  forensics/…  ─┤        │                │    graph_summary.json         (M2)
  threat intel ─┘        │                ├─► M2, M3, M4                 
                         ├─► M5 timeline  │    campaign_analysis.json     (M3)
                         └─► M6 analytics ◄┘   suspect_assessment.json    (M4)
                              │                timeline_analysis.json     (M5)
                              ▼                analytics.json + 2 more    (M6)
                         M8 priority ─► M7 report                        
                                               investigation_report.md/json (M7)
                                               case_priority.json         (M8)
```

Modules are failure-isolated: one broken analysis is audited as ERROR and
the rest continue. Re-analysis produces `_v2`, `_v3`… — nothing is replaced.

## Explainability contract

Every correlation pair lists its factors, weights, matched values and a
narrative; every campaign membership names the exact links that placed it;
every suspect and priority score decomposes into weighted components with
per-component justification; every graph edge carries an explanation; the
Module-7 report is templated exclusively over computed values (missing
inputs render "not available" — hallucination is structurally impossible).

## Relationship levels & bands (config-driven)

Correlation confidence = `1 − exp(−weight/1.6)` →
NO_RELATIONSHIP < 0.05 ≤ WEAK < 0.30 ≤ MEDIUM < 0.55 ≤ STRONG < 0.80 ≤ VERY_STRONG.
Campaigns cluster pairs ≥ 0.55. Priority: LOW < 30 ≤ MEDIUM < 55 ≤ HIGH < 75 ≤ CRITICAL.

## Threat intelligence input

Optional file `storage/investigation/threat_intel_indicators.json`:

```json
{"indicators": {"scam-domain.top": {"verdict": "malicious", "source": "PhishTank"}}}
```

Absent file ⇒ the factor is skipped and reported as unavailable (never
treated as "no threat"). The existing threat_intelligence_system can export
into this format without any coupling.

## API / usage

```python
from backend.modules.investigation.pipeline import build_default_pipeline

pipeline = build_default_pipeline()          # composition root (DI)
results = pipeline.analyze_case("CASE_0042") # all 8 modules
results["priority"].priority_level           # e.g. "HIGH"
```

CLI:

```
python investigation_cli.py analyze CASE_0042   # or --all
python investigation_cli.py priority CASE_0042
python investigation_cli.py report CASE_0042
```

## Dependencies

None beyond the existing stack (pydantic; pure-Python graph algorithms — no
networkx). Phase-3 dashboard can consume every JSON artefact as-is;
`graph.json` is deliberately visualization-independent.
