"""Shared infrastructure for every correlation-engine service.

* :mod:`.config`       - configuration-driven behaviour (``INVESTIGATION_*`` env)
* :mod:`.data_access`  - READ-ONLY gateway over the OCR engine's storage tree
* :mod:`.repository`   - versioned case-level artifacts (never overwrites)
* :mod:`.audit`        - ``storage/investigation/investigation_audit_log.csv``
* :mod:`.maintenance`  - storage reset, case and evidence deletion

Services receive these by dependency injection from
:func:`ciis_timeline_report.pipeline.build_default_pipeline`; nothing here reaches
back into an analytical module.
"""

from .audit import InvestigationAuditTrail
from .config import InvestigationConfig
from .data_access import CaseDataRepository, EvidenceContext, ThreatIntelProvider
from .repository import InvestigationReportRepository

__all__ = [
    "InvestigationAuditTrail",
    "InvestigationConfig",
    "CaseDataRepository",
    "EvidenceContext",
    "ThreatIntelProvider",
    "InvestigationReportRepository",
]
