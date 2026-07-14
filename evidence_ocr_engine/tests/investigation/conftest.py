"""Fixtures for the Phase-2 investigation test suite.

Builds one fully synthetic case (CASE_9001) inside temp storage, mirroring
every real storage format the data gateway reads: evidence.csv,
entities.csv, the case JSON, Phase-1 forensic report envelopes, and a
threat-intelligence indicator file.

Designed relationships:
  EVID_A <-> EVID_B : shared phone + wallet + device + 2h apart  (VERY strong)
  EVID_A <-> EVID_C : shared malicious domain + threat intel     (strong)
  EVID_D            : unrelated (only a lone email, distant time)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

import pytest

from backend.modules.evidence.config import EvidenceConfig
from backend.modules.investigation.audit import InvestigationAuditTrail
from backend.modules.investigation.config import InvestigationConfig
from backend.modules.investigation.data_access import CaseDataRepository
from backend.modules.investigation.repository import InvestigationReportRepository

CASE = "CASE_9001"

_EVIDENCE_FIELDS = [
    "evidence_id", "case_id", "original_file_name", "stored_file_name",
    "file_extension", "file_size_bytes", "sha256_before", "sha256_after",
    "hash_verified", "upload_time", "processing_time", "status",
    "investigator_notes",
]

_EVIDENCE_ROWS = [
    ("EVID_A", "chat_offer.png", "a" * 64, "2026-07-01T10:00:00.000Z",
     "Hello dear customer you won a prize. Please verify your account. "
     "Enter your login password at http://scam-bank.top/login"),
    ("EVID_B", "esewa_payment.png", "b" * 64, "2026-07-01T12:00:00.000Z",
     "Send money via esewa now. Paid rs. 5000. OTP 4521 shared."),
    ("EVID_C", "warning_sms.png", "c" * 64, "2026-07-03T10:00:00.000Z",
     "URGENT your account is suspended, verify immediately at "
     "http://scam-bank.top/verify"),
    ("EVID_D", "victim_note.png", "d" * 64, "2026-07-04T09:00:00.000Z",
     "He blocked me after payment, I was scammed, filing police report."),
]

_ENTITIES: List[tuple] = [
    ("EVID_A", "phones", "9812345678"),
    ("EVID_A", "wallets", "esewa:9812345678"),
    ("EVID_A", "urls", "http://scam-bank.top/login"),
    ("EVID_A", "domains", "scam-bank.top"),
    ("EVID_B", "phones", "9812345678"),
    ("EVID_B", "wallets", "esewa:9812345678"),
    ("EVID_B", "money", "rs 5000"),
    ("EVID_B", "otp", "4521"),
    ("EVID_C", "urls", "http://scam-bank.top/verify"),
    ("EVID_C", "domains", "scam-bank.top"),
    ("EVID_D", "emails", "victim@example.com"),
]

_FORENSICS: Dict[str, Dict[str, dict]] = {
    "EVID_A": {
        "evidence_confidence": {"confidence_score": 85.0,
                                "confidence_level": "VERY_HIGH",
                                "explanation": "test"},
        "forgery_report": {"forgery_score": 10.0, "forgery_risk": "LOW"},
        "metadata_report": {"image": {"has_exif": True,
                                      "device": "Samsung SM-A505",
                                      "software": "", "gps": {}},
                            "consistency_notes": []},
        "logo_detections": {"detected_brands": ["eSewa"]},
    },
    "EVID_B": {
        "evidence_confidence": {"confidence_score": 80.0,
                                "confidence_level": "HIGH",
                                "explanation": "test"},
        "forgery_report": {"forgery_score": 12.0, "forgery_risk": "LOW"},
        "metadata_report": {"image": {"has_exif": True,
                                      "device": "Samsung SM-A505",
                                      "software": "", "gps": {}},
                            "consistency_notes": []},
        "logo_detections": {"detected_brands": ["eSewa"]},
    },
    "EVID_C": {
        "evidence_confidence": {"confidence_score": 60.0,
                                "confidence_level": "MODERATE",
                                "explanation": "test"},
        "forgery_report": {"forgery_score": 65.0, "forgery_risk": "HIGH"},
        "metadata_report": {"image": {"has_exif": False, "device": "",
                                      "software": "", "gps": {}},
                            "consistency_notes": ["no EXIF metadata"]},
    },
    "EVID_D": {
        "evidence_confidence": {"confidence_score": 70.0,
                                "confidence_level": "HIGH",
                                "explanation": "test"},
    },
}


def _seed_case(config: EvidenceConfig, icfg: InvestigationConfig) -> None:
    # evidence.csv (exact legacy schema)
    with open(config.evidence_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_EVIDENCE_FIELDS)
        writer.writeheader()
        for evidence_id, name, sha, upload, _text in _EVIDENCE_ROWS:
            writer.writerow({
                "evidence_id": evidence_id, "case_id": CASE,
                "original_file_name": name,
                "stored_file_name": f"{evidence_id}__x__{name}",
                "file_extension": ".png", "file_size_bytes": "1000",
                "sha256_before": sha, "sha256_after": sha,
                "hash_verified": "True", "upload_time": upload,
                "processing_time": upload, "status": "processed",
                "investigator_notes": "",
            })
    # entities.csv (exact legacy schema)
    with open(icfg.entities_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "evidence_id", "entity_type", "value",
                         "normalized", "extracted_at"])
        for evidence_id, entity_type, value in _ENTITIES:
            writer.writerow([CASE, evidence_id, entity_type, value, value,
                             "2026-07-05T00:00:00.000Z"])
    # case JSON (raw_text + confidence per evidence)
    case_doc = {
        "case_id": CASE, "created_at": "2026-07-01T00:00:00.000Z",
        "updated_at": "2026-07-04T00:00:00.000Z",
        "evidence_count": len(_EVIDENCE_ROWS),
        "evidence": [
            {"evidence_id": evidence_id, "case_id": CASE, "raw_text": text,
             "average_confidence": 0.9}
            for evidence_id, _n, _s, _u, text in _EVIDENCE_ROWS
        ],
    }
    config.json_dir.mkdir(parents=True, exist_ok=True)
    (config.json_dir / f"{CASE}.json").write_text(
        json.dumps(case_doc), encoding="utf-8")
    # Phase-1 forensic report envelopes
    for evidence_id, reports in _FORENSICS.items():
        directory = icfg.forensics_dir / evidence_id
        directory.mkdir(parents=True, exist_ok=True)
        for name, payload in reports.items():
            (directory / f"{name}.json").write_text(json.dumps({
                "report_type": name, "report_version": 1,
                "evidence_id": evidence_id, "case_id": CASE,
                "report": payload,
            }), encoding="utf-8")
    # threat intel indicator file
    icfg.threat_intel_json.parent.mkdir(parents=True, exist_ok=True)
    icfg.threat_intel_json.write_text(json.dumps({
        "indicators": {"scam-bank.top": {"verdict": "malicious",
                                         "source": "unit-test"}}
    }), encoding="utf-8")


@pytest.fixture()
def icfg(config: EvidenceConfig) -> InvestigationConfig:
    investigation = InvestigationConfig.from_evidence_config(config)
    investigation.ensure_directories()
    _seed_case(config, investigation)
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
