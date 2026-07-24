# Project Progress

**What this is:** a case-centric digital evidence processing **engine** for
cybercrime investigation. An investigator opens a case by reference, adds
evidence files, and the engine produces correlation, timeline, graph,
analytics, priority, and a report. No accounts, no database for case data.

**Last updated:** 2026-07-23 · branch `guided-flow`

---

## Status at a glance

| Area | State | Notes |
|---|---|---|
| Phase 1 — evidence acquisition & OCR | ✅ Working | PaddleOCR PP-OCRv5, SHA-256 chain of custody |
| Phase 2 — investigation analysis | ✅ Working | 8 modules, failure-isolated, versioned artifacts |
| Phase 3 — web platform | ✅ Working | React 19 + Django REST |
| Readable investigation report | ✅ Working | Summary table + plain findings, HTML download |
| Engine mode (no login) | ✅ Working | Case reference replaces identity |
| CSV case registry | ✅ Working | `storage/case_registry.csv` |
| Case privacy | ✅ Working | Nothing lists cases — API or UI |
| Guided one-screen flow | ✅ Working | Choose → identify case → work on it |
| Cross-case entity correlation | ✅ Working | Persistent JSON index; auto bidirectional link + report update |
| Clear-all-data reset | ✅ Working | Testing button + `POST /api/maintenance/reset/` |
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

### Readable investigation report
The Reports tab opens on a plain-language report modelled on a URLVoid-style
scan summary: a **Report Summary** table of verdicts (priority, evidence
integrity, linked pairs, text-recognition quality) with coloured badges and a
one-line explanation of each, then *What We Found*, *How The Scam Progressed*,
*Evidence Examined*, *Links Between Evidence*, and *Recommended Next Steps*.

- It appears on screen as soon as the analysis finishes.
- **Download report** produces a self-contained HTML file (no external assets)
  that opens offline and prints to PDF.
- The earlier chart-heavy view is still available under **Charts & detail**.
- Every value comes from engine artifacts — nothing is computed in the browser.

### Guided flow & case privacy
The UI is one screen at a time: **choose** (new / existing) → **identify the
case by reference** → **work on it**. There is no dashboard, case list, audit
page, or sidebar, so one case never exposes another. The case-listing API
endpoints were removed too — hiding them in the SPA would not have been
privacy. An unknown reference simply reports "not found".

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
| `checkpoint-visual-reports` (on `main`) | Original platform — login, DB-backed cases, chart report |
| `checkpoint-engine-mode` (on `engine-refactor`) | No login + CSV case registry, but cases were listed and the report was chart-heavy |
| `guided-flow` | Current: one-screen flow, case privacy, readable report |

Go back with `git checkout <tag or branch>`. See `AUDIT.md` for the full
change record of each stage.
