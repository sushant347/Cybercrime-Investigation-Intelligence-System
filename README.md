# CIIE — Cybercrime Investigation Intelligence Engine

Turns screenshots, chat exports and receipts of a cybercrime case into an
evidence-backed investigation report: OCR and entity extraction, threat
scoring, relationship correlation, an attack timeline, and a forensic report —
each step explainable and traceable back to the exact evidence it came from.

Every correlation weight, suspect score, priority band and report finding is
deterministic and carries a written justification. The optional RAG assistant
is a read-only layer over those stored findings: generated answers are withheld
unless their citations validate against retrieved case sources.

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
| `rag_assistant_engine` | Case-scoped retrieval, grounded local answers and citation validation | [README](rag_assistant_engine/README.md) |
| `ciis_api` | REST API, permissions, background jobs | — |
| `ciis_frontend` | Investigator UI, timeline and progressive relationship graph | [README](ciis_frontend/README.md) |

## Reference data

| Path | What it is |
|---|---|
| `sample/` | Phishing-URL datasets the threat engine trains on (585,040 URLs across four files) |
| `samples/legal_corpus/` | Nepali cyber-law and policy instruments — see [README](samples/legal_corpus/README.md) |
| `evidence_ocr_engine/samples/ground_truth/` | Gold labels for the accuracy harnesses |

`sample/` and `samples/` are different things and one letter apart: the first is
ML training data scanned by the threat engine's dataset discovery, the second is
legal source material read by nobody at runtime.

The legal corpus is **not** training data. Selected provisions of the Electronic
Transactions Act, 2063 and relevant NRB controls are transcribed into the
source-backed legal/guidance module; no model is fitted to them.
`samples/legal_corpus/manifest.json` records, per
document, whether a machine can read it at all — two of the Nepali originals are
in legacy Preeti fonts and cannot be extracted.

## Analysis flow in detail

Stage 1 is triggered per uploaded file. Stages 3–4 run as one case analysis,
orchestrated by `ciis_timeline_report.pipeline`:

```
load evidence (read-only)
  → correlation          weighted evidence-pair scoring (upload time is context only)
  → cross-case           links to other cases over the shared entity index
  → timeline             timestamp resolution, ordering, attack stages
      → graph            typed graph + NetworkX analytics (consumes timeline events)
      → campaigns        clustering over strong correlations
      → suspects         identity-anchor scoring
  → analytics            case / entity / threat / quality statistics
  → priority             weighted case priority
  → report               Markdown + JSON + PDF, referencing every finding
```

After those artifacts are persisted, the API performs a best-effort RAG index
sync through the standalone engine. RAG failure never changes the outcome of
OCR, correlation, timeline, graph or report generation.

Every module is failure-isolated — one broken analysis is audited as an error
and the rest continue — and every run appends to
`storage/investigation/investigation_audit_log.csv`.

Before Phase 2, the API verifies that each stored item still has its original
file and required forensic artifacts. `CIIS_ANALYSIS_INPUT_POLICY=warn` (the
default) completes a reproducible partial run with visible warnings;
`CIIS_ANALYSIS_INPUT_POLICY=strict` blocks regeneration instead. Missing or
tampered originals are detected against the acquisition SHA-256. Every
completed or quality-blocked run writes a versioned `analysis_manifest.json`
containing input quality, evidence IDs, warnings, runtime/library versions,
semantic validator, threat provider, and the correlation/timeline settings
used.

## Investigator relationship graph

The graph artifact remains complete and audit-friendly: the Python graph
service stores every case, evidence, entity, event and typed relationship in
`graph.json`. NetworkX enriches it with centrality, community, bridge and
maximum-spanning-forest backbone metrics. The frontend never rewrites that
artifact. Instead, Cytoscape.js uses those metrics to prioritize and render
smaller investigator views:

- **Evidence map** (default) projects all relationships between two evidence
  items into one labelled edge. Selecting the edge lists and can reveal its
  underlying phones, wallets, accounts, timestamps and correlations.
- **Timeline flow** places reconstructed events left-to-right by resolved time
  with each source exhibit below it. Green outlines are actual timestamps,
  amber dashed outlines are inferred, and grey dotted outlines are upload-time
  fallbacks.
- **Entity map** shows evidence and extracted entities with Leads, Standard and
  Everything detail levels.
- **Cross-case** isolates entities and evidence shared with other cases.
- **Threats** isolates threat-intelligence hits and their source evidence.
- **Full graph** displays the complete technical artifact for advanced review.

Search always scans the complete artifact, including nodes hidden by the active
view. Confidence, relationship type, entity type and actual/inferred/unresolved
timestamp filters apply without changing stored evidence. Quick presets cover
strong leads, cross-case indicators, threat hits, cryptocurrency trails and
actual-time relationships. View preferences, expansions and viewport are saved
per case in the browser.
The default Structure layout replaces the previous force-directed first view;
Clusters and Circle remain available, and Reset view clears filters and saved
viewport state in one action.

For rendering performance, the frontend caps unreadable overview and focus
views, prevents upload timestamps and shared dates/amounts from inventing
relationships, updates Cytoscape
elements incrementally, and reruns layout only when the visible structure
changes. Investigation, Graph, Timeline, Analytics and Reports are independently
lazy-loaded, so opening a case initially downloads only the overview/evidence
surface. See [the frontend README](ciis_frontend/README.md#relationship-graph).

## Running it

Install Python 3.12 and Node.js 20+ first. Windows also needs Git for Windows
(Git Bash); `dev.cmd` locates it automatically. Ollama is optional for generated
assistant answers and is not required for the deterministic retrieval fallback.

```bash
./dev.sh           # prepare every environment, then start the full project
./dev.sh setup     # prepare without starting (optional)
./dev.sh test      # frontend, API and all core engine suites
./dev.sh threat <url>   # threat engine CLI, in its own venv
```

No virtual-environment activation is required. The launcher calls each
interpreter directly and reinstalls only when that module's requirements
change. On Windows, use `dev.cmd` or run `./dev.sh` from Git Bash. On macOS and
Linux, run `./dev.sh` from the normal terminal. Native macOS OCR is supported
on Apple Silicon (arm64); PaddlePaddle's current macOS wheel no longer supports
Intel Macs.

The RAG environment is managed automatically. Windows uses a short path under
`%LOCALAPPDATA%/CIIS/venvs/rag` to avoid Torch `WinError 206`; macOS and Linux
use `.venv-rag`. `CIIS_RAG_VENV` can override either location.

The frontend then exposes **Ask this case** on every case page. It retrieves
evidence/OCR text, entities and relationships, timeline events, graph summaries,
campaigns, suspects, analytics, priority, reports and legal or regulatory
sections. New evidence triggers a warm index update, and every question checks
freshness incrementally again.

On Windows without a POSIX shell, `dev.cmd` takes the same subcommands.

The threat engine cannot share the platform virtualenv: PaddleOCR needs
`numpy<2` while its ML stack needs `numpy>=2`. RAG is also isolated because it
owns Torch/Chroma. `dev.sh` hides these boundaries behind one-command startup.

## Tests

```bash
cd evidence_ocr_engine          && python -m pytest -q    # 392
cd evidence_correlation_engine  && python -m pytest -q    # 103
cd timeline_report_engine       && python -m pytest -q    #  94
cd ciis_api                     && python -m pytest -q    #  83
cd rag_assistant_engine         && python -m pytest -q    #  44
cd ciis_frontend                && npm test               #  87
```

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs automatically on
every pushed branch and pull request, and can also be started manually from
the GitHub Actions page. Its three isolated jobs run:

- 716 OCR, correlation, timeline/report, API and standalone RAG tests using
  `requirements-ci.txt`, followed by static-analysis and module-boundary gates;
- 409 threat-intelligence tests in their separate NumPy-compatible environment;
- 87 frontend tests, TypeScript checking and the production Vite build.

Normal CI deliberately excludes PaddleOCR/PaddlePaddle and uses the injected
OCR test doubles, keeping checks repeatable and lightweight. Real PP-OCRv5
validation remains an explicit research check:

```bash
cd evidence_ocr_engine
python scripts/validate_sample_case.py
```

After the workflow passes on GitHub, protect the target integration branch in
**Settings → Branches** and require these checks before merging:
`Engines, API and RAG (716 tests)`, `Threat intelligence (409 tests)`, and
`Frontend (87 tests)`.

## Storage

All engines read and write one tree, owned by the OCR engine:

```
evidence_ocr_engine/storage/
  cases.csv  evidence.csv  entities.csv  ocr_results.csv   chain of custody
  json/<CASE_ID>.json                                      full OCR output
  forensics/<EVIDENCE_ID>/                                 Phase-1 reports
  investigation/<CASE_ID>/                                 analysis artifacts
```

The RAG engine stores only a derived, rebuildable Chroma index and manifests
under `rag_assistant_engine/storage/`. That directory is ignored because vector
metadata may reproduce sensitive evidence text; canonical evidence remains in
the storage tree above.

The correlation engine reads that tree strictly read-only through
`CaseDataRepository`; analysis output only ever lands under `investigation/`.
Re-analysis versions artifacts rather than overwriting them.
