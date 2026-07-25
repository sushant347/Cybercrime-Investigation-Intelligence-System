# Change Audit

A record of deliberate architectural changes: what changed, why, and how to
undo it. Newest entry first.

---

## 2026-07-25 — Database removed, admin role added, analytics rebuilt

**Branch:** `feature-new-timeline`

### 1. No database anywhere (approved: full removal → CSV/JSON)
Five Django models were live (`BackgroundJob`, `Notification`, `ActivityLog`,
`CaseMeta`, `CaseHistory`); three (`User`, `RolePermission`, `UserPreference`)
were already dead. All are gone:

- **`api/store.py`** — new file-backed store under `storage/platform/`:
  `jobs.json`, `notifications.json`, `activity_log.csv`, `case_meta.csv`,
  `case_history.csv`. Atomic writes (temp + rename), per-file locks (the upload
  worker writes from a background thread), auto-increment ids for JSON records.
- **Deleted:** `api/models.py`, `api/migrations/`, the whole `accounts/` app,
  and `ciis_platform.sqlite3`.
- **`config/settings.py`** — `DATABASES = {}`; removed `django.contrib.{admin,
  auth,contenttypes,sessions,messages}`, `AUTH_USER_MODEL`, JWT settings and the
  session/auth/message middleware. `UNAUTHENTICATED_USER = None` (there is no
  `AnonymousUser` to import any more).
- **Dropped dependencies:** `djangorestframework-simplejwt`, `django-filter`.
- Serializers are plain dict shapers; `accounts.permissions` → `api/permissions.py`.

### 2. Admin role (shared password)
- **`api/admin_auth.py`** — password check + **stateless signed token**
  (`django.core.signing`), so admin sessions need no table. Password from
  `CIIS_ADMIN_PASSWORD`, default `hello123`; 8-hour expiry.
- **`api/views/admin.py`** — `POST /api/admin/login/`, `GET /api/admin/session/`,
  `GET /api/admin/cases/` (every case + evidence count, analysed flag, linked
  cases), `DELETE /api/admin/cases/<id>/`.
- **Deletion cascade** (`maintenance.delete_case` + `engine.delete_case_cascade`):
  purges the case from the registry, evidence/entity/OCR/processing/audit CSVs,
  its OCR JSON, uploaded originals, Phase-1 forensics and all Phase-2 artifacts,
  and drops it from the cross-case index — then **re-analyses every case that was
  linked to it** so their cross-case correlation, timeline, graph and reports stop
  referencing the deleted case.
- **Frontend:** `features/admin/AdminPage.tsx` (password gate → case table →
  delete dialog spelling out the cascade), `/admin` route, entry point on the
  start page. `apiClient` lost its JWT plumbing and now attaches `X-Admin-Token`.

### 3. Analytics rebuilt
Root cause of the "blank charts": the engine legitimately returns **all-zero
metric dicts** (no threat intel configured, no forensic reports) and **empty
lists** (no URLs/brands/wallets in the evidence). A bar chart of zeros renders as
an empty plot, which looked broken.

- `AnalyticsTab` now leads with four headline stat cards, groups panels into
  "What the engine found" / "How the case fits together" / "Evidence quality",
  and uses a `SmartChart` that detects empty-or-all-zero data and prints a
  plain-language reason instead of an empty chart.
- Quality metrics render as labelled progress bars (with an explicit note when
  forensic scores are 0 because those reports were not generated).

### Verified
API suite **42 passed** (incl. 8 new admin tests) with no database; engine suite
passes; `tsc` clean; production build succeeds. Live: admin login rejects a wrong
password, lists 5 cases, and deleting a case refreshed all 4 linked cases —
`CASE_2CF24DBA5F`'s cross-case artifact went v4→v5 and its report no longer
mentions the deleted case.

### How to undo
```bash
git checkout <commit-before-this-change>
```

---

## 2026-07-25 — Evaluation completion (metrics, harnesses, consolidated output)

**Branch:** `eval-metrics-completion` (from `feature-new-timeline`, which had
already merged the earlier `eval-metrics-remediation` work).

### Why
Complete the evaluation system: fill the remaining reusable-metric gaps, add the
verification/behaviour tests the tables were missing, build the report-review
and master-runner output, and re-verify everything against the **new** timeline/
graph code on `feature-new-timeline`. Hard rules honoured: the verified Table 6.3
XGBoost result was **not** rerun (only read + cross-checked), nothing fabricated,
live modules only.

### Built
- **`investigation/evaluation/classification_metrics.py`** — dependency-free
  confusion matrix, accuracy, precision/recall/F1, FNR/FPR, and rank-based
  ROC-AUC + PR-AUC (average precision). Cross-checked against scikit-learn to
  **0.0e+00** on 2,000 samples. Tests: `tests/investigation/test_classification_metrics.py`.
- **Table 6.3 provenance test** — `threat_intelligence_system/tests/test_table_6_3_source.py`
  asserts the source is the full retraining report (has `test_evaluations`), and
  that every model's stored confusion matrix reproduces its P/R/F1/FNR against
  n=87,756. Skips cleanly if the gitignored artifact is absent. **Does not rerun
  the model.**
- **Table 6.8 posture test** — `ciis_api/api/tests/test_security_posture.py`
  proves the real open-access behaviour (unauthenticated requests are permitted,
  never 401/403), backing the honest row-1 claim with a passing test.
- **Table 6.7 report-review harness** — `scripts/report_review.py` builds a
  gradeable checklist from a real stored report and scores a human-filled review
  (correct/partial/incorrect); refuses to score an ungraded template. Test:
  `tests/evaluation/test_report_review.py`.
- **`run_all_evaluations.py`** (repo root) + **`EVALUATION.md`** — one command
  runs every computable table (real 6.3 + 6.7 output) and prints an honest status
  matrix; the doc lists every table's command, status, and blocker.

### Re-verified on the new code
Engine, API, and threat suites all pass on `feature-new-timeline`'s reworked
timeline/graph modules; the eval harnesses target the **live** services (the
timeline module was un-deprecated on that branch).

### Still blocked (human-only, unchanged)
6.1/6.2 corpus; 6.4/6.5 gold labels; 6.7 manual baseline + report grading. All
have working harnesses that refuse to emit fake numbers.

### How to undo
```bash
git checkout feature-new-timeline
```
Additive: new modules/scripts/tests only; no existing behaviour changed.

---

## 2026-07-25 — Evaluation-metrics remediation (Tables 6.1–6.8)

**Branch:** `eval-metrics-remediation`
**Restore point:** tag `checkpoint-pre-eval-metrics` (on `feature/correlation-addition`)

### Why

Aligning the thesis evaluation tables with what the code actually does — fix or
build real infrastructure, never fabricate a number. Every code change ships
with a test; ground-truth-blocked tables get harnesses, not invented results.

### Phase 0 — re-verification (two real discrepancies caught)
- `AllowAny` still set (`ciis_api/config/settings.py:106`) ✓; both prototypes
  still unimported dead code ✓.
- **Table 6.3 artifacts were absent** on this machine (`results/`, `checkpoints/`
  gitignored, training never run here) — the user supplied them; now placed in
  `threat_intelligence_system/results/` + `checkpoints/` (gitignored).
- The thesis document is **external** to the repo, so table-text edits are given
  as text to paste, not committed.

### What changed / was built

**Table 6.3 (verified, real):** `threat_intelligence_system/scripts/run_table_6_3.py`
regenerates the table from `test_evaluations` in the supplied report (test set
n=87,756); 6/8 checkpoints byte-verified to `run_id 20260712T090000Z`. Test:
`tests/test_table_6_3.py`. Corrected citation: `full_retraining_report_*.json` /
`full_retraining.py` (not `baseline_comparison_report.json` / `train_baselines.py`).

**Table 6.8:**
- Row 1 (JWT): decision **B** — reframed as open-by-design (no code change; text
  supplied).
- Row 4 (oversized upload): `test_upload_rejects_oversized` added to
  `ciis_api/api/tests/test_evidence.py` (>50 MB → 400).
- Row 3 (homoglyph): definitively **live** (features `security_features.py:47-48`
  + rule engine `rule_engine.py:624` → `BrandIntelligenceEngine._detect_homoglyphs`),
  but `MLThreatIntelProvider` surfaces only the final verdict → cite as
  **component-level** (`tests/test_brand_intelligence.py`, 91 pass), not e2e.
- Row 2 (tampering): already real (`tests/test_hash_service.py:34`).

**Table 6.7 (real):** `evidence_ocr_engine/scripts/aggregate_processing_time.py`
sums `duration_ms` per case; **avoids double-counting** the `pipeline` /
`phase2_pipeline` umbrella rows (real CASE_2CF24DBA5F total = **8.0 s**, not the
15.9 s a naive sum gives). Test: `tests/evaluation/test_processing_time.py`.
Manual-workflow + report-correctness cells flagged not-code-derivable.

**Tables 6.4 / 6.5 (infrastructure; numbers await gold):**
- New timestamp-accuracy metric `evaluate_timestamp_accuracy` in `timeline_eval.py`
  (MAE / median / within-tolerance / unresolved-rate; definition in the docstring
  for approval).
- `evaluation/gold_labels.py` (loaders) + `evaluation/correlation_baselines.py`
  (exact-match, unweighted baselines) + gold templates in `samples/ground_truth/`.
- Runners `scripts/run_table_6_4.py` / `run_table_6_5.py` target the **live**
  services (not the deprecated engines); refuse to emit numbers from a template.
- Tests: `tests/investigation/test_eval_infrastructure.py`.

**Tables 6.1 / 6.2 (infrastructure; numbers await corpus):**
- `entity_preservation_rate` added to `ocr_metrics.py` (+ test
  `tests/evaluation/test_entity_preservation.py`).
- `scripts/run_table_6_1.py` (3 OCR stages) refuses the example manifest;
  `scripts/run_table_6_2.py` (regex / spaCy / full) flags spaCy as a new optional
  dependency and skips cleanly when absent.
- **Entity-type count:** extractor emits **28** types, not the thesis's "22" —
  surfaced, not reconciled.

### Problems faced (and how they were resolved)

1. **Table 6.3's data source did not exist on this machine.** The audit/guide
   said the numbers were "already sitting in `results/`", but
   `results/full_retraining_report_*.json` and `checkpoints/` are gitignored
   (`.gitignore:46`) and training was never run here — so nothing was
   verifiable locally. Phase 0 caught this; rather than paste the guide's prose
   numbers (which would be trusting text over evidence), we **stopped and asked
   the author to supply the files**, then verified every value against the real
   JSON and byte-checked 6 of 8 checkpoints to `run_id 20260712T090000Z`.
2. **The thesis document is not in the repo.** Phase 1 assumed a "report text"
   to edit; the actual Tables 6.1–6.8 live in an external thesis. So the
   citation fix and the 6.8 row-1 reframe are delivered as **text to paste**,
   not code changes — and no in-repo "report" was invented to edit.
3. **Processing-time double-counting (6.7).** The first aggregation summed every
   `duration_ms` row and reported **15.9 s**. Inspection showed `pipeline`
   (per-evidence) and `phase2_pipeline` (per-case) are **umbrella** rows whose
   duration already includes their sub-stages — summing both double-counts. The
   script was reworked to use the umbrella as the authoritative total (real
   CASE_2CF24DBA5F = **8.0 s**), with leaves shown as an informational
   breakdown only. A regression test locks this in.
4. **`pytest-django` was missing from the platform venv.** The whole API test
   suite errored at collection (DRF settings unconfigured) even for pre-existing
   tests. It is declared in `ciis_api/requirements.txt` but was never installed
   in `.venv-platform`; installing it fixed collection. (Not a code bug — an
   environment gap.)
5. **Homoglyph wiring was ambiguous (6.8 row 3).** Determining whether the live
   path actually runs `_detect_homoglyphs` required tracing
   `MLThreatIntelProvider → PhishingPredictor.predict → RuleEngine →
   BrandIntelligenceEngine.analyze`. Conclusion: it **is** live (also as ML
   features), but the provider only surfaces the final verdict — so we cite it
   honestly at **component level**, not end-to-end, rather than over-claim.
6. **Entity-type count mismatch.** The extractor emits **28** types, not the
   thesis's "22". Surfaced explicitly (with the full list) instead of silently
   reconciling either direction.
7. **Everything else is genuinely blocked on human data.** 6.4/6.5 need gold
   labels; 6.1/6.2 need a 30–100 sample bilingual corpus; 6.7's manual-workflow
   cell needs a cited estimate. The harnesses were built and their math
   unit-tested, but the runners **refuse to emit numbers from a template** — a
   deliberate non-fabrication guard, proven with a synthetic-gold wiring test.
8. **Minor:** zsh glob-expanded `grep --include=*.py` (fixed by quoting); the
   timeline wiring test exposed a real finding — the engine falls back to
   `upload_time`, so content-timestamp MAE will be large once real gold exists.

### Verified
Full engine suite passes (incl. all new eval tests); API evidence tests pass
(after installing the declared `pytest-django`); threat `test_table_6_3` +
`test_brand_intelligence` pass. No number was fabricated: every blocked table
stops and states its blocker.

### How to undo
```bash
git checkout feature/correlation-addition   # or: git checkout checkpoint-pre-eval-metrics
```
Additive: reverting the listed files removes the harnesses and leaves the
engines unchanged.

---

## 2026-07-24 — Cross-case entity correlation

**Branch:** `feature/correlation-addition` (from `feature/roadmap-implementation`)

### Why

Entities were correlated only *within* a single case. Investigators needed to
know when a phone, wallet, URL or email in one case also appears in another —
automatically, on both cases, without a separate tool.

### Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Where the logic lives | Extended the existing `CorrelationService` + `InvestigationReportService` | The brief required extending the integrated services, not a new engine |
| Persistent store | `storage/investigation/cross_case_index.json` | A storage helper (like `repository.py`), keyed to dedup entity records; no database |
| What links two cases | Shared **normalized** entities of a *weighted* type (phone/email/url/domain/wallet/bank/social) | Reuses the within-case weights, so cross-case confidence is on the same scale; unweighted noise (otp/amount) is excluded |
| Scoring | `1 - exp(-Σ weight / normaliser)` with per-type cap, then the existing relationship bands | Identical explainable framework as within-case correlation |
| Bidirectional update | Analysing a case recomputes + re-saves the linked cases' cross-case artifact and regenerates their report — **only when changed** | Links appear on both sides without duplicate correlations or report-version spam; one hop, no recursion |
| Reset (“clear cache”) | `POST /api/maintenance/reset/` + Start-page button with confirm | Testing aid; truncates CSVs to headers and clears artifacts/index/index, scoped strictly to engine storage |

### Changed

**Engine** (`evidence_ocr_engine/backend/modules/investigation/`)
- `crosscase.py` — **new.** Persistent entity index (upsert/dedup, per-case
  removal, clear, atomic save, lookups).
- `correlation/models.py` — added `CrossCaseEntityMatch`, `CrossCaseLink`,
  `CrossCaseCorrelation`.
- `correlation/service.py` — added `index_case_entities`,
  `correlate_cross_case`, `persist_cross_case` (save-if-changed) and link
  scoring. Existing within-case correlation untouched.
- `reporting/service.py` — new `cross_case_correlation` report section +
  executive-summary line + markdown title, and `regenerate_with_cross_case`
  (rebuilds a report from stored artifacts for propagation).
- `pipeline.py` — indexes entities, runs cross-case, threads it into the
  report, and propagates to linked cases.
- `config.py` — cross-case artifact/index names, index path,
  `cross_case_min_shared_entities`.
- `maintenance.py` — **new.** `reset_all` (storage wipe, guarded to storage dir).
- `tests/investigation/test_cross_case_correlation.py` — **new.** exact,
  normalized, no-match, unweighted-excluded, duplicate-processing idempotence,
  bidirectional report update, reset.

**API** (`ciis_api/`)
- `api/engine.py` — `cross_case` artifact key; `reset_engine_storage()`.
- `api/views/maintenance.py` — **new.** `ResetView` (also clears Django jobs,
  notifications, audit, case metadata).
- `api/urls.py` — `maintenance/reset/` route.

**Frontend** (`ciis_frontend/`)
- `InvestigationTab.tsx` — Cross-Case Correlation panel (linked cases, shared
  entities, confidence).
- Report: `reportModel.ts` / `SimpleReportView.tsx` / `reportHtml.ts` — a
  "Linked Other Cases" summary row + section in the readable report and the
  HTML download.
- `StartPage.tsx` — "Clear all data (testing)" button + confirm dialog.
- `api/index.ts`, `types/index.ts` — `investigationApi.crossCase`,
  `maintenanceApi.reset`, cross-case types.

### Verified

- Full engine suite passes (incl. 7 new cross-case tests); `tsc` clean; Django
  check clean; production build succeeds.
- End-to-end through the API + browser: two cases sharing entities linked
  VERY_STRONG (0.86, 4 shared entities); the first case auto-updated to
  artifact v2 and report v2; the panel and readable report both show the link;
  reset cleared every CSV/artifact/index and made the cases unresolvable.

### How to undo

```bash
git checkout feature/roadmap-implementation   # the branch this was cut from
```

The feature is additive: reverting the listed files removes cross-case behaviour
and leaves within-case correlation exactly as it was.

### Follow-up (same day) — entity-type coverage fix

Manual testing surfaced a real gap: correlation only counted **7 hardcoded
entity types** (`phones, emails, urls, domains, wallets, bank_accounts,
social_accounts`), but the Phase-1 extractor emits a much larger vocabulary and
does not even produce `wallets`/`social_accounts` — it produces `esewa_ids`,
`khalti_ids`, `imepay_ids`, `eth_wallets`, `btc_wallets`, `whatsapp_numbers`,
`telegram_usernames`, `facebook_usernames`, `instagram_usernames`,
`social_media_urls`, `ipv4/ipv6`, `mac_addresses`, `money`, etc. So shared
wallets/social handles were silently ignored, and cases sharing only weaker
types (`money`) produced **no** cross-case link at all.

- `config.py` — `correlation_weights` expanded to the full extractor vocabulary;
  new `correlation_entity_types` tuple enumerates the linkable identifiers.
  `dates`/`times` stay excluded (the timeline module owns temporal correlation);
  `money`/`otp` are included at low weight (visible but WEAK).
- `correlation/service.py` — within-case (`correlate_pair`) and cross-case both
  iterate `config.correlation_entity_types` instead of the old hardcoded tuple.
- Tests updated: temporal types don't link; `esewa_ids` links; a shared `money`
  value links WEAKly (the exact manual-test scenario).

Verified: the user's scenario (two cases sharing `money Rs 2000`) now links; with
real samples the cross-case panel shows 3 linked cases where it previously showed
0. Cause of the original "no output": the redacted samples
(`+977-98XXXXXXXX`, `esewa id 98XXXXXXXX`) yield no clean phone/wallet, only
`dates`/`times`/`money`, and `money` was not a linkable type.

---

## 2026-07-23 — Guided one-screen flow + readable report

**Branch:** `guided-flow`
**Restore point:** `engine-refactor` @ tag `checkpoint-engine-mode`

### Why

Two problems with the previous stage:

1. **Every case was visible to everyone.** The intake page listed the whole
   case registry and the API exposed case-listing endpoints. With no accounts,
   a case reference is the only thing protecting a case — so listing them
   defeated the point.
2. **The report was unreadable.** It was accurate but written for someone who
   already understood the engine: eight charts, raw metric names, and
   artifact filenames in the prose.

### Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Navigation | One screen at a time: choose → identify case → work | Requested; also removes every cross-case view |
| Case discovery | None. Reference only | A case is private to whoever knows its reference |
| Listing endpoints | Removed from the API, not just hidden in the UI | Hiding in the SPA is not privacy; the API was the actual leak |
| "Open existing" with an unknown reference | Says not found, offers to create | Reveals nothing about which cases exist |
| "New case" with a taken reference | Refuses, offers to open it | A reference maps to one case; never silently join someone else's |
| Report style | Summary table of verdicts + plain sentences, modelled on the URLVoid scan layout supplied | Reads top-to-bottom without forensic training |
| Old chart report | Kept behind a "Charts & detail" toggle | Still useful; no longer the default |
| Download format | Self-contained HTML (inline CSS, no assets) | Opens anywhere offline, prints to PDF, emails as one file |

### Changed

**API** (`ciis_api/`)
- `api/views/intake.py` — **removed the `GET` listing.** `POST /api/intake/`
  and `GET /api/intake/resolve/` remain; both require knowing the reference.
- `api/urls.py` — removed `cases/` (list), `dashboard/`, `audit/`, and
  `notifications/` routes. Every remaining case route addresses one known id.
- `api/views/cases.py` — case detail now returns `case_reference` from the
  registry (the report is titled by it).

**Frontend** (`ciis_frontend/`)
- `src/features/intake/StartPage.tsx` — **new.** Two choices, no case list.
- `src/features/intake/NewCasePage.tsx` — **new.** Checks the reference is free,
  then creates and enters the case.
- `src/features/intake/OpenCasePage.tsx` — **new.** Resolves a reference;
  never creates.
- `src/features/reports/reportModel.ts` — **new.** Derives a plain-language
  view-model from the engine artifacts (labels, badges, "what this means"
  glosses, de-duplicated findings). Pure presentation — no new scoring.
- `src/features/reports/SimpleReportView.tsx` — **new.** On-screen report.
- `src/features/reports/reportHtml.ts` — **new.** Standalone HTML download,
  built from the same model so screen and file cannot drift. Escapes
  user-supplied filenames.
- `src/features/reports/ReportsTab.tsx` — summary report by default;
  "Charts & detail" toggle; "Download report" button.
- `src/features/cases/CaseDetailPage.tsx` — Run Analysis now navigates to the
  report and refreshes it when the engine has written it.
- `src/app/router.tsx` — routes: `/`, `/new`, `/open`, `/cases/:caseId/:tab`,
  `/settings`. No dashboard, cases list, audit, or notifications.
- `src/components/layout/AppLayout.tsx`, `Topbar.tsx` — single column, minimal
  header (identity + theme). Sidebar deleted.
- **Removed:** `IntakePage`, `CasesPage`, `DashboardPage`, `AuditPage`,
  `NotificationsPage`, `NotificationsPopover`, `Sidebar`.

### Verified

- 382 engine tests pass; `tsc --noEmit` clean; production build succeeds.
- Privacy: `GET /api/intake/` → 405, `GET /api/cases/` → 404,
  `GET /api/dashboard/` → 404. `intake/resolve/` still works *with* a reference.
- Unknown reference in the UI → "No case found", no hint that others exist.
- Report renders from real artifacts: verdict badges, evidence table,
  progression, findings.
- Download produces 5.7 KB self-contained HTML — no external references —
  and renders correctly when opened.

### Not done (deliberate)

- Jobs, notifications, and the activity audit still use SQLite (unchanged).
- The removed pages still exist in git history at
  `checkpoint-engine-mode` if any are wanted back.
- Deleting a case is still not possible from the UI.

### How to undo

```bash
git checkout engine-refactor   # previous stage: intake list, chart report
git checkout main              # original: login + DB-backed cases
```

---

## 2026-07-23 — Engine mode: no login, CSV case registry

**Branch:** `engine-refactor`
**Restore point:** `main` @ tag `checkpoint-visual-reports`

### Why

The project is a **case-centric digital evidence processing engine**, not a
multi-user case management system. Accounts, RBAC, and a login wall modelled
the wrong thing: an investigator should be able to open the tool, drop files
in, and get output. Identity was replaced by the **case reference**.

A second goal: keep structured records in CSV, not a database. The forensic
engine was already built this way (`csv_storage.py` explicitly documents "no
PostgreSQL / MongoDB / Neo4j / Redis"); only the Django platform layer had
drifted into SQLite.

### Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Case identity | `CASE_<10 hex>` = SHA-256 of the normalised reference | Deterministic: the same reference always reopens the same case, so a reference replaces a login as the way back to your files |
| Reference matching | Case- and whitespace-insensitive | `"Nabil Bank"`, `"nabil  bank"` resolve to one case |
| Case mapping store | `evidence_ocr_engine/storage/case_registry.csv` | No database, per project goal |
| Existing sequential ids | Left working | `CASE_0001`-style cases still load; ids are opaque to the engine |
| RBAC removal | `require()` kept as a documented no-op | One edit disables access control everywhere and leaves a clear restore path |
| DB removal scope | Cases only, this pass | Jobs / notifications / audit stay on SQLite until explicitly removed (user's call) |

### Changed

**Engine** (`evidence_ocr_engine/`)
- `backend/modules/evidence/case_registry.py` — **new.** Reference
  normalisation, `make_case_id()` hashing, and the CSV registry
  (`resolve_or_create`, `get_by_reference`, `list_all`, `touch`).
- `backend/modules/evidence/config.py` — added `case_registry_csv` (dataclass
  field + `from_env`).
- `backend/modules/evidence/csv_storage.py` — `CaseRepository.create()` takes
  an optional `case_id`; omitting it keeps the original sequential behaviour.

**API** (`ciis_api/`)
- `api/views/intake.py` — **new.** `GET/POST /api/intake/`,
  `GET /api/intake/resolve/`.
- `api/engine.py` — added `case_registry()` and `intake_case()`; `create_case()`
  accepts an explicit id. `intake_case` reconciles the registry with
  `cases.csv` and holds the engine write lock.
- `api/urls.py` — registered the intake routes.
- `accounts/permissions.py` — `require()` is now open access (no-op).
- `config/settings.py` — default DRF permission `IsAuthenticated` → `AllowAny`.
- `api/models.py` — `Notification.user` nullable; `broadcast()` writes one
  engine-wide row instead of one per user.
- `api/views/notifications.py`, `api/views/dashboard.py` — notifications are
  engine-wide, no per-user filtering.
- `api/views/cases.py` — dropped `has_platform_permission` checks and the
  `created_by` user link.
- `api/migrations/0002_alter_notification_user.py` — **new.**

**Frontend** (`ciis_frontend/`)
- `src/features/intake/IntakePage.tsx` — **new.** The landing page: open a case
  by reference, see the registry, jump into evidence upload.
- `src/features/auth/AuthContext.tsx` — reduced to an engine session
  (`hasPermission` no-op); no login, logout, tokens, or user.
- `src/features/auth/LoginPage.tsx`, `src/features/auth/RequireAuth.tsx`,
  `src/features/users/` — **removed.**
- `src/app/router.tsx` — `/` is intake, dashboard moved to `/dashboard`, no
  route guards, `/login` and `/admin/users` gone.
- `src/components/layout/Sidebar.tsx`, `Topbar.tsx` — removed account menu,
  sign-out, and the RBAC nav filter.
- `src/features/settings/SettingsPage.tsx` — account-backed "My Preferences"
  replaced by a browser-local "Appearance" tab.
- `src/api/index.ts`, `src/types/index.ts` — `intakeApi` + `RegisteredCase`.
- `vite.config.ts`, `dev.sh` — API port 8000 → **8001**.

### Port change (incidental fix)

Port `8000` on this machine is held by an unrelated local project
(`tracker/api`, uvicorn). The Vite proxy pointed `/api` → `8000`, so the SPA
was silently talking to the wrong application — the likely cause of the
"cannot log in any more" symptom. CIIS now defaults to `8001`
(`CIIS_API_PORT` overrides). The other project was left running.

### Verified

- 382 engine tests pass (`pytest` in `evidence_ocr_engine/`) — Phase 1/2 intact.
- `tsc --noEmit` clean.
- Hashing: deterministic, normalised, distinct references differ.
- Full pipeline on a hash id `CASE_EC77C8432C`, unauthenticated: upload →
  OCR (`EVID_00006`) → analysis → report v1 served.
- Same reference re-entered returns `created: false` and the same case id.
- Empty reference rejected (400).
- Browser: intake → `CASE_F8997BCF8C` → evidence tab, no login anywhere.

### Not done (deliberate)

- Jobs, notifications, and activity audit still use SQLite.
- `accounts/` app, `User` model, and `/api/auth/*` endpoints still exist,
  now unused by the SPA.
- `seed_demo` still creates demo users; harmless, no longer needed to log in.

### How to undo

```bash
git checkout main          # back to the pre-refactor state
```

`main` is unchanged at tag `checkpoint-visual-reports`. To discard the work
entirely: `git branch -D engine-refactor`.
