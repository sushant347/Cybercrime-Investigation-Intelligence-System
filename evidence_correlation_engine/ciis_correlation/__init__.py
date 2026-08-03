"""CIIS Module 2 - Evidence Correlation Engine.

The analytical core of the platform. Everything that reasons *about* evidence -
rather than extracting it - lives here:

* :mod:`.correlation`    - weighted, explainable evidence-pair correlation
* :mod:`.crosscase`      - cross-case entity lookup over ``entities.csv``
* :mod:`.graph`          - evidence relationship graph
* :mod:`.campaigns`      - scam campaign clustering over strong correlations
* :mod:`.suspects`       - suspect confidence assessment
* :mod:`.analytics`      - case analytics and statistics
* :mod:`.prioritization` - case priority scoring
* :mod:`.reporting`      - investigation report generation (MD / JSON / PDF)
* :mod:`.evaluation`     - accuracy measurement against gold labels
* :mod:`.pipeline`       - case orchestrator and composition root

Shared infrastructure lives in :mod:`.core` (configuration, the read-only
storage gateway, the versioned artifact repository, the audit trail and
storage maintenance).

Module boundaries
-----------------
This engine sits downstream of the OCR engine and upstream of the timeline
engine::

    evidence_ocr_engine  ->  evidence_correlation_engine  ->  timeline_reconstruction
                                        ^
                            threat_intelligence_system

It reads the OCR engine's storage tree strictly read-only through
:class:`~ciis_correlation.core.data_access.CaseDataRepository`, and imports
exactly two symbols from it: ``EvidenceConfig`` and ``get_logger``. The OCR
engine never imports this package, so the dependency graph stays acyclic.

Because that upstream dependency is resolved by path rather than by
installation, importing this package puts the OCR engine root on ``sys.path``
(below). ``CIIS_ENGINE_ROOT`` overrides the default sibling location, matching
the environment variable the Django layer already honours.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Root of this engine (the directory containing this package).
CORRELATION_ENGINE_ROOT = Path(__file__).resolve().parent.parent

#: Root of the upstream OCR engine, whose ``backend.modules.evidence`` package
#: supplies ``EvidenceConfig`` and ``get_logger`` and whose ``storage/`` tree is
#: this engine's read-only input.
OCR_ENGINE_ROOT = Path(
    os.environ.get(
        "CIIS_ENGINE_ROOT",
        CORRELATION_ENGINE_ROOT.parent / "evidence_ocr_engine",
    )
).resolve()


def _bootstrap_ocr_engine() -> None:
    """Put the OCR engine on ``sys.path`` before any submodule imports it.

    Must run at package-import time rather than lazily: ``core.config`` and
    ``core.data_access`` import from ``backend.modules.evidence`` at module
    scope, and they are imported by every service in this package.
    """
    root = str(OCR_ENGINE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


_bootstrap_ocr_engine()

from .core.config import InvestigationConfig  # noqa: E402  (needs bootstrap)

__all__ = ["InvestigationConfig", "CORRELATION_ENGINE_ROOT", "OCR_ENGINE_ROOT"]
