"""Fixtures for the timeline & report engine test suite.

Identical fixture surface to the correlation engine's suite, built from the
same :mod:`ciis_correlation.testing` synthetic case, so a test that moves
between the two engines needs no rewriting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Importing this package chains the bootstrap that puts the correlation engine
# and, through it, the OCR engine on sys.path - so it must precede the imports
# below.
import ciis_timeline_report  # noqa: F401

from ciis_correlation.core.audit import InvestigationAuditTrail  # noqa: E402
from ciis_correlation.core.config import InvestigationConfig  # noqa: E402
from ciis_correlation.core.data_access import CaseDataRepository  # noqa: E402
from ciis_correlation.core.repository import (  # noqa: E402
    InvestigationReportRepository,
)
from ciis_correlation.testing import CASE, seed_case  # noqa: E402

from backend.modules.evidence.config import EvidenceConfig  # noqa: E402

__all__ = ["CASE"]


@pytest.fixture()
def config(tmp_path: Path) -> EvidenceConfig:
    """Isolated OCR-engine configuration: storage lives under a temp directory."""
    storage = tmp_path / "storage"
    cfg = EvidenceConfig(
        base_dir=tmp_path,
        storage_dir=storage,
        json_dir=storage / "json",
        originals_dir=storage / "originals",
        log_dir=tmp_path / "logs",
        cases_csv=storage / "cases.csv",
        evidence_csv=storage / "evidence.csv",
        ocr_results_csv=storage / "ocr_results.csv",
        processing_log_csv=storage / "processing_log.csv",
    )
    cfg.ensure_directories()
    return cfg


@pytest.fixture()
def icfg(config: EvidenceConfig) -> InvestigationConfig:
    investigation = InvestigationConfig.from_evidence_config(config)
    investigation.ensure_directories()
    seed_case(config, investigation)
    return investigation


@pytest.fixture()
def data(icfg: InvestigationConfig) -> CaseDataRepository:
    return CaseDataRepository(icfg)


@pytest.fixture()
def repo(icfg: InvestigationConfig) -> InvestigationReportRepository:
    return InvestigationReportRepository(icfg)


@pytest.fixture()
def audit(icfg: InvestigationConfig) -> InvestigationAuditTrail:
    return InvestigationAuditTrail(icfg)
