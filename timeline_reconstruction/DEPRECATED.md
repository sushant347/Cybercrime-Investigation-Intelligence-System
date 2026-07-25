# ⚠️ DEPRECATED — superseded prototype

This standalone module is an **early prototype** and is **no longer part of the
running product**. It has been fully superseded by the integrated investigation
engine:

| This prototype | Integrated replacement (authoritative) |
|---|---|
| `timeline_reconstruction.py` | `evidence_ocr_engine/backend/modules/investigation/timeline/service.py` |

The live API (`ciis_api`) and the engine import **only** from
`evidence_ocr_engine`; nothing imports this directory. It is retained for
historical/reference purposes only.

**Do not build on this module.** Timeline accuracy for the integrated version is
measured by `investigation/evaluation/timeline_eval.py` (see F5).

_Scheduled for archival to `archive/` once repository housekeeping permits._
