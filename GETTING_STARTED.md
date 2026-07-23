# CIIS — Local Environment & Walkthrough

Verified working on macOS (Apple Silicon, arm64) on 2026-07-16.

## What got installed

| Environment | Python | Serves |
|---|---|---|
| `.venv-platform` | 3.12.13 | `ciis_api` (Django/DRF), `evidence_ocr_engine` (PaddleOCR), `evidence_correlation_engine`, `timeline_reconstruction`, `report generation` |
| `.venv-threat` | 3.12.13 | `threat_intelligence_system` (XGBoost/LightGBM/sklearn) |
| `ciis_frontend/node_modules` | Node 24.15 | React 19 + Vite SPA |

**Why two venvs:** `paddlepaddle` (OCR) and the threat-intel ML stack resolve to
different numpy majors. Keeping them separate avoids an unsolvable pin conflict.

**Why not the system Python:** macOS ships 3.9; every engine here needs ≥3.12.
Both venvs are built from Homebrew's `/opt/homebrew/bin/python3.12`.

## Everyday use

```bash
./dev.sh up          # API :8000 + frontend :5173 together
./dev.sh api         # just the Django API
./dev.sh web         # just the Vite dev server
./dev.sh reset-db    # wipe platform DB, re-seed demo users
./dev.sh setup       # rebuild everything from scratch
```

Open **http://localhost:5173** and sign in. Seeded accounts all use password
`Ciis@Demo2026`:

| User | Role |
|---|---|
| `admin` | administrator (full access) |
| `investigator` | create cases, upload evidence, run analysis |
| `analyst` | read + analyze |
| `viewer` | read-only |

Start with `admin`, then log in as `viewer` to see RBAC hide the write actions.

## The production pipeline (what runs where)

The end-to-end pipeline is wired through `ciis_api/api/engine.py` — the single
bridge between the platform and the forensic engines:

1. **Evidence upload** → `POST /api/cases/<id>/evidence/upload/` queues
   `EvidencePipeline.process_file` (Phase 1: OCR, hashing, chain of custody)
   in a background worker; the UI polls `jobs/<n>/`.
2. **Run Analysis** → `POST /api/cases/<id>/analyze/` queues
   `build_default_pipeline().analyze_case(case_id)` (Phase 2: correlation →
   graph → campaigns → suspects → timeline → analytics → priority → report).
   Each run writes a new immutable artifact version under
   `evidence_ocr_engine/storage/investigation/<CASE_ID>/`.
3. **Every tab** (Graph, Timeline, Analytics, **Reports**) renders those stored
   artifacts verbatim — no score or verdict is ever computed in the browser.

## Walkthrough — the web platform

1. **Dashboard** — counters are zero on a fresh DB. That's expected; the platform
   DB and the engine's own storage are separate.
2. **Cases → New Case** — create one.
3. **Evidence tab → Upload** — use anything from `evidence_ocr_engine/samples/`
   (`scam_sms_screenshot.png` and `phishing_email_screenshot.png` are the clearest
   demos). Upload runs OCR in a background worker; the UI polls the job.
4. **Investigation tab → Run Analysis** — builds correlation, graph, timeline,
   campaigns, suspects, priority.
5. **Reports tab** — renders the full **visual investigation report**: headline
   stat cards (evidence count, related pairs, engine priority score/level,
   timeline stages), executive summary, charts (priority score breakdown,
   correlation strength distribution, OCR confidence per evidence, evidence
   quality), the attack-progression timeline with milestones, key evidence
   relationships with engine explanations, chain-of-custody table, conclusions,
   and recommendations. Every chart is fed by the stored engine artifacts —
   the versioned JSON/Markdown report history (preview + download) sits below.
6. **Graph / Timeline / Analytics tabs** — the other artifact views.

Tabs show a 503/empty state until analysis has run for that case — that's the
designed behavior, not a bug. Re-running analysis bumps the report version;
reports are never overwritten.

## Walkthrough — the engines directly (no web UI)

Already smoke-tested; all of these ran clean:

```bash
# OCR — extracts text + entities. Created CASE_0001 at 97.7% confidence.
cd evidence_ocr_engine
../.venv-platform/bin/python cli.py ingest samples/scam_sms_screenshot.png --title "Demo"
../.venv-platform/bin/python cli.py list-cases
../.venv-platform/bin/python cli.py show-case CASE_0001

# Correlation — found 7 shared-entity links across 2 test cases
cd ../evidence_correlation_engine
../.venv-platform/bin/python correlation_engine.py tests/case_0021_test.json tests/case_0042_test.json

# Timeline (takes case files positionally, no --help flag)
cd ../timeline_reconstruction
../.venv-platform/bin/python timeline_reconstruction.py ../evidence_correlation_engine/tests/case_0021_test.json

# Report → PDF or Markdown
cd "../report generation"
../.venv-platform/bin/python report_generator.py ../timeline_reconstruction/output/timeline.json --format md

# Phishing URL detection (separate venv)
cd ../threat_intelligence_system
../.venv-threat/bin/python cli.py "http://paypa1-secure-login.tk/verify" --no-intel --no-resolve
```

## Known caveats

- **First OCR run is slow.** PaddleOCR downloads PP-OCRv5 models on first use.
  Already done — subsequent runs are fast.
- **No trained phishing model checkpoint.** `threat_intelligence_system` has no
  `checkpoints/xgboost.pkl`, so it logs "Model not trained -- using feature-based
  heuristic" and falls back to the rule engine. Verdicts still work (the test URL
  scored 44/100 SUSPICIOUS), but they're heuristic, not ML. Train a model to get
  real ML scoring — that needs a dataset in `DATASET_PATH`.
- **Optional deps skipped.** `easyocr`/`torch` (multi-OCR fusion) and
  `transformers` (semantic correction) are commented out of the requirements and
  not installed — both engines degrade gracefully without them. The `tesseract`
  binary *is* on your PATH already if you want to add `pytesseract`.
- **API keys unset.** `threat_intelligence_system/.env.example` wants
  `VIRUSTOTAL_API_KEY` / `MAXMIND_LICENSE_KEY`. Without them, use `--no-intel`
  (as above) or those connectors just return nothing.
- **Engine settings are read-only in the UI** by design — the engine owns its
  config via `EVIDENCE_*` / `INVESTIGATION_*` env vars.
