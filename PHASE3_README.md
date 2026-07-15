# CIIS Phase 3 — Investigation Platform

Professional web platform for the Cybercrime Investigation Intelligence System.
Phase 3 adds **zero forensic logic**: it wraps the completed Phase 1/2 engines in a
thin Django REST API (`ciis_api/`) and a React 19 investigation dashboard
(`ciis_frontend/`). Phase 1/2 code is never modified — the API imports the engine
packages read-only and serves their stored artifacts verbatim.

```
┌────────────────────┐   HTTP/JSON    ┌───────────────────┐   imports (read-only)   ┌──────────────────────────┐
│  ciis_frontend     │ ─────────────► │  ciis_api (DRF)   │ ──────────────────────► │  evidence_ocr_engine     │
│  React 19 + MUI    │                │  auth · RBAC ·    │                         │  Phase 1 + Phase 2       │
│  Vite + TS strict  │ ◄───────────── │  jobs · notifs    │ ◄────────────────────── │  storage/ CSV + JSON     │
└────────────────────┘                └───────────────────┘      artifacts          └──────────────────────────┘
```

## Quick start

### 1. API (Django REST Framework)

```bash
cd ciis_api
pip install -r requirements.txt
# also needs the engine's own deps (pydantic etc.):  pip install -r ../evidence_ocr_engine/requirements.txt
python manage.py migrate
python manage.py seed_demo          # admin / investigator / analyst / viewer  (password: Ciis@Demo2026)
python manage.py runserver 8000
```

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `CIIS_ENGINE_ROOT` | `../evidence_ocr_engine` | Path to the Phase 1/2 engine |
| `CIIS_DB_PATH` | `ciis_api/ciis_platform.sqlite3` | Platform DB (users, workflow, notifications) |
| `CIIS_SECRET_KEY`, `CIIS_DEBUG`, `CIIS_ALLOWED_HOSTS`, `CIIS_CORS_ORIGINS` | dev defaults | Deployment settings |

### 2. Frontend (React 19 + Vite)

```bash
cd ciis_frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api → localhost:8000)
npm run build        # tsc --noEmit && vite build  → dist/
```

## API surface (all under `/api/`)

| Area | Endpoints |
|---|---|
| Auth | `auth/login/` `auth/refresh/` `auth/logout/` `auth/me/` `auth/me/preferences/` `auth/users/` `auth/permissions/` |
| Dashboard | `dashboard/` |
| Cases | `cases/` `cases/<id>/` `cases/<id>/archive/` `cases/<id>/history/` |
| Evidence | `cases/<id>/evidence/` `…/upload/` `…/<eid>/` `…/<eid>/download/` `jobs/` `jobs/<n>/` |
| Investigation | `cases/<id>/artifacts/` `cases/<id>/artifacts/<key>/` `cases/<id>/analyze/` |
| Reports | `cases/<id>/reports/` `…/latest/` `…/<file>/download/` |
| Audit / Notifs / Settings | `audit/` `notifications/` `notifications/mark-read/` `settings/` |

Artifact keys map 1:1 to the Phase-2 storage spec: `correlation`, `graph`,
`graph_statistics`, `graph_summary`, `campaigns`, `suspects`, `timeline`,
`analytics`, `case_statistics`, `entity_statistics`, `report`, `priority`.

**Engine integration rules** (enforced in `ciis_api/api/engine.py`, the single
bridge module): engine CSV/JSON storage is the source of truth; artifacts are
served wrapped in their original envelope (`report_type`, `report_version`,
`generated_at`, `report`); uploads call `EvidencePipeline.process_file` and
analysis calls `build_default_pipeline().analyze_case` in a background worker
with job tracking; a lock serializes engine writes (CSV storage is not
concurrent-safe).

## RBAC

Roles: administrator, investigator, analyst, viewer. Permissions
(`case.view`, `case.manage`, `evidence.upload`, `investigation.run`,
`report.view`, `audit.view`, `settings.view`, `user.manage`, …) are stored per
role in the `RolePermission` table and editable from **User Management → Role
Permissions**. Defaults live in `accounts/models.py`; DRF views check them via
`accounts.permissions.require("<code>")`, the SPA via `useAuth().hasPermission`.
Route guards hide/deny pages; the API is the actual enforcement point.

## Frontend architecture

```
src/
  api/            typed endpoint layer (only place axios is called)
  app/            router + react-query client
  components/     layout (AppLayout/Sidebar/Topbar) + common (StatusChip,
                  ConfidenceBar, JsonViewer, KeyValueTable, SearchField,
                  StatCard, EmptyState, ErrorBoundary, skeletons)
  features/       auth, dashboard, cases, evidence, investigation, graph,
                  timeline, analytics, reports, audit, settings,
                  notifications, users   (one folder per module)
  lib/            apiClient (JWT + refresh interceptor), format helpers
  theme/          design tokens, dark/light themes, severity & node colors
  types/          domain types mirroring the engine's pydantic models
```

State management: React Query for all server state (30 s stale time, no
retries on 401/403/404/503); React context for auth session and color mode;
no client-side business logic — every score, explanation, band, and
relationship is rendered exactly as the engine stored it.

Routes: `/login`, `/` (dashboard), `/cases`, `/cases/:caseId/:tab`
(overview · evidence · investigation · graph · timeline · analytics ·
reports · history), `/cases/:caseId/evidence/:evidenceId`, `/audit`,
`/settings`, `/notifications`, `/admin/users`.

## Testing strategy

- **API**: DRF `APIClient` integration tests per view (auth flow, RBAC deny
  matrix, artifact 503 when missing, upload job lifecycle). The smoke suite
  used during development logs in and walks every endpoint against the real
  engine storage.
- **Frontend**: Vitest + React Testing Library for common components
  (StatusChip mapping, ConfidenceBar clamping, SearchField debounce) and
  feature pages with mocked API layer (`src/api` is the seam — mock the module,
  never axios). MSW recommended for full-page tests.
- **E2E**: Playwright happy path — login → create case → upload evidence →
  poll job → run analysis → verify graph/timeline/report tabs.

## Notes

- Evidence upload and Phase-2 analysis run in a thread pool; the UI polls
  `jobs/<id>/` and notifications broadcast on completion, high-priority
  verdicts, and failures.
- Engine settings pages are intentionally **read-only**: the engine owns its
  configuration via `EVIDENCE_*` / `INVESTIGATION_*` environment variables.
- First OCR upload downloads PaddleOCR models — expect a slow first run.
