# Security posture

This document states what CIIS protects, what it does not, and why. It exists
because the most important fact about this system is easy to miss from the
code: **the API has no authentication.**

## The posture, plainly

CIIS is built as a **single-operator forensic workstation**, not a networked
service. An investigator opens it on their own machine, works a case, and the
service is bound to localhost.

Concretely:

| | |
|---|---|
| User accounts | **None.** There is no login, no session, no user identity. |
| API authentication | **None.** `require()` in `api/permissions.py` is a documented no-op returning `AllowAny`. |
| Case access control | **None.** Any case, evidence item, artifact or report is readable by anyone who can reach the port. |
| Admin surface | Shared password (`CIIS_ADMIN_PASSWORD`) — the only gate in the system. |
| Transport | Plain HTTP. No TLS. |
| Default binding | `127.0.0.1` via `manage.py runserver`. |
| Default `ALLOWED_HOSTS` | `localhost, 127.0.0.1, testserver` |

`api/tests/test_security_posture.py` asserts this openness deliberately, so it
cannot change by accident without a test failing.

## Why it is built this way

The design decision was recorded on 2026-07-23: investigators reach a case by
knowing its reference, and accounts were removed to keep the tool usable
without a directory service or a database. For its intended deployment — one
analyst, one machine, evidence that already lives on that machine's disk —
adding authentication would protect nothing that the operating system's own
login does not already protect.

**That reasoning stops holding the moment the service is reachable by anyone
else.** At that point every case in the storage tree is world-readable to the
network, including the original uploaded evidence.

## What enforces the boundary

Nothing in the code can stop an operator exposing the service — but it will
tell them, loudly, and refuse to start in the worst configurations.
`api/checks.py` registers Django system checks that run on every
`manage.py check` and every `runserver`:

| Id | Condition | Level |
|---|---|---|
| `ciis.W001` | Admin password is still the shipped default, on localhost with DEBUG | Warning |
| `ciis.E001` | Admin password is still the default, and the host is reachable **or** DEBUG is off | **Error — refuses to start** |
| `ciis.W002` | `ALLOWED_HOSTS` admits a non-local host while there is no authentication | Warning |
| `ciis.E002` | `DEBUG` is on and `ALLOWED_HOSTS` admits a non-local host | **Error — refuses to start** |

The escalation is deliberate. A default password on a laptop is untidy; the
same password on a reachable host, guarding an endpoint that deletes cases, is
a different thing entirely.

To run in a configuration the checks reject, either fix the configuration or
silence the check explicitly with `SILENCED_SYSTEM_CHECKS` — which leaves a
record of the decision in settings rather than an unexamined risk.

## Deploying beyond one workstation

If this has to be reachable by more than one person, the platform does not
grow authentication on its own. Put it behind something that has it:

1. **Terminate TLS and authenticate at a reverse proxy** (nginx with client
   certificates, or an SSO-aware proxy). CIIS never sees an unauthenticated
   request.
2. **Or keep it on a private network / VPN** and treat network membership as
   the access control.
3. **Set `CIIS_ADMIN_PASSWORD`**, `CIIS_DEBUG=0`, and an explicit
   `CIIS_ALLOWED_HOSTS`.
4. **Restrict the storage tree** at the filesystem level. The evidence, the
   originals and the reports are ordinary files; the API is not the only way to
   read them.

Building real accounts into CIIS would be a larger change than it looks: there
is no database, platform state is CSV/JSON, and the audit trail records module
actions rather than user actions. Doing it properly means adding an identity
store and threading a user through every audit record — worth doing if the tool
becomes multi-user, and not worth faking before then.

## What is protected

Some things hold regardless of the access posture:

- **Evidence integrity.** SHA-256 is taken before and after processing and
  recorded in the chain-of-custody register; `hash_verified` is reported per
  item and surfaced in every report.
- **Originals are never modified.** The pipeline writes derived text and
  artifacts; the uploaded file is left as acquired.
- **Forensic invariants.** `raw_text`, `cleaned_text` and `enhanced_text` are
  never rewritten, including by the semantic corrector.
- **Provenance.** Every report embeds SHA-256 digests of the exact artifacts it
  was generated from, so a report can be tied to the evidence state that
  produced it.
- **Auditability.** Every module run appends to
  `storage/investigation/investigation_audit_log.csv`.
- **Path traversal.** Report downloads resolve and confirm the file stays
  inside the case directory before serving.

## Known limitations

- No authentication, no authorisation, no per-case access control.
- No TLS; credentials for the admin surface cross the wire in plain text.
- The admin password is shared, not per-person, so admin actions are not
  attributable to an individual.
- The audit trail records *what* ran, not *who* asked for it — a direct
  consequence of having no user identity.
- No rate limiting; the analysis endpoint is computationally expensive.

## Reporting a problem

This is student research software, not a maintained product. If you find a
vulnerability, raise it on the repository issue tracker.
