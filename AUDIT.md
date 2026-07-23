# Change Audit

A record of deliberate architectural changes: what changed, why, and how to
undo it. Newest entry first.

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
