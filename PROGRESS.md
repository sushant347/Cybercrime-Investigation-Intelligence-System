# Project Progress

**What this is:** a case-centric digital evidence processing **engine** for
cybercrime investigation. An investigator opens a case by reference, adds
evidence files, and the engine produces correlation, timeline, graph,
analytics, priority, and a report. No accounts, no database for case data.

**Last updated:** 2026-07-23 · branch `engine-refactor`

---

## Status at a glance

| Area | State | Notes |
|---|---|---|
| Phase 1 — evidence acquisition & OCR | ✅ Working | PaddleOCR PP-OCRv5, SHA-256 chain of custody |
| Phase 2 — investigation analysis | ✅ Working | 8 modules, failure-isolated, versioned artifacts |
| Phase 3 — web platform | ✅ Working | React 19 + Django REST |
| Visual investigation report | ✅ Working | Charts from real engine artifacts |
| Engine mode (no login) | ✅ Working | Case reference replaces identity |
| CSV case registry | ✅ Working | `storage/case_registry.csv` |
| Database removal | ⚠️ Partial | Cases are CSV; jobs/notifications/audit still SQLite |
| Threat intelligence ML model | ⚠️ Untrained | Falls back to rule/heuristic scoring |

---

## Done

### Local environment
- Two Python 3.12 virtualenvs — `.venv-platform` (API, OCR, correlation,
  timeline, reports) and `.venv-threat` (phishing ML). Split because
  `paddlepaddle` and the ML stack pin incompatible numpy majors.
- `dev.sh` launcher: `setup` · `api` · `web` · `up` · `reset-db`.
- Frontend deps installed; Django DB migrated.

### Visual investigation report
The Reports tab renders the stored `investigation_report` artifact:
stat cards (evidence, related pairs, priority score/level, timeline stages),
executive summary, four charts (priority breakdown, correlation strength,
OCR confidence per item, evidence quality), attack progression with
milestones, key relationships with engine explanations, chain-of-custody
table, conclusions, recommendations. Every value comes from engine
artifacts — nothing is computed in the browser.

### Engine mode — no login
- Login, RBAC, route guards, and user management removed from the SPA.
- API is open access; `require()` kept as a documented no-op so access
  control can be reinstated in one place.
- Landing page is **Evidence Intake**.

### CSV case registry
- A case reference (`nabil-bank-phishing-2026`) is hashed into a stable id
  (`CASE_EC77C8432C`). Same reference → same case, so the reference is how a
  user returns to their files without an account.
- Matching is case- and whitespace-insensitive.
- Mapping stored in `evidence_ocr_engine/storage/case_registry.csv`.
- Pre-existing sequential cases (`CASE_0001`) still work.

### Fixed
- **Login failure / port collision.** Another local project (`tracker/api`)
  occupies port `8000`, so the Vite proxy was forwarding `/api` to the wrong
  application. CIIS now uses `8001` (`CIIS_API_PORT` overrides).

---

## Next up

1. **Finish removing the database** (on request). Move background jobs,
   notifications, and the activity audit to CSV/JSON; drop `accounts/`,
   the `User` model, `/api/auth/*`, and Django's DB config. This is the
   remaining gap against the "no database" goal.
2. **Multi-file intake.** Upload several evidence files in one action, then
   run the analysis automatically when processing finishes.
3. **Train the phishing model.** `threat_intelligence_system` has no
   checkpoint, so it uses heuristic scoring. Needs a dataset in `DATASET_PATH`.
4. **Wire the threat engine into a case.** Currently a separate CLI; URLs
   extracted from evidence could be scored and folded into the report.
5. **Prune dead platform surface.** `CaseMeta` assignment/tags fields and the
   dashboard's multi-user framing no longer fit engine mode.

---

## Restore points

| Tag / branch | What it is |
|---|---|
| `checkpoint-visual-reports` (on `main`) | Working platform **before** engine mode — login, DB-backed cases, visual report |
| `engine-refactor` | Current work: no login, CSV case registry |

`git checkout main` returns to the pre-refactor state. See `AUDIT.md` for the
full change record.
