# ⚠️ DEPRECATED — superseded prototype

This standalone module is an **early prototype** and is **no longer part of the
running product**. It has been fully superseded by the integrated investigation
engine:

| This prototype | Integrated replacement (authoritative) |
|---|---|
| `correlation_engine.py` | `evidence_ocr_engine/backend/modules/investigation/correlation/service.py` |
| `graph_builder.py` | `evidence_ocr_engine/backend/modules/investigation/graph/service.py` |

The live API (`ciis_api`) and the engine import **only** from
`evidence_ocr_engine`; nothing imports this directory (verified: zero import
references). It is retained here for historical/reference purposes only.

**Do not build on this module.** New correlation/graph work belongs in the
integrated engine, which is dependency-injected, failure-isolated, and unit
tested. Accuracy for the integrated versions is measured by
`evidence_ocr_engine/backend/modules/investigation/evaluation/` (see F5).

_Scheduled for archival to `archive/` once repository housekeeping permits._
