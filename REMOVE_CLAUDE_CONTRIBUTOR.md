# Remove "Claude" from the repo's contributors

## What was going on

Claude was **not** a separate commit or a commit author. It appeared as a
**co-author** via a trailer in 3 commit messages on `main`:

```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

on these commits (all authored by DahalSachyam):

- `feat: guided one-screen flow, case privacy, and a readable report`
- `feat: engine mode - no login, CSV case registry with hashed case ids`
- `feat: local dev environment + visual investigation report`

GitHub counts co-authors as contributors, so `noreply@anthropic.com` showed up
in the contributor list. The fix is to rewrite those commit messages to drop the
trailer. **No code changes** — I verified the rewritten history is byte-for-byte
identical to the current remote; only the messages differ.

The cleaned history is in **`main_no_claude.bundle`** (a complete copy of the
remote `main` with every Claude/Anthropic trailer stripped). New `main` tip:
`9bc76d7`.

> ⚠️ This is a **history rewrite + force-push**. Anyone else who has cloned the
> repo (DahalSachyam, Suraj KC, sujal119) must re-clone or hard-reset afterward.
> Do it when no one else is mid-push.

## Steps — run in `...\Desktop\project`

```
del ".git\index.lock" ".git\HEAD.lock"                rem clear stale locks (ignore "not found")

git fetch ".\main_no_claude.bundle" main-noclaude:cleaned-main
git push origin cleaned-main:main --force-with-lease
```

- `--force-with-lease` aborts safely if someone pushed to `main` in the meantime.

### Point your local `main` at the cleaned history (optional but recommended)

```
git checkout main
git reset --hard cleaned-main
git branch -D cleaned-main
```

## After pushing

- GitHub's **Contributors** page and the commit co-author chips update after it
  re-indexes (can take a little while / a cache refresh).
- If any **other branches** still contain the old commits (e.g. old feature or
  `revert-*` branches from the merged PRs), delete them on GitHub too — otherwise
  the co-author can linger via those refs.
- Delete `main_no_claude.bundle` and this file when done.

## Verify (locally, after reset)

```
git log --pretty="%an <%ae>%n%b" | findstr /I "anthropic claude"
```
No output = fully removed.
