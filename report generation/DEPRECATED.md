# ⚠️ DEPRECATED — legacy, explicitly retired

This standalone module is **legacy** and **not part of the running product**. It
has been superseded by the integrated reporting service, which explicitly calls
this one "legacy … untouched":

| This module | Integrated replacement (authoritative) |
|---|---|
| `report_generator.py` | `evidence_ocr_engine/backend/modules/investigation/reporting/service.py` |

The live API (`ciis_api`) and the engine import **only** from
`evidence_ocr_engine`; nothing imports this directory. It is retained for
historical/reference purposes only.

**Do not build on this module.** Investigator-facing MD/JSON reports are produced
by the integrated `InvestigationReportService`.

_Scheduled for archival to `archive/` once repository housekeeping permits._
