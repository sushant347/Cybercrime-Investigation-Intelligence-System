# CIIS — Cybercrime Investigation Intelligence System

Turns screenshots, chat exports and receipts of a cybercrime case into an
evidence-backed investigation report: OCR and entity extraction, threat
scoring, relationship correlation, an attack timeline, and a forensic report —
each step explainable and traceable back to the exact evidence it came from.

No machine learning in the scoring path. Every correlation weight, suspect
score and priority band is deterministic and carries a written justification,
so nothing in a report can be hallucinated.

## Architecture

Four engines in a straight chain, plus a Django API and a React frontend.
Each engine imports only the one before it, so the dependency graph is acyclic.

```
                 ┌─────────────┐
                 │  frontend   │  React + Vite
                 └──────┬──────┘
                        │ REST
                 ┌──────▼──────┐
                 │  ciis_api   │  Django — api/engine.py is the only bridge
                 └──────┬──────┘
                        │
   ┌────────────────────▼─────────────────────────────────────────┐
   │                                                              │
   │  1. evidence_ocr_engine                                      │
   │     upload → OCR → clean → enhance → entities → forensics    │
   │     writes storage/ (evidence.csv, entities.csv, json/)      │
   │                          │                                   │
   │                          ▼                                   │
   │  2. threat_intelligence_system            (optional)         │
   │     phishing-URL classifier, own virtualenv                  │
   │     reached lazily; absent ⇒ heuristics only                 │
   │                          │                                   │
   │                          ▼                                   │
   │  3. evidence_correlation_engine                              │
   │     correlation → cross-case → campaigns → suspects          │
   │                          │                                   │
   │                          ▼                                   │
   │  4. timeline_report_engine                                   │
   │     timeline → graph → analytics → priority → report         │
   │     writes storage/investigation/<CASE_ID>/                  │
   │                                                              │
   └──────────────────────────────────────────────────────────────┘
```

| Module | Owns | Docs |
|---|---|---|
| `evidence_ocr_engine` | OCR, cleaning, entity extraction, forensics, storage | [README](evidence_ocr_engine/README.md) |
| `threat_intelligence_system` | Phishing-URL classification, brand & reputation intel | [README](threat_intelligence_system/README.md) |
| `evidence_correlation_engine` | Relationship intelligence + shared infrastructure | [README](evidence_correlation_engine/README.md) |
| `timeline_report_engine` | Timeline, graph, analytics, priority, reports | [README](timeline_report_engine/README.md) |
| `ciis_api` | REST API, permissions, background jobs | — |
| `ciis_frontend` | Investigator UI | — |

## Analysis flow in detail

Stage 1 is triggered per uploaded file. Stages 3–4 run as one case analysis,
orchestrated by `ciis_timeline_report.pipeline`:

```
load evidence (read-only)
  → correlation          weighted 12-factor evidence-pair scoring
  → cross-case           links to other cases over the shared entity index
  → timeline             timestamp resolution, ordering, attack stages
      → graph            relationship graph (consumes timeline events)
      → campaigns        clustering over strong correlations
      → suspects         identity-anchor scoring
  → analytics            case / entity / threat / quality statistics
  → priority             weighted case priority
  → report               Markdown + JSON + PDF, referencing every finding
```

Every module is failure-isolated — one broken analysis is audited as an error
and the rest continue — and every run appends to
`storage/investigation/investigation_audit_log.csv`.

## Running it

```bash
./dev.sh up        # API + frontend + engines, full pipeline enabled
./dev.sh test      # frontend, API and both analysis engine suites
./dev.sh doctor    # what is / isn't set up
./dev.sh threat <url>   # threat engine CLI, in its own venv
```

On Windows without a POSIX shell, `dev.cmd` takes the same subcommands.

The threat engine cannot share the platform virtualenv: PaddleOCR needs
`numpy<2` while its ML stack needs `numpy>=2`. It gets `.venv-threat`;
everything else uses `.venv-platform`.

## Tests

```bash
cd evidence_ocr_engine          && python -m pytest -q    # 392
cd evidence_correlation_engine  && python -m pytest -q    #  93
cd timeline_report_engine       && python -m pytest -q    #  52
cd ciis_api                     && python -m pytest -q    #  53
```

## Storage

All engines read and write one tree, owned by the OCR engine:

```
evidence_ocr_engine/storage/
  cases.csv  evidence.csv  entities.csv  ocr_results.csv   chain of custody
  json/<CASE_ID>.json                                      full OCR output
  forensics/<EVIDENCE_ID>/                                 Phase-1 reports
  investigation/<CASE_ID>/                                 analysis artifacts
```

The correlation engine reads that tree strictly read-only through
`CaseDataRepository`; analysis output only ever lands under `investigation/`.
Re-analysis versions artifacts rather than overwriting them.
