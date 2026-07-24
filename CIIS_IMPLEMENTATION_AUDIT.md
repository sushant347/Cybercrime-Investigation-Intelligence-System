# CIIS — Complete Implementation Audit

**Cybercrime Investigation Intelligence System**
Audit date: 2026-07-24 · Method: **source-code inspection** (not documentation).
Every claim below references a real file, class, function, endpoint, or on-disk artifact.

> **Reading note.** Where a capability is documented but absent in code it is marked
> **"Documented but not implemented."** Where it exists but is incomplete it is marked
> **"Partially implemented."** Nothing here is inferred from the `.md` docs alone.

---

## 0. Architecture as actually built (ground truth)

The repository is **not** a single app. It is **seven** top-level units, and only three of
them are wired together into the live product:

| Unit | Role | Wired into the running product? | Evidence |
|---|---|---|---|
| `ciis_api/` | Django REST API — a **read-only bridge** over the engine | ✅ Yes | `ciis_api/api/engine.py` |
| `ciis_frontend/` | React 19 + Vite + MUI + React Query SPA | ✅ Yes | `ciis_frontend/src/app/router.tsx` |
| `evidence_ocr_engine/` | The **core engine**: Phase-1 (OCR/forensics) + Phase-2 (investigation) | ✅ Yes | `settings.ENGINE_ROOT`, `engine.py` imports `backend.modules.*` |
| `threat_intelligence_system/` | 133-file ML URL-threat classifier | ❌ **Standalone, not imported** | no reference from `ciis_api` or engine |
| `evidence_correlation_engine/` | 3-file prototype correlation/graph | ❌ **Superseded / dead** | duplicated by `investigation/correlation` + `graph` |
| `timeline_reconstruction/` | 1-file prototype timeline | ❌ **Superseded / dead** | duplicated by `investigation/timeline` |
| `report generation/` | 1-file `report_generator.py` | ❌ **Legacy, explicitly retired** | `reporting/service.py:10` "The legacy `report generation` module is untouched" |

**The single most important structural fact:** the API imports the engine from
`settings.ENGINE_ROOT = evidence_ocr_engine` (`ciis_api/config/settings.py:14`) and touches it
**only** through `ciis_api/api/engine.py`. The four root-level modules
(`threat_intelligence_system`, `evidence_correlation_engine`, `timeline_reconstruction`,
`report generation`) are **not imported anywhere** in `ciis_api` or the engine — verified by
grep returning zero import references. They are parallel research/prototype code.

---

## 1. Overall Project Status

| Dimension | Completion | Justification (source-based) |
|---|---:|---|
| **Overall** | **~70%** | Core engine is genuinely strong and tested; the API/UX shell is clean but thin; a real pipeline-integration gap and missing research metrics pull the weighted score down. |
| **Backend (Django API)** | **~80%** | All engine-mode endpoints implemented cleanly (`api/views/*`, `api/engine.py`), good error isolation. Deductions: **zero API tests**, and 3 view modules (`dashboard.py`, `audit.py`, `notifications.py`) exist but are **not routed** in `api/urls.py`. |
| **Frontend** | **~75%** | 7 case tabs + intake flow fully wired to real endpoints. Deductions: dead API client groups + 2 orphaned components, **zero frontend tests**, a broken "Back to cases" nav target. |
| **Investigation Engine (Phase-2)** | **~90%** | All 8 modules implemented, DI-composed, failure-isolated, and unit-tested (`investigation/pipeline.py`, 8 `service.py`, 8 test files). Deduction: no ground-truth accuracy validation; `storage/investigation/` is currently empty (artifacts are on-demand). |
| **OCR / Phase-1 Engine** | **~85% built, integration-gapped** | OCR, preprocessing, hashing, cleaning, enhancement, semantic, forensics all implemented + 30+ tests. **But the API upload path runs OCR + storage only** — cleaning/enhancement/semantic/entity-extraction are not invoked by the API (see §6). |
| **Research** | **~40%** | Real precision/recall/F1/AUC + benchmarks exist **only** in the standalone `threat_intelligence_system`. **No CER/WER/OCR-accuracy, no entity P/R/F1, no correlation/timeline accuracy** anywhere in the integrated engine. |
| **Production readiness** | **~40%** | SQLite, `DEBUG=1` default (`settings.py:21`), engine-mode has no auth, in-process `ThreadPoolExecutor(max_workers=2)`, CSV storage is not concurrency-safe (guarded by a single global lock), no API/UI tests. Fine for a demo, not for production. |

---

## 2. What SHOULD Be Present (per architecture)

For each module: **Purpose · Expected functionality · Expected APIs · Expected frontend · Expected outputs.**

1. **Case Management** — create/open/track a case. *Fn:* reference→case-id, status, history. *API:* `POST /intake/`, `GET /cases/{id}/`, `/history/`, `/archive/`. *UI:* Start/New/Open pages, case overview + history tabs. *Out:* `cases.csv`, `CaseMeta`, `CaseHistory`.
2. **Evidence Upload** — ingest a file into a case. *API:* `POST /cases/{id}/evidence/upload/`. *UI:* Upload dialog, Evidence tab. *Out:* stored original, `evidence.csv` row, `BackgroundJob`.
3. **SHA-256 Hashing** — chain-of-custody integrity (before/after). *Out:* hash fields in `evidence.csv`, verification in processing log.
4. **OCR** — text extraction per page. *Out:* `ocr_results.csv`, `storage/json/<CASE>.json`.
5. **Image Preprocessing** — deskew/denoise/threshold before OCR.
6. **OCR Enhancement** — confidence/context/confusion correction.
7. **Semantic Correction** — knowledge-base + candidate-based correction with entity protection.
8. **Entity Extraction** — URLs/emails/phones/wallets/hashes → `entities.csv`.
9. **Threat Intelligence** — flag malicious indicators. *Out:* threat-intel lookups feeding correlation/suspects.
10. **Brand / Logo Intelligence** — detect impersonated brand logos (forensics).
11. **Evidence Correlation** — pairwise relationship scoring. *API artifact:* `correlation`.
12. **Network Graph** — entity/evidence relationship graph + statistics. *Artifacts:* `graph`, `graph_statistics`, `graph_summary`.
13. **Timeline Reconstruction** — chronological event ordering + narrative. *Artifact:* `timeline`.
14. **Campaign Detection** — cluster evidence into campaigns. *Artifact:* `campaigns`.
15. **Suspect Assessment** — score suspect entities. *Artifact:* `suspects`.
16. **Investigation Analytics** — case/entity statistics. *Artifacts:* `analytics`, `case_statistics`, `entity_statistics`.
17. **Report Generation** — investigator-facing MD/JSON report. *Artifact:* `report`; *API:* `/reports/…`.
18. **Dashboard** — cross-case operational overview.
19. **Testing** — unit/integration coverage across all layers.
20. **Documentation** — architecture + usage docs.

---

## 3. What Has Been Achieved (fully implemented)

### 3.1 Core engine — Phase-1 acquisition (OCR)
- **Status:** Implemented + tested.
- **Files:** `evidence_ocr_engine/backend/modules/evidence/pipeline.py` (285 LOC), `paddle_service.py`, `preprocessing.py`, `hash_service.py`, `json_storage.py`, `csv_storage.py`, `pdf_processor.py`.
- **Classes/fn:** `EvidencePipeline.process_file()` orchestrates `upload → hash(before) → preprocessing → OCR (per page) → hash(after)+verify → CSV+JSON storage`; `HashService`, `ImagePreprocessor`, `PDFProcessor`, `JSONCaseStorage`.
- **Evidence:** `storage/evidence.csv`, `storage/ocr_results.csv`, `storage/json/CASE_*.json` (14 populated cases on disk). Tests: `tests/test_pipeline_and_errors.py`, `test_ocr.py`, `test_hash_service.py`, `test_pdf_processor.py`, `test_json_storage.py`, `test_csv_storage.py`, `test_upload.py`.

### 3.2 Cleaning · Enhancement · Semantic (as libraries)
- **Status:** Implemented + tested **as standalone services** (see §4/§6 for the integration caveat).
- **Files:** `evidence/cleaning/*` (13 files incl. `cleaning_pipeline.py`, `entity_extractor.py`, `noise_cleaner.py`, `language_detector.py`), `evidence/enhancement/*` (15 files incl. `enhancement_pipeline.py`, `confidence_corrector.py`, `context_corrector.py`, `character_confusion.py`, `english_dictionary.py`, `nepali_dictionary.py`), `evidence/semantic/*` (12 files incl. `semantic_pipeline.py`, `orchestrator.py`, `knowledge_base.py`, `candidate_generator.py`, `entity_protection.py`).
- **Orchestrator:** `semantic/orchestrator.py::EvidenceProcessingOrchestrator` chains `OCR → CleaningService.clean_case → EnhancementService.enhance_case → SemanticCorrectionService.correct_case`.
- **Evidence:** `storage/entities.csv`, `storage/keyword_statistics.csv`, `storage/ocr_corrections.csv` populated. Tests: `tests/cleaning/*` (6), `tests/enhancement/*` (5), `tests/semantic/*` (3).

### 3.3 Forensics (integrity, forgery, metadata, logos, quality, multi-OCR fusion)
- **Status:** Implemented + tested.
- **Files:** `evidence/forensics/*` — `forgery/service.py`, `integrity/service.py`, `metadata/service.py`, `logos/service.py` + `registry.py`, `quality/service.py`, `confidence/service.py`, `advanced_preprocessing/service.py`, `multi_ocr/fusion.py`, `pipeline.py`, `repository.py`. Also `evidence/ocr_forensics/*` (analyzer, duplicate, chat_reconstruction, image_quality, language).
- **Evidence:** `forensics_cli.py`; tests `tests/forensics/*` (10 files) + `tests/ocr_forensics/test_ocr_forensics.py`. **Brand/Logo intelligence = the `logos` forensics module.**

### 3.4 Investigation engine — Phase-2 (all 8 modules)
- **Status:** Fully implemented, DI-composed, failure-isolated, tested.
- **Orchestrator:** `investigation/pipeline.py::InvestigationPipeline.analyze_case()` + `build_default_pipeline()` (DI root). Each module wrapped in `safe()` so one failure never aborts the case.
- **Modules / files / tests:**
  - Correlation — `correlation/service.py` (277 LOC, 15 fns) · `tests/investigation/test_correlation.py`
  - Graph — `graph/service.py` (319 LOC, 13 fns) · `test_graph.py`
  - Campaigns — `campaigns/service.py` (252 LOC, 8 fns) · `test_campaigns.py`
  - Suspects — `suspects/service.py` (272 LOC, 10 fns) · `test_suspects.py`
  - Timeline — `timeline/service.py` (232 LOC, 10 fns) · `test_timeline.py`
  - Analytics — `analytics/service.py` (253 LOC, 11 fns) · `test_analytics_priority.py`
  - Prioritization — `prioritization/service.py` (202 LOC, 6 fns) · `test_analytics_priority.py`
  - Reporting — `reporting/service.py` (456 LOC, 19 fns) · `test_reporting_pipeline.py`
- **Outputs:** MD + JSON artifacts via `InvestigationReportRepository` (versioned) — `investigation_report.md/.json`, `correlation_analysis.json`, `graph*.json`, `campaign_analysis.json`, `suspect_assessment.json`, `timeline_analysis.json`, `analytics.json`, `case_priority.json`.
- **Entry point:** `investigation_cli.py`.

### 3.5 Django API (engine-mode)
- **Status:** Implemented.
- **Files/endpoints (`api/urls.py`):**
  - Intake — `intake.IntakeView` (`POST /api/intake/`), `IntakeResolveView` (`GET /api/intake/resolve/`)
  - Cases — `cases.CaseDetailView` `/cases/{id}/`, `CaseArchiveView`, `CaseHistoryView`
  - Evidence — `evidence.EvidenceListView`, `EvidenceUploadView`, `EvidenceDetailView`, `EvidenceDownloadView`, `JobListView`, `JobStatusView`
  - Investigation — `investigation.ArtifactIndexView` `/artifacts/`, `ArtifactView` `/artifacts/{key}/`, `RunAnalysisView` `POST /analyze/`
  - Reports — `reports.ReportListView`, `ReportLatestView`, `ReportDownloadView`
  - System — `system.SystemSettingsView` `/settings/`
- **Bridge:** `api/engine.py` — CSV/JSON readers, artifact loaders (`ARTIFACTS` map), background workers `submit_evidence_job` / `submit_analysis_job` (`ThreadPoolExecutor`, `_pipeline_lock`), notification broadcasting, `engine_health()`.
- **Models:** `api/models.py` — `CaseMeta`, `CaseHistory`, `Notification`, `ActivityLog`, `BackgroundJob`.

### 3.6 Auth / Accounts app (implemented but unused by the UI)
- **Status:** Implemented server-side, **not consumed by the frontend** (engine mode).
- **Files:** `accounts/` — `models.py` (custom `User`), `views.py` (`LoginView`, `LogoutView`, `MeView`, `UserViewSet`, `RolePermissionView`), `permissions.py`, `serializers.py`, `urls.py` (JWT via `rest_framework_simplejwt`), `management/commands/seed_demo.py`.
- **Caveat:** Frontend `features/auth/AuthContext.tsx` is a **documented no-op** (`hasPermission: () => true`); `authApi` in `src/api/index.ts` is never called. So RBAC exists in the backend but is dormant.

### 3.7 Frontend (engine-mode SPA)
- **Status:** Implemented for the engine-mode scope.
- **Router (`app/router.tsx`):** Start `/`, New `/new`, Open `/open`, Case `/cases/:caseId/:tab`, Evidence `/cases/:caseId/evidence/:evidenceId`, Settings `/settings`.
- **Case tabs (`features/cases/CaseDetailPage.tsx`):** overview, evidence, investigation, graph, timeline, analytics, reports, history — all wired to real endpoints via `src/api/index.ts` + React Query.
- **Notable components:** `GraphCanvas.tsx` (cytoscape), `OcrResultsView.tsx`, `EvidencePreview.tsx`, `reportHtml.ts`/`reportModel.ts`, common component kit (`StatCard`, `ConfidenceBar`, `StatusChip`, `JsonViewer`, …).

### 3.8 Threat classifier research (standalone)
- **Status:** Implemented + benchmarked, **but unintegrated.**
- **Files:** `threat_intelligence_system/src/{models,ensemble,feature_engineering,evaluation,training,…}` (133 py files), `cli.py`, `run_benchmark.py`, `train_*.py`.
- **Evidence:** `src/evaluation/cross_validation.py` computes accuracy/precision/recall/F1/ROC-AUC/PR-AUC/MCC; `results/baseline_comparison_report.json`, `results/benchmarks/benchmark_history.jsonl`, `results/reports/{confusion_matrix,calibration_curve,feature_importance}_xgboost.{png,pdf}`. 23 test files.

---

## 4. What Is Partially Implemented

### 4.1 Phase-1 text-processing chain in the *live product*
- **Current:** Cleaning/Enhancement/Semantic/Entity-extraction are complete and tested **as libraries** and runnable via `evidence_ocr_engine/cli.py` (`EvidenceProcessingOrchestrator`).
- **Missing:** They are **not invoked by the API upload path.** `api/engine.py::_evidence_pipeline()` builds a plain `EvidencePipeline` whose docstring states it does *"acquisition, hashing, preprocessing, OCR and storage ONLY — no text cleaning, language detection, entity extraction."*
- **Files to modify:** `api/engine.py` (`_evidence_pipeline`, `submit_evidence_job`) to call `EvidenceProcessingOrchestrator` after OCR.
- **Effort:** ~0.5–1 day. **Why incomplete:** the API was built as a thin OCR bridge; the richer chain was left CLI-only.

### 4.2 Threat Intelligence (integrated)
- **Current:** `investigation/data_access.py::ThreatIntelProvider` = static indicator-file lookup (`storage/investigation/threat_intel_indicators.json`) with `lookup()`/`is_malicious()`.
- **Missing:** No connection to the 133-file ML `threat_intelligence_system`; no live feeds (VirusTotal etc.). **Partially implemented.**
- **Files:** `investigation/data_access.py`, `investigation/pipeline.py::build_default_pipeline(threat_intel=…)`.
- **Effort:** 2–4 days to adapt the ML system behind the `ThreatIntelProvider` interface.

### 4.3 Notifications / Audit / Dashboard (backend)
- **Current:** View modules **exist**: `api/views/notifications.py` (39 LOC), `audit.py` (72 LOC), `dashboard.py` (86 LOC); models `Notification`/`ActivityLog` exist and are written to by `engine.py`.
- **Missing:** **None of these are routed** in `api/urls.py`. So notifications are *written* but not *served*; dashboard/audit endpoints are unreachable. Frontend `dashboardApi`/`auditApi`/`notificationsApi` therefore hit dead URLs (they are currently unused — see §7). **Partially implemented (write-only).**
- **Effort:** ~0.5 day to re-route + re-wire UI.

### 4.4 On-disk Phase-2 artifacts
- **Current:** `storage/investigation/` is **empty** — no case has generated artifacts yet. The `/analyze/` endpoint and pipeline are present; artifacts are produced on demand.
- **Impact:** A fresh clone shows empty Investigation/Graph/Timeline/Analytics tabs until "Run Analysis" is executed. **Partially populated.**

---

## 5. What Is Still Missing

| Missing item | Why required | Where it belongs | Files to modify | Dependencies | Priority |
|---|---|---|---|---|---|
| **OCR accuracy metrics (CER/WER)** | Core research claim of an OCR project | New `evidence/evaluation/` + `scripts/benchmark_ocr.py` | new files; ground-truth set | labelled transcripts | **Critical** |
| **Entity extraction P/R/F1** | Validates entity module | `evidence/cleaning/` eval harness | new eval script | labelled entities | **Critical** |
| **Correlation / timeline accuracy** | Validates Phase-2 quality | `investigation/evaluation/` | new files | ground-truth cases | High |
| **API integration tests** | `ciis_api` has **zero** tests | `ciis_api/api/tests/` | new `test_*.py` | Django test client | High |
| **Frontend tests** | zero `*.test.*` files | `ciis_frontend/src/**` | vitest + RTL setup | test tooling | Medium |
| **Live threat-intel integration** | "Threat Intelligence" is static-file only | `investigation/data_access.py` | adapter to ML system | `threat_intelligence_system` | Medium |
| **Cross-case Dashboard (if in scope)** | Deliberately absent in engine mode | `api/views/dashboard.py` + new UI page | route + page | product decision | Low/Optional |
| **Production hardening** | `DEBUG=1`, SQLite, no auth | `config/settings.py` | env config | deploy target | Medium |

---

## 6. Integration Status (end-to-end workflow)

| Stage | Status | Evidence / where it breaks |
|---|:--:|---|
| Case Creation | ✅ | `intake.IntakeView` → `engine.intake_case` → `case_registry.resolve_or_create` |
| Evidence Upload | ✅ | `EvidenceUploadView` → `engine.submit_evidence_job` |
| SHA-256 Hash | ✅ | `EvidencePipeline` hash(before)+hash(after)+verify; `HashService` |
| OCR | ✅ | `EvidencePipeline._ocr_image_page` → `PaddleOCRService` |
| Cleaning | ⚠️ | Implemented + tested, **but not called by the API pipeline** (CLI-only) |
| Enhancement | ⚠️ | Same — orchestrator exists (`semantic/orchestrator.py`), API doesn't call it |
| Semantic Correction | ⚠️ | Same |
| Entity Extraction | ⚠️ | `entities.csv` written by `CleaningService`, **not by the API upload** → API-uploaded evidence produces no entities |
| Threat Intelligence | ⚠️ | Static indicator-file lookup only; ML system not wired |
| Evidence Correlation | ✅* | `CorrelationService` runs — *but quality depends on entities that the API path doesn't produce* |
| Network Graph | ✅* | `GraphService` — same dependency caveat |
| Timeline Reconstruction | ✅ | `TimelineService.analyze` (OCR timestamps, not entity-dependent) |
| Campaign Detection | ✅* | `CampaignService` — entity/correlation dependent |
| Suspect Assessment | ✅* | `SuspectService` — entity/correlation dependent |
| Analytics | ✅ | `AnalyticsService.generate` |
| Report Generation | ✅ | `InvestigationReportService.generate` → MD/JSON |
| Dashboard | ❌ | No dashboard endpoint routed; engine mode has no cross-case view (by design) |

**Where the pipeline breaks:** between **OCR and Correlation**. The API upload path
(`_evidence_pipeline`) stops after OCR + storage. The cleaning→enhancement→semantic→entity
chain runs **only** through `cli.py`. Consequently, for evidence uploaded through the
web app, `storage/entities.csv` is not updated, and the entity-driven Phase-2 modules
(correlation, graph, campaigns, suspects) operate on empty/stale entity input. The existing
populated `entities.csv` (dated Jul 8) was produced by a manual CLI/batch run, not by the API.
**Fix:** call `EvidenceProcessingOrchestrator` inside `submit_evidence_job`.

---

## 7. Frontend Audit

**Pages completed:** Start, New case, Open case, Case detail (8 tabs), Evidence detail, Settings — all wired to real endpoints via `src/api/index.ts` + React Query. Graph uses cytoscape (`GraphCanvas.tsx`); reports render via `reportHtml.ts`.

**Pages missing:** No Dashboard, no cross-case list, no login page — **intentional** in engine mode (`router.tsx` comment; `AuthContext.tsx` no-op).

**Broken buttons / nav:** `CaseDetailPage.tsx:126` — `navigate("/cases")` targets a route that does not exist; the `*` wildcard redirects it to `/`. Label "Back to cases" is misleading. Minor.

**Missing API integration / dead client code (verified by grep — zero component usage):**
- `dashboardApi`, `auditApi`, `notificationsApi`, `casesApi.list`, `authApi` in `src/api/index.ts` are defined but **never called** by any component, and several point at unrouted backend URLs.
- `casesApi.create` (`POST /cases/`) is only used by `CreateCaseDialog.tsx`, which is itself **not imported anywhere** — and `POST /cases/` isn't routed. Cases are actually created via `intakeApi.open` in `NewCasePage.tsx`.

**Placeholder / orphaned components:** `features/cases/CreateCaseDialog.tsx` and `features/notifications/notificationIcon.tsx` are dead (no importers).

**UI consistency:** Component kit is consistent (MUI + shared `common/*`). Main inconsistencies are the dead code above and the stale "Back to cases" target.

**Tests:** **0** frontend tests.

---

## 8. Backend Audit

**Completed services:** intake, cases, evidence (upload/list/detail/download + jobs), investigation artifacts + run-analysis, reports, system settings; engine bridge; background workers; notification broadcasting; full accounts/JWT/RBAC app.

**Missing / unrouted services:** `dashboard.py`, `audit.py`, `notifications.py` views exist but are absent from `api/urls.py`. No `GET /cases/` list or `POST /cases/` create route (intake-only by design).

**Error handling:** Good. `api/exceptions.py::EngineUnavailable`; artifact loader raises 503 with actionable text (`engine.py::load_artifact`); background workers catch-and-report, never crash the pool, and emit `SYSTEM_ERROR` notifications (`submit_evidence_job`/`submit_analysis_job`). Phase-2 pipeline isolates each module via `safe()`.

**Validation:** DRF serializers on cases/evidence; upload handled via `FormData`. Adequate but light on file-type/size guards at the view layer.

**Logging:** Structured — `logging.getLogger("ciis.engine")`, engine `get_logger`, `StageTimer` per stage, CSV audit logs (`processing_log.csv`, `investigation_audit_log.csv`) + DB `ActivityLog`.

**Architecture quality:** Strong separation — the API never contains forensic logic (all in `engine.py` bridge); engine uses dependency injection (`build_default_pipeline`); CSV/JSON is the single source of truth, DB holds only workflow state (`api/models.py` docstring). Concurrency handled with a global `_pipeline_lock` because CSV storage isn't concurrency-safe (documented, but a scaling ceiling).

**Weaknesses:** **0** API tests; `DEBUG=1` and SQLite defaults; in-process executor won't survive restart / scale horizontally.

---

## 9. Research Evaluation Audit

| Metric | Implemented? | Where / verdict |
|---|:--:|---|
| OCR Accuracy | ❌ | No accuracy computation in `evidence_ocr_engine` (grep for accuracy/benchmark = none). **Documented but not implemented.** |
| Character Error Rate (CER) | ❌ | No CER/levenshtein/edit-distance metric anywhere in engine. **Missing.** |
| Word Error Rate (WER) | ❌ | Same. **Missing.** |
| Precision | ⚠️ | Implemented **only** in `threat_intelligence_system/src/evaluation/cross_validation.py` (`precision_score`) for the URL classifier — not for OCR/entities. |
| Recall | ⚠️ | Same file (`recall_score`). Classifier only. |
| F1 Score | ⚠️ | Same file (`f1_score`) + `results/baseline_comparison_report.json`. Classifier only. |
| Correlation Accuracy | ❌ | `CorrelationService` computes scores but there is no ground-truth accuracy evaluation. **Missing.** |
| Timeline Accuracy | ❌ | No accuracy harness for `TimelineService`. **Missing.** |
| Processing Time | ⚠️ | Measured per stage via `StageTimer` and stored in audit logs + `duration_ms`, but **not aggregated into a research report.** Partially. |
| Test Coverage | ⚠️ | 40 engine + 23 threat-intel + 1 correlation-prototype test files; **0 API, 0 frontend.** No coverage % is computed/reported. |
| Usability Evaluation | ❌ | No usability study/instrument in the repo. **Missing.** |

**Bottom line:** the only rigorous, reproducible research metrics in the repository belong to
the **unintegrated** URL threat classifier. The headline OCR-forensics research metrics
(CER/WER/entity P-R-F1/correlation/timeline accuracy/usability) are **not implemented**.

---

## 10. Code Quality Audit

**Unused / dead files:**
- Frontend: `features/cases/CreateCaseDialog.tsx`, `features/notifications/notificationIcon.tsx` (no importers); dead client groups in `src/api/index.ts` (`dashboardApi`, `auditApi`, `notificationsApi`, `authApi`, `casesApi.list/create`).
- Backend: `api/views/dashboard.py`, `audit.py`, `notifications.py` (not routed).

**Dead code:** the auth/RBAC surface (`accounts/`) is fully built but dormant behind a no-op `AuthContext`.

**Duplicate implementations (the big one):** three root modules duplicate the integrated engine —
`evidence_correlation_engine/` ↔ `investigation/correlation` + `graph`; `timeline_reconstruction/` ↔ `investigation/timeline`; `report generation/report_generator.py` ↔ `investigation/reporting/service.py` (the latter explicitly calls the former "legacy … untouched", `service.py:10`).

**Deprecated modules:** `report generation/`, `evidence_correlation_engine/`, `timeline_reconstruction/` — superseded, safe to archive.

**Technical debt:** CSV-as-database + global `_pipeline_lock` (won't scale); `DEBUG=1`/SQLite defaults; the OCR-only API pipeline gap; `ocr_interface.py::FutureOCRService` is an intentional `NotImplementedError` research placeholder (documented, harmless).

**Refactoring opportunities:** (1) route `submit_evidence_job` through the orchestrator; (2) delete/relocate the 3 root prototype modules; (3) prune dead frontend/back-end code; (4) decide-and-restore or delete the auth/notifications/dashboard surface; (5) extract a metrics/evaluation package.

---

## 11. Mid-Term Readiness

**Verdict: Ready for mid-term defense — comfortably — if you demo via the CLI-backed populated cases (or wire §4.1 first).**

**Strengths:** genuinely deep, well-architected engine (Phase-1 + Phase-2, DI, failure isolation); 60+ engine/classifier tests; clean API/UI separation; real artifacts and reports; a substantial ML research sub-project with proper benchmarks.

**Weaknesses:** OCR→entity chain not wired into the web upload; no OCR research metrics (CER/WER); zero API/UI tests; dead/duplicate code; empty `storage/investigation/` on a fresh run.

**Critical missing items for a *flawless live* demo:** (1) the §4.1 orchestrator wiring so a freshly uploaded file flows all the way to entities/correlation; (2) pre-run "Run Analysis" on a demo case so Phase-2 tabs are populated.

**Suggested demo flow:** Open case by reference → upload a screenshot (OCR result + confidence in Evidence tab) → open a **pre-analyzed** case → walk Investigation (correlation/campaigns/suspects) → Graph (cytoscape) → Timeline → Analytics → download the generated MD/JSON report → briefly show the threat-classifier benchmark artifacts as the research contribution.

---

## 12. Final Defense Readiness

**Critical:** wire cleaning→enhancement→semantic→entity into the API pipeline (§4.1); implement OCR CER/WER + entity P/R/F1 evaluation (§5); add `ciis_api` integration tests.

**High:** correlation/timeline accuracy evaluation with ground truth; integrate (or formally scope out) the ML threat system; compute + report test coverage %.

**Medium:** frontend tests; production settings (env-driven `DEBUG`, Postgres, static/media); route-or-remove dashboard/audit/notifications; fix "Back to cases".

**Low:** delete/archive the 3 duplicate root modules; prune dead frontend client code; usability evaluation; decide the fate of the dormant auth/RBAC layer.

---

## 13. Final Roadmap (prioritized)

| # | Task | Current | Remaining work | Files to modify | Priority | Effort | Dependencies | Expected outcome |
|---|---|---|---|---|:--:|:--:|---|---|
| 1 | Wire full Phase-1 chain into API | OCR-only | Call `EvidenceProcessingOrchestrator` post-OCR | `api/engine.py` | Critical | 0.5–1d | orchestrator (exists) | Web uploads produce entities → real Phase-2 |
| 2 | OCR CER/WER metrics | none | Ground-truth set + metric script + report | new `evidence/evaluation/`, `scripts/` | Critical | 2–3d | labelled data | Defensible OCR accuracy numbers |
| 3 | Entity P/R/F1 | none | Labelled entities + eval harness | new eval script | Critical | 1–2d | labelled data | Entity-extraction validation |
| 4 | API integration tests | 0 | Cover intake→upload→analyze→report | `ciis_api/api/tests/` | High | 1–2d | Django test client | Regression safety |
| 5 | Correlation/timeline accuracy | none | Ground-truth cases + scoring | new `investigation/evaluation/` | High | 2–3d | annotated cases | Phase-2 quality evidence |
| 6 | Integrate ML threat intel | static file | Adapter behind `ThreatIntelProvider` | `investigation/data_access.py` | Medium | 2–4d | threat_intel_system | Real threat scoring |
| 7 | Prod hardening | dev defaults | env `DEBUG`, Postgres, media/static | `config/settings.py` | Medium | 1–2d | deploy target | Deployable build |
| 8 | Route/remove dashboard/audit/notif | unrouted | Re-route + re-wire UI, or delete | `api/urls.py`, `src/api/index.ts` | Medium | 0.5d | product decision | No dead endpoints |
| 9 | Frontend tests | 0 | vitest + RTL for key tabs | `ciis_frontend/src/**` | Medium | 1–2d | tooling | UI regression safety |
| 10 | Remove duplicate root modules | present | Archive `evidence_correlation_engine`, `timeline_reconstruction`, `report generation` | repo root | Low | 0.5d | none | Smaller, clearer repo |

---

## 14. Final Summary

| Module | Should Exist | Implemented | Remaining Work | Completion % |
|---|:--:|:--:|---|:--:|
| Case Management | ✔ | ✔ | — | 95% |
| Evidence Upload | ✔ | ✔ | file-type/size validation | 90% |
| SHA-256 Hashing | ✔ | ✔ | — | 100% |
| OCR | ✔ | ✔ | accuracy metrics | 90% |
| Image Preprocessing | ✔ | ✔ | — | 90% |
| OCR Enhancement | ✔ | ✔ (lib) | wire into API pipeline | 75% |
| Semantic Correction | ✔ | ✔ (lib) | wire into API pipeline | 75% |
| Entity Extraction | ✔ | ✔ (lib) | wire into API pipeline | 70% |
| Threat Intelligence | ✔ | ⚠ static-file | integrate ML system | 45% |
| Brand/Logo Intelligence | ✔ | ✔ (forensics) | — | 85% |
| Evidence Correlation | ✔ | ✔ | entity-input fix + accuracy eval | 85% |
| Network Graph | ✔ | ✔ | accuracy eval | 88% |
| Timeline Reconstruction | ✔ | ✔ | accuracy eval | 85% |
| Campaign Detection | ✔ | ✔ | eval | 85% |
| Suspect Assessment | ✔ | ✔ | eval | 85% |
| Investigation Analytics | ✔ | ✔ | — | 90% |
| Report Generation | ✔ | ✔ | retire legacy dup | 90% |
| Dashboard | ✔ | ❌ (by design) | route + UI (if in scope) | 20% |
| Auth / RBAC | ✔ | ⚠ built-but-dormant | restore or remove | 60% |
| Notifications/Audit (served) | ✔ | ⚠ write-only | route + wire UI | 50% |
| Backend API | ✔ | ✔ | tests | 80% |
| Frontend | ✔ | ✔ | tests, dead-code, nav fix | 75% |
| Testing | ✔ | ⚠ engine-only | API + UI tests, coverage % | 55% |
| Research Metrics | ✔ | ⚠ classifier-only | CER/WER/P-R-F1/accuracy | 40% |
| Documentation | ✔ | ✔ | reconcile docs vs code | 85% |

### 1. What has been successfully achieved
A genuinely strong, well-architected **forensic engine**: full Phase-1 (OCR, preprocessing, hashing, cleaning, enhancement, semantic correction, forensics incl. logo/brand) and full Phase-2 (correlation, graph, campaigns, suspects, timeline, analytics, prioritization, reporting) — dependency-injected, failure-isolated, and backed by 40+ tests. A clean Django API bridge and an engine-mode React SPA that renders every artifact and produces downloadable MD/JSON reports. A substantial, properly benchmarked ML threat classifier as a research sub-project.

### 2. What is still remaining
The web upload path stops at OCR — the cleaning/entity chain isn't wired into the API, so entity-driven Phase-2 modules are starved for API-uploaded cases. The headline OCR research metrics (CER/WER, entity P/R/F1, correlation/timeline accuracy, usability) are not implemented. The API and frontend have no tests. There is meaningful dead/duplicate code (3 superseded root modules, unrouted dashboard/audit/notifications, dormant auth). Production settings are dev-grade.

### 3. What should be implemented next
Wire `EvidenceProcessingOrchestrator` into `submit_evidence_job` (Roadmap #1) — this single change makes the end-to-end web pipeline real. Then build the OCR/entity evaluation harness (#2–#3) so the project has defensible research numbers.

### 4. Recommended order of implementation
#1 (pipeline wiring) → #2, #3 (OCR/entity metrics) → #4 (API tests) → #5 (Phase-2 accuracy) → #6 (threat-intel integration) → #7 (prod hardening) → #8–#10 (cleanup: route/remove dead code, frontend tests, delete duplicates).
