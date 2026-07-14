"""CIIS Phase 2 - Intelligent Cybercrime Investigation Platform.

Pure add-on package (no existing module is modified):

* Module 1 - Advanced Evidence Correlation Engine  -> :mod:`.correlation`
* Module 2 - Evidence Relationship Graph Engine    -> :mod:`.graph`
* Module 3 - Scam Campaign Clustering Engine       -> :mod:`.campaigns`
* Module 4 - Suspect Confidence Engine             -> :mod:`.suspects`
* Module 5 - Timeline Intelligence Engine          -> :mod:`.timeline`
* Module 6 - Investigation Analytics Engine        -> :mod:`.analytics`
* Module 7 - Advanced Report Generation            -> :mod:`.reporting`
* Module 8 - Case Prioritization Engine            -> :mod:`.prioritization`

Shared infrastructure:

* :mod:`.config`       - configuration-driven behaviour (INVESTIGATION_* env)
* :mod:`.data_access`  - READ-ONLY gateway over all existing storage
* :mod:`.repository`   - versioned case-level JSON outputs (never overwrites)
* :mod:`.audit`        - storage/investigation/investigation_audit_log.csv
* :mod:`.pipeline`     - case orchestrator + composition root

Design guarantees: existing JSON/CSV formats untouched, all outputs stored
independently under ``storage/investigation/<CASE_ID>/``, every analytical
decision carries a human-readable explanation, no machine learning - only
explainable weighted scoring.
"""

from .config import InvestigationConfig

__all__ = ["InvestigationConfig"]
