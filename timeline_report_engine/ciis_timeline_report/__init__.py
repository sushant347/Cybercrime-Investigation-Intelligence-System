"""CIIE Module 4 - Timeline & Report Engine.

The terminal stage of the investigation pipeline: it turns the relationships
found by the correlation engine into the artifacts an investigator reads.

* :mod:`.timeline`       - timestamp reconstruction, ordering, attack stages
* :mod:`.graph`          - evidence relationship graph (consumes timeline events)
* :mod:`.analytics`      - case, entity, threat and quality statistics
* :mod:`.prioritization` - weighted case priority
* :mod:`.reporting`      - investigation report (Markdown / JSON / PDF)
* :mod:`.pipeline`       - orchestrator and composition root for the whole run

Module boundaries
-----------------
This engine sits at the end of the chain::

    evidence_ocr_engine -> evidence_correlation_engine -> timeline_report_engine
                                      ^
                          threat_intelligence_system

It imports the correlation engine (models, configuration, the storage gateway
and the audit trail) and, through it, the OCR engine. Neither imports back, so
the dependency graph is a straight line.

Everything downstream of correlation lives here rather than in the correlation
engine because ``graph``, ``analytics`` and ``prioritization`` all consume
``TimelineAnalysis``; splitting them from the timeline would have made the two
engines mutually importing.

Because the upstream engines are resolved by path rather than by installation,
importing this package puts the correlation engine root on ``sys.path`` (which
in turn bootstraps the OCR engine). ``CIIS_CORRELATION_ROOT`` overrides the
default sibling location.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Root of this engine (the directory containing this package).
TIMELINE_REPORT_ENGINE_ROOT = Path(__file__).resolve().parent.parent

#: Root of the upstream correlation engine, which supplies the analytical
#: models, ``InvestigationConfig``, ``CaseDataRepository`` and the audit trail -
#: and which bootstraps the OCR engine in turn.
CORRELATION_ENGINE_ROOT = Path(
    os.environ.get(
        "CIIS_CORRELATION_ROOT",
        TIMELINE_REPORT_ENGINE_ROOT.parent / "evidence_correlation_engine",
    )
).resolve()


def _bootstrap_correlation_engine() -> None:
    """Make the upstream engines importable before any submodule needs them.

    Must run at package-import time: every service here imports
    ``ciis_correlation`` at module scope, and several import
    ``backend.modules.evidence`` too.

    Importing ``ciis_correlation`` (rather than only adding its root to
    ``sys.path``) is what chains the bootstrap: that package's own ``__init__``
    is what puts the OCR engine on the path. Adding the path alone would leave
    ``backend`` unimportable until something happened to import the correlation
    package first.
    """
    root = str(CORRELATION_ENGINE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    import ciis_correlation  # noqa: F401  (chains the OCR-engine bootstrap)


_bootstrap_correlation_engine()

__all__ = ["TIMELINE_REPORT_ENGINE_ROOT", "CORRELATION_ENGINE_ROOT"]
