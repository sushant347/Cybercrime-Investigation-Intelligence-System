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
./dev.sh up          # API :8001 + frontend :5173 together
./dev.sh api         # just the Django API
./dev.sh web         # just the Vite dev server
./dev.sh reset-db    # wipe platform DB (jobs/notifications/audit only)
./dev.sh setup       # rebuild everything from scratch
```

Open **http://localhost:5173**. **There is no login** — this is an engine, not
a multi-user system. You land on Evidence Intake.

> **Port note:** the API runs on **8001**, not 8000. Another local project on
> this machine (`tracker/api`) occupies 8000, and the Vite proxy would
> otherwise forward `/api` to the wrong application — which is what made the
> app appear broken/unloggable. Override with `CIIS_API_PORT=xxxx ./dev.sh up`.

## How you find your case again (no accounts)

You identify a case by a **case reference** you make up, e.g.
`nabil-bank-phishing-2026`. The engine hashes it into a stable id:

```
"Nabil Bank Phishing 2026"  ->  CASE_7F3A9C2E11
```

Typing the same reference later reopens the **same** case with its evidence and
reports — the reference is your handle instead of a login. Matching ignores
capitalisation and extra spaces. The mapping lives in
`evidence_ocr_engine/storage/case_registry.csv`; there is no database for case
data.

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

The flow is one screen at a time. Nothing ever lists your cases: a case is
private to whoever knows its reference.

1. **Start screen** — choose **Start a new case** or **Open an existing case**.
2. **New case:** type a reference, e.g. `esewa-lottery-scam-2026` (plus an
   optional title) → **Create case**. If the reference is already taken it says
   so and offers to open it instead.
   **Existing case:** type the reference → **Open case**. An unknown reference
   reports "No case found" and offers to create it.
3. You land on the case's **Evidence** tab. **Upload** — use anything from
   `evidence_ocr_engine/samples/` (`scam_sms_screenshot.png` and
   `phishing_email_screenshot.png` are the clearest demos). Upload runs OCR in a
   background worker; the UI polls the job.
4. **Run Analysis** (top right) — builds correlation, graph, timeline,
   campaigns, suspects, and priority, then takes you straight to the report.
5. **Reports tab** — the report in plain language:

   - a **Report Summary** table of verdicts — case priority, evidence
     integrity, linked evidence pairs, text-recognition quality — each with a
     coloured badge and a one-line explanation of what it means;
   - **What We Found**, **How The Scam Progressed**, **Evidence Examined**,
     **Links Between Evidence**, **Recommended Next Steps**.

   **Download report** saves it as a single self-contained HTML file that opens
   offline and prints to PDF. **Charts & detail** switches to the chart-heavy
   view, and the engine's own versioned JSON/Markdown files are listed below.
6. **Graph / Timeline / Analytics tabs** — the other artifact views.

Every figure in the report comes from the stored engine artifacts; the report
layer only relabels and explains them.

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
- **SQLite is still used for plumbing.** Case data is CSV, but background jobs,
  notifications, and the activity audit still live in `ciis_platform.sqlite3`.
  Removing them is the next step (see `PROGRESS.md`).
- **Leftover account machinery.** The `accounts/` app and `/api/auth/*` endpoints
  still exist but nothing uses them; `seed_demo` is no longer needed.

## Going back

| Command | Result |
|---|---|
| `git checkout main` | Original: login, DB-backed cases, chart report |
| `git checkout engine-refactor` | No login + CSV registry, but cases listed and report chart-heavy |
| `git checkout guided-flow` | Current: one-screen flow, case privacy, readable report |

Tagged restore points: `checkpoint-visual-reports`, `checkpoint-engine-mode`.
`AUDIT.md` records exactly what changed and why at each stage; `PROGRESS.md`
tracks overall project state and what's next.
