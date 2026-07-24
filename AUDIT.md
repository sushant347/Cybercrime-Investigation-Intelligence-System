# Change Audit

A record of deliberate architectural changes: what changed, why, and how to
undo it. Newest entry first.

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
