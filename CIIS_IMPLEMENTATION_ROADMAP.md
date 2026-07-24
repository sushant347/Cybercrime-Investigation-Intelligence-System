# CIIS — Implementation Roadmap to Completion

Companion to `CIIS_IMPLEMENTATION_AUDIT.md`. This is a practical, sequenced development
plan. Each remaining feature has: **why · files to modify · dependencies · complexity ·
risks · order · defense gate.** Complexity is rated **S** (≤1 day), **M** (2–3 days),
**L** (4–7 days). Every file path is real and taken from the audited source.

**Legend for "Gate":** `MID` = do before mid-term defense · `FINAL` = required before final
defense · `POST` = optional / post-defense polish.

---

## Implementation status — updated 2026-07-24

| ID | Status | Notes |
|---|---|---|
| **F1** | ✅ Done | `submit_evidence_job` now runs `EvidenceProcessingOrchestrator` after OCR (failure-isolated, inside `_pipeline_lock`, `CIIS_RUN_FULL_PIPELINE` flag). Fixed an idempotency bug: entity/keyword CSV rows are now upserted per evidence (`csv_storage.delete_where`). |
| **F2** | ✅ Harness done | `evidence/evaluation/ocr_metrics.py` (CER/WER) + `scripts/benchmark_ocr.py` + tests + `samples/ground_truth/`. Real numbers require a human-annotated corpus (documented). |
| **F3** | ✅ Harness done | `evidence/evaluation/entity_metrics.py` (P/R/F1) + `scripts/benchmark_entities.py` + tests. Needs a labelled entity gold set for real numbers. |
| **F4** | ✅ Done | `ciis_api/api/tests/` — 22 integration tests (intake→upload→enrich→analyze→report) with fake OCR + temp storage. Proves F1 end-to-end. |
| **F5** | ✅ Harness done | `investigation/evaluation/{correlation_eval,timeline_eval}.py` + tests. Needs annotated cases for real numbers. |
| **F7** | ✅ Done | Env-driven `DEBUG`/`SECRET_KEY`/hosts, Postgres option, static/media, security headers, logging, `.env.example`. |
| **F11** | ◑ Partial | Nav "Back to cases" → "/" fixed; upload file-type/size validation confirmed already present; broader doc reconciliation ongoing. |
| **F6** | ✅ Done (integrated) | `investigation/ml_threat_intel.py::MLThreatIntelProvider` adapts the phishing classifier behind the `ThreatIntelProvider` interface (lazy load, graceful degradation). Wired via `engine._threat_intel_provider()` into `build_default_pipeline` when `CIIS_ML_THREAT_INTEL=1`. Verified against the trained xgboost artifact. |
| **F8** | ✅ Done (routed) | Dashboard/audit/notifications endpoints routed + notification bell wired (see below). |
| **F9** | ✅ Done | Vitest + Testing-Library set up (`vite.config.ts` test block, `src/test/`), with tests for `apiClient` error mapping, format utils, and the `NotificationBell`. Run locally with `npm install && npm test`. |
| **F10** | ◑ Deprecated in place | The 3 superseded modules (`evidence_correlation_engine`, `timeline_reconstruction`, `report generation`) each carry a `DEPRECATED.md` pointing at the integrated engine. Physical move to `archive/` deferred (host FS permissions); zero code imports them. |

---

## A. The critical path in one sentence

Wire the Phase-1 text chain into the API (F1) → generate real research metrics (F2, F3, F5)
→ prove it with tests (F4) → integrate or scope-out the ML threat system (F6) → harden and
clean up (F7–F11). F1 unblocks almost everything else, so it goes first.

---

## F1 — Wire the full Phase-1 chain into the API upload path

**1. Why needed.** The web upload currently stops at OCR. `api/engine.py::_evidence_pipeline()`
builds a plain `EvidencePipeline` (OCR + hash + storage only), so cleaning, enhancement,
semantic correction and **entity extraction never run for web-uploaded evidence**. Because
Phase-2 correlation/graph/campaigns/suspects read `storage/entities.csv`, they are starved
of input for any case created through the UI. This is the single break that makes the
end-to-end demo not truly end-to-end.

**2. Files to modify.**
- `ciis_api/api/engine.py` — replace/extend `_evidence_pipeline()` and the `work()` body of
  `submit_evidence_job()` to call `EvidenceProcessingOrchestrator` after OCR.
- `evidence_ocr_engine/backend/modules/evidence/semantic/orchestrator.py` — reuse
  `EvidenceProcessingOrchestrator` (no change expected; verify its constructor/DI).
- `ciis_api/api/views/evidence.py` — no change if the job contract stays the same.
- (Optional) `ciis_api/api/models.py::BackgroundJob.detail` — extend to report per-stage status.

**3. Dependencies.** None external — the orchestrator, cleaning, enhancement and semantic
services already exist and are tested. Depends only on the existing `_pipeline_lock` to keep
CSV writes serialized.

**4. Complexity.** **S–M** (0.5–1.5 days). Mostly composition + one integration test run.

**5. Risks.**
- *Performance:* the semantic/enhancement chain is heavier than OCR; a synchronous run inside
  the worker could lengthen job time — acceptable because it already runs in a background
  `ThreadPoolExecutor`. Watch memory (dictionaries/knowledge base load).
- *Concurrency:* multiple stages now write CSVs (`entities.csv`, `keyword_statistics.csv`) —
  keep everything inside `_pipeline_lock`.
- *Idempotency:* re-processing the same evidence must not duplicate entity rows — confirm the
  cleaning storage upserts or is keyed by `evidence_id`.
- *Regression:* OCR-only callers (tests, CLI) must remain intact — add the chain in the API
  layer, not inside `EvidencePipeline`.

**6. Order.** **#1 — do this first.** It unblocks F3, F5 and a credible live demo.

**7. Gate.** **MID.** Without it the demo depends on manually pre-seeded data.

---

## F2 — OCR accuracy metrics (CER / WER)

**1. Why needed.** This is an OCR-forensics project; the audit found **no** CER/WER/accuracy
computation anywhere in `evidence_ocr_engine`. There is no defensible OCR quality number to
put in the report or defend on the stand.

**2. Files to modify / create.**
- New `evidence_ocr_engine/backend/modules/evidence/evaluation/ocr_metrics.py` — CER/WER via
  edit distance (e.g. `jiwer` or a small Levenshtein implementation).
- New `evidence_ocr_engine/scripts/benchmark_ocr.py` — run OCR over a labelled set, emit a JSON
  report + summary.
- New `evidence_ocr_engine/tests/evaluation/test_ocr_metrics.py`.
- New data folder `evidence_ocr_engine/samples/ground_truth/` — images + reference transcripts.

**3. Dependencies.** A **labelled ground-truth set** (images with human transcripts). Optional
`jiwer` package. This is the real blocker — not code, but data.

**4. Complexity.** **M** (2–3 days), most of it building/annotating the ground-truth set.

**5. Risks.**
- *Data availability:* need 30–100 representative labelled samples (English + Nepali, given the
  dual dictionaries) or numbers won't be credible.
- *Metric definition:* be explicit about normalization (case, whitespace, Unicode) so CER/WER
  are reproducible — document it next to the script.
- *Cherry-picking:* report the full distribution, not just the best case.

**6. Order.** **#2**, immediately after F1 (so you can also measure the effect of the
enhancement/semantic stages on CER/WER — a strong research result).

**7. Gate.** **FINAL** (a small subset is nice to show at **MID** to prove the methodology).

---

## F3 — Entity extraction Precision / Recall / F1

**1. Why needed.** Entity extraction feeds every Phase-2 module, yet there is no validation of
how well it extracts URLs/emails/phones/wallets/hashes. The audit confirmed no entity P/R/F1
anywhere in the engine.

**2. Files to modify / create.**
- New `evidence_ocr_engine/backend/modules/evidence/evaluation/entity_metrics.py` —
  precision/recall/F1 per entity type against a labelled gold set.
- New `evidence_ocr_engine/scripts/benchmark_entities.py`.
- New `evidence_ocr_engine/tests/evaluation/test_entity_metrics.py`.
- Reuses output of `evidence/cleaning/entity_extractor.py` → `storage/entities.csv`.

**3. Dependencies.** F1 (so entities are actually produced by the pipeline) + a **labelled
entity gold set** (same corpus as F2 ideally).

**4. Complexity.** **M** (1–2 days once the gold set exists; share annotation effort with F2).

**5. Risks.**
- *Matching rules:* define exact vs normalized matching (e.g. trailing-slash URLs, phone
  formats) — ambiguous matching inflates or deflates scores.
- *Type confusion:* count per-type and micro/macro-averaged so a common type doesn't mask a
  weak one.

**6. Order.** **#3**, right after F2 (shared corpus, shared harness pattern).

**7. Gate.** **FINAL.**

---

## F4 — API integration tests

**1. Why needed.** `ciis_api` has **zero** tests. The API is the integration seam that binds
UI ↔ engine; without tests, F1 and every later change risk silent breakage of the
intake → upload → analyze → report flow.

**2. Files to modify / create.**
- New `ciis_api/api/tests/__init__.py`
- New `ciis_api/api/tests/test_intake.py`, `test_evidence.py`, `test_investigation.py`,
  `test_reports.py`, `test_engine_bridge.py`.
- Possibly a `conftest.py` with a temporary `ENGINE_ROOT` + seeded storage fixture.
- Reference: `accounts/management/commands/seed_demo.py` for seed logic.

**3. Dependencies.** Django test client + pytest-django (add to `ciis_api/requirements.txt`).
F1 should land first so tests assert the *full* pipeline, not the OCR-only one.

**4. Complexity.** **M** (1–2 days).

**5. Risks.**
- *Heavy engine in tests:* real OCR/PaddleOCR is slow — inject a fake OCR (`BaseOCR`) and a
  temporary storage dir so tests stay fast and deterministic.
- *Background workers:* `ThreadPoolExecutor` is async — tests must run jobs synchronously
  (call the `work()` closure directly, or a test-mode flag).

**6. Order.** **#4**, after F1 (and ideally after F2/F3 so metric scripts are covered too).

**7. Gate.** **FINAL** (a couple of smoke tests are worth having by **MID**).

---

## F5 — Correlation & timeline accuracy evaluation

**1. Why needed.** Phase-2 is the intellectual core, but there is no ground-truth evaluation of
whether correlations/timelines are *correct*. To defend "the system links related evidence"
you need measured accuracy, not just that code runs.

**2. Files to modify / create.**
- New `evidence_ocr_engine/backend/modules/investigation/evaluation/` — `correlation_eval.py`,
  `timeline_eval.py` (compare produced pairs/order against annotated truth).
- New `evidence_ocr_engine/tests/investigation/test_evaluation.py`.
- Uses `investigation/correlation/service.py`, `timeline/service.py` outputs.

**3. Dependencies.** F1 (entities) + a small set of **annotated cases** (which evidence pairs
are truly related; the true event order).

**4. Complexity.** **M–L** (2–3 days; annotation is the cost).

**5. Risks.**
- *Subjectivity:* "related" is fuzzy — write annotation guidelines and, ideally, have a second
  annotator for a subset to report agreement.
- *Small-n:* with few cases, report per-case results honestly rather than a single headline
  number.

**6. Order.** **#5**, after F1–F4.

**7. Gate.** **FINAL.**

---

## F6 — Integrate (or formally scope-out) the ML threat-intel system

**1. Why needed.** "Threat Intelligence" in the running product is only a static indicator-file
lookup (`investigation/data_access.py::ThreatIntelProvider`). Meanwhile a 133-file ML classifier
(`threat_intelligence_system/`) with real benchmarks sits unintegrated. Either connect it —
turning a documented capability into a real one — or explicitly declare it out of the
integrated scope so the mismatch isn't a defense liability.

**2. Files to modify.**
- `evidence_ocr_engine/backend/modules/investigation/data_access.py` — add an adapter that
  implements the `ThreatIntelProvider` interface (`available()`, `lookup()`, `is_malicious()`)
  by calling the ML system.
- `evidence_ocr_engine/backend/modules/investigation/pipeline.py::build_default_pipeline(threat_intel=…)`
  — inject the adapter.
- `threat_intelligence_system/cli.py` / prediction module — expose a callable prediction API.
- `ciis_api/api/engine.py` — wire the chosen provider into `build_default_pipeline`.

**3. Dependencies.** A trained model artifact in `threat_intelligence_system/checkpoints/`;
its Python deps (transformers/catboost/xgboost) added to the environment.

**4. Complexity.** **L** (2–4 days) — mostly interface adaptation, dependency reconciliation,
and latency management.

**5. Risks.**
- *Dependency weight:* the ML stack is heavy; loading it inside the Django process could bloat
  memory and startup. Prefer a lazy, cached loader (mirror `engine.py::_evidence_pipeline`'s
  `lru_cache` pattern) or an out-of-process call.
- *Scope creep:* full integration is the biggest single item — if time is tight, the
  scope-out decision is a legitimate, defensible choice.
- *Input mismatch:* the classifier scores URLs; make sure entities of type URL are what you
  feed it.

**6. Order.** **#6**, after the metric/test foundation. Make the integrate-vs-scope-out call
**before** starting.

**7. Gate.** **FINAL** (or explicitly deferred/scoped-out with a written justification).

---

## F7 — Production hardening

**1. Why needed.** Defaults are dev-grade: `DEBUG=1` (`config/settings.py:21`), SQLite,
in-process worker, no media/static config. Fine for a demo, not for any deployed/graded
"production readiness" claim.

**2. Files to modify.**
- `ciis_api/config/settings.py` — env-driven `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, DB
  (Postgres option), media/static roots, logging levels.
- `ciis_api/requirements.txt` — add `psycopg`/`gunicorn` as needed.
- New `ciis_api/.env.example` + a short deploy note in `GETTING_STARTED.md`.
- `dev.sh` — parametrize.

**3. Dependencies.** A target environment decision (local Postgres vs container).

**4. Complexity.** **M** (1–2 days).

**5. Risks.**
- *Storage model:* the engine uses CSV/JSON as source of truth; DB change only affects
  workflow tables (`api/models.py`). Don't accidentally couple engine storage to the DB.
- *Concurrency ceiling:* CSV + global `_pipeline_lock` won't scale horizontally — document
  this as a known limitation rather than trying to fix it now.

**6. Order.** **#7.**

**7. Gate.** **FINAL** (basic env-driven `DEBUG`/`SECRET_KEY` is cheap enough to do at **MID**).

---

## F8 — Route or remove Dashboard / Audit / Notifications

**1. Why needed.** `api/views/dashboard.py`, `audit.py`, `notifications.py` exist but are
**not routed** in `api/urls.py`; the matching frontend clients (`dashboardApi`, `auditApi`,
`notificationsApi`) are defined but unused and hit dead URLs. Notifications are *written* by
`engine.py` but never *served*. Decide: expose them, or delete the dead surface.

**2. Files to modify.**
- To expose: `ciis_api/api/urls.py` (add routes), `ciis_frontend/src/api/index.ts` (already
  present), plus a small UI (e.g. a notification bell using the orphaned
  `features/notifications/notificationIcon.tsx`).
- To remove: delete the three view modules + the dead client groups.

**3. Dependencies.** A product decision (does engine-mode want a notifications UI?).

**4. Complexity.** **S** (0.5 day either direction).

**5. Risks.** Low. If exposing, remember there are no accounts in engine mode, so
notifications are engine-wide (`Notification.broadcast`, `user=None`).

**6. Order.** **#8** (cleanup phase).

**7. Gate.** **POST** (or **FINAL** if you want the notifications feature to count).

---

## F9 — Frontend tests

**1. Why needed.** Zero `*.test.*` files. Key tabs (evidence upload, investigation, reports)
have real logic (React Query states, artifact rendering) that regresses silently.

**2. Files to modify / create.**
- Add `vitest` + `@testing-library/react` to `ciis_frontend/package.json`.
- New `ciis_frontend/src/features/**/__tests__/*.test.tsx` for InvestigationTab, EvidenceTab,
  ReportsTab, and `lib/apiClient` error mapping.
- `ciis_frontend/vite.config` test setup.

**3. Dependencies.** Test tooling only.

**4. Complexity.** **M** (1–2 days).

**5. Risks.** Low. Mock the API layer (`src/api/index.ts`) so tests don't hit a live backend.

**6. Order.** **#9.**

**7. Gate.** **FINAL** (a couple of smoke tests optional at MID).

---

## F10 — Remove duplicate / legacy root modules

**1. Why needed.** `evidence_correlation_engine/`, `timeline_reconstruction/`, and
`report generation/` duplicate the integrated engine's `investigation/{correlation,graph,
timeline,reporting}`. `reporting/service.py:10` explicitly calls the last one "legacy …
untouched." They add confusion and dead code to the repo.

**2. Files to modify.**
- Move `evidence_correlation_engine/`, `timeline_reconstruction/`, `report generation/` into an
  `archive/` folder (or delete after confirming nothing imports them — the audit confirmed
  zero imports from `ciis_api`/engine).
- Also prune frontend dead code: `features/cases/CreateCaseDialog.tsx`,
  `features/notifications/notificationIcon.tsx` (if not used by F8), and the unused client
  groups in `src/api/index.ts`.

**3. Dependencies.** Confirm F8 first (notificationIcon may be revived there).

**4. Complexity.** **S** (0.5 day).

**5. Risks.** Low — but do it on a branch and run the full test suite + a UI smoke test after,
in case a stray import exists.

**6. Order.** **#10** (final cleanup).

**7. Gate.** **POST.**

---

## F11 — Small fixes & documentation reconciliation

**1. Why needed.** Minor correctness/UX and keeping docs honest for the defense.
- `CaseDetailPage.tsx:126` `navigate("/cases")` targets a non-existent route (wildcard
  redirects to `/`); fix the target/label.
- Add file-type/size validation at `api/views/evidence.py` upload.
- Reconcile the older audit/status docs with the code reality (this repo has several `.md`
  audits with differing claims).

**2. Files to modify.** `ciis_frontend/src/features/cases/CaseDetailPage.tsx`,
`ciis_api/api/views/evidence.py`, the various root `*.md` docs.

**3. Dependencies.** None.

**4. Complexity.** **S** (0.5 day total).

**5. Risks.** Low.

**6. Order.** Fold into whichever sprint has slack; the nav/validation fixes are quick wins for
**MID**.

**7. Gate.** Nav fix **MID**; doc reconciliation **FINAL**.

---

## B. Priority ranking (all remaining tasks)

### 🔴 Critical — the project's credibility depends on these
| ID | Task | Gate | Complexity |
|---|---|---|---|
| F1 | Wire Phase-1 chain into API upload | MID | S–M |
| F2 | OCR CER/WER metrics | FINAL (subset MID) | M |
| F3 | Entity P/R/F1 metrics | FINAL | M |
| F4 | API integration tests | FINAL (smoke MID) | M |

### 🟠 High — required for a strong final defense
| ID | Task | Gate | Complexity |
|---|---|---|---|
| F5 | Correlation/timeline accuracy eval | FINAL | M–L |
| F6 | Integrate or scope-out ML threat intel | FINAL | L |
| F7 | Production hardening | FINAL (basics MID) | M |

### 🟡 Medium — quality, completeness, professionalism
| ID | Task | Gate | Complexity |
|---|---|---|---|
| F8 | Route/remove dashboard-audit-notifications | POST/FINAL | S |
| F9 | Frontend tests | FINAL | M |
| F11 | Nav fix + upload validation + doc reconciliation | MID/FINAL | S |

### 🟢 Low — cleanup / polish
| ID | Task | Gate | Complexity |
|---|---|---|---|
| F10 | Remove duplicate/legacy root modules + dead code | POST | S |
| — | Usability evaluation (if research scope requires it) | FINAL/POST | M |
| — | Restore or delete dormant auth/RBAC layer | POST | M |

---

## C. Sequenced plan (sprints)

**Sprint 0 — Foundation & demo-readiness (before MID) · ~3–4 days**
F1 (pipeline wiring) → F11 quick wins (nav fix, upload validation) → 2–3 API smoke tests from
F4 → a small F2 subset to demonstrate the CER/WER methodology. Pre-run "Run Analysis" on a
demo case so every Phase-2 tab is populated. **Outcome: a true end-to-end live demo.**

**Sprint 1 — Research metrics (between MID and FINAL) · ~5–6 days**
Build/annotate the shared ground-truth corpus, then F2 (CER/WER, incl. before/after the
enhancement+semantic stages), F3 (entity P/R/F1), F5 (correlation/timeline accuracy).
**Outcome: defensible, reproducible numbers for the report.**

**Sprint 2 — Robustness (before FINAL) · ~4–5 days**
Complete F4 (full API test suite), F9 (frontend tests), F7 (production settings).
**Outcome: change-safe, deployable build with coverage evidence.**

**Sprint 3 — Threat-intel decision (before FINAL) · ~2–4 days**
Make the F6 integrate-vs-scope-out call early; if integrating, adapt the ML system behind
`ThreatIntelProvider`. **Outcome: threat intelligence is either real or honestly scoped-out.**

**Sprint 4 — Cleanup & polish (FINAL/POST) · ~1–2 days**
F8 (route or remove), F10 (archive duplicates + prune dead code), F11 doc reconciliation.
**Outcome: a clean, professional repository that matches its documentation.**

---

## D. Defense-gate summary

**Must be done before MID:** F1, F11 (nav/validation), API smoke tests, a pre-analyzed demo
case, and a small CER/WER sample to show methodology.

**Must be done before FINAL:** F2, F3, F4 (full), F5, F7, F9, and an explicit F6 decision.
Every research metric in the write-up must trace to a script and a data set in the repo.

**Optional / POST:** F8 (unless notifications are a graded feature), F10, usability study,
auth restoration.

---

## E. Effort at a glance

| Phase | Items | Rough effort |
|---|---|---|
| Sprint 0 (MID) | F1, F11, smoke tests, F2-subset | 3–4 days |
| Sprint 1 | F2, F3, F5 (+ corpus) | 5–6 days |
| Sprint 2 | F4, F9, F7 | 4–5 days |
| Sprint 3 | F6 | 2–4 days |
| Sprint 4 | F8, F10, docs | 1–2 days |
| **Total** | | **~15–21 working days** |

The largest single risk across the whole plan is **data, not code**: F2/F3/F5 all hinge on a
labelled ground-truth corpus. Start annotating that corpus in parallel with Sprint 0 so it is
ready when the metric sprints begin.
