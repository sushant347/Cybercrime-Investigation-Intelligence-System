"""Phase-2 infrastructure tests: data gateway, repository, audit, threat intel."""

from __future__ import annotations

import csv

from .conftest import CASE


def test_data_gateway_loads_full_context(data):
    items = data.load_case_evidence(CASE)
    assert [c.evidence_id for c in items] == ["EVID_A", "EVID_B", "EVID_C", "EVID_D"]
    a = items[0]
    assert a.file_name == "chat_offer.png"
    assert a.hash_verified is True
    assert "prize" in a.raw_text.lower()
    assert a.ocr_confidence == 0.9
    assert set(a.entity_values("phones")) == {"9812345678"}
    assert a.forensics["evidence_confidence"]["confidence_score"] == 85.0
    assert data.case_exists(CASE)
    assert not data.case_exists("CASE_0000")
    assert data.list_case_ids() == [CASE]


def test_threat_intel_provider(data):
    intel = data.threat_intel
    assert intel.available
    assert intel.is_malicious("scam-bank.top")
    assert intel.is_malicious("http://scam-bank.top/login")  # via domain match
    assert not intel.is_malicious("https://example.com")


def test_repository_versioning_never_overwrites(repo):
    p1 = repo.save(CASE, "correlation_analysis", {"n": 1})
    p2 = repo.save(CASE, "correlation_analysis", {"n": 2})
    assert p1.name == "correlation_analysis.json"
    assert p2.name == "correlation_analysis_v2.json"
    assert p1.exists() and p2.exists()
    assert repo.load_latest(CASE, "correlation_analysis")["report"]["n"] == 2


def test_repository_text_versioning(repo):
    p1 = repo.save_text(CASE, "investigation_report", "# one", ".md")
    p2 = repo.save_text(CASE, "investigation_report", "# two", ".md")
    assert p1.name == "investigation_report.md"
    assert p2.name == "investigation_report_v2.md"
    assert p2.read_text(encoding="utf-8") == "# two"


def test_audit_appends(audit):
    audit.record(CASE, "correlation", "analyzed", "ok", duration_ms=5.0)
    with open(audit.path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[-1]["module"] == "correlation"
    assert rows[-1]["case_id"] == CASE
