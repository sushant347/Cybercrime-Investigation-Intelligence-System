# How to push the roadmap work to GitHub

## ⚠️ Read this first — your `main` was reverted

Your GitHub `main` no longer matches your local code. On GitHub, **PR #2
reverted PR #1** ("Engine mode: no-login guided flow…"), so the remote `main`
is back on the **older pre-engine-mode architecture**. Your **local** repo — and
all of this F1–F11 roadmap work — is built **on** engine-mode.

That's why `git push … :main` was rejected and a rebase onto `main` conflicts
(e.g. `urls.py`: reverted main uses `cases/` list/create; the roadmap work uses
the engine-mode `intake` design). They are two different designs of the same app.

**So do NOT push straight to `main`.** Push to a new branch and open a PR, where
you can decide how to reconcile. All work is in `ciis_roadmap_work.bundle`
(9 commits, base `44607e7`, which is already on the remote — so a branch push is
clean and non-destructive).

The 9 commits (oldest → newest):

```
909478d  fix(engine): idempotent entity/keyword CSV storage (F1 pre-req)
5043948  feat(api): full Phase-1 chain on upload, ML threat-intel, prod hardening
72c0737  feat(api): route dashboard, audit & notifications endpoints (F8)
027e4f7  test(api): integration suite intake -> upload -> analyze -> report (F4)
12052c5  feat(research): OCR, entity & Phase-2 accuracy harnesses (F2/F3/F5)
21cdb72  feat(frontend): notification bell + fix back nav (F8, F11)
38bcee7  test(frontend): vitest + Testing Library setup and specs (F9)
9b49e63  docs+chore: status, deprecate legacy modules, ignore junk (F10, F11)
fd7b4f5  chore(prototype): pending evidence_correlation_engine outputs
```

---

## ✅ Recommended: push to a new branch, then open a PR

Run in `...\Desktop\project`:

```
del ".git\index.lock" ".git\HEAD.lock"          rem clear stale locks (ignore "not found")

git fetch ".\ciis_roadmap_work.bundle" main:feature/roadmap-implementation
git push origin feature/roadmap-implementation
```

Then on GitHub, open a Pull Request from `feature/roadmap-implementation`. There
you (and reviewers) decide whether this supersedes the revert on `main`.

---

## Alternative: make this the new `main` (undoes the revert)

Only if you deliberately want `main` to be engine-mode + roadmap again,
**overwriting** the PR #2 revert:

```
del ".git\index.lock" ".git\HEAD.lock"

git fetch ".\ciis_roadmap_work.bundle" main:roadmap-main
git push origin roadmap-main:main --force-with-lease
```

`--force-with-lease` refuses if someone else pushed in the meantime. This
rewrites remote `main` — coordinate with anyone else on the repo first.

---

## Sync your local checkout afterward (optional)

Your working-tree edits are already inside these commits, so:

```
git checkout feature/roadmap-implementation      rem or: git reset --hard fd7b4f5
git status                                        rem should be clean
```

When finished, delete `ciis_roadmap_work.bundle` and this file.
