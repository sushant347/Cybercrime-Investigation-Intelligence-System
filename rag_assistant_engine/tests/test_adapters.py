from __future__ import annotations

import pytest

from ciis_rag.adapters import bundle_from_documents
from ciis_rag.core.exceptions import ArtifactContractError


def current_documents():
    case = {
        "case_id": "CASE_NOW",
        "evidence": [{
            "evidence_id": "EVID_010",
            "file_name": "message.png",
            "raw_text": "Pay 5000 to 9800000001",
            "upload_time": "2026-07-01T10:00:00Z",
            "file_hash": "abc",
            "cleaning": {
                "cleaned_text": "Pay 5000 to 9800000001",
                "entities": {
                    "phone_numbers": [{"value": "9800000001", "normalized": "9800000001"}]
                },
                "risk_signals": {"financial": True, "threat": False},
            },
        }, {
            "evidence_id": "EVID_011",
            "file_name": "receipt.pdf",
            "raw_text": "Transfer receipt",
            "upload_time": "2026-07-01T10:05:00Z",
            "cleaning": {},
        }],
    }
    artifacts = {
        "timeline": {"case_id": "CASE_NOW", "report": {"case_id": "CASE_NOW", "events": [{
            "evidence_id": "EVID_010",
            "timestamp": "2026-06-11T21:41:00Z",
            "time_source": "content_chat_timestamp",
            "confidence": "high",
            "timestamp_inferred": False,
            "source_evidence_ids": "EVID_010 EVID_011",
        }]}},
        "correlation": {"case_id": "CASE_NOW", "report": {
            "case_id": "CASE_NOW",
            "related_pair_count": 1,
            "pairs": [{
                "evidence_a": "EVID_010",
                "evidence_b": "EVID_011",
                "correlation_confidence": 0.88,
                "relationship_strength": "STRONG",
                "factors": [{
                    "factor": "phone_numbers",
                    "supporting_evidence": ["9800000001"],
                }],
                "explanation": "shared phone",
            }],
        }},
        "graph": {"case_id": "CASE_NOW", "report": {
            "case_id": "CASE_NOW", "nodes": [], "edges": []
        }},
    }
    return case, artifacts


def test_current_envelopes_are_normalized():
    case, artifacts = current_documents()
    bundle = bundle_from_documents(case, artifacts)
    assert bundle.case_id == "CASE_NOW"
    assert bundle.timeline[0].timestamp == "2026-06-11T21:41:00Z"
    assert bundle.timeline[0].inferred is False
    assert bundle.relationships[0].confidence == 0.88
    assert bundle.relationships[0].shared_entities == (
        "phone_numbers=9800000001",
    )
    assert bundle.evidence[0].entities[0].normalized == "9800000001"


def test_artifact_from_another_case_is_rejected():
    case, artifacts = current_documents()
    artifacts["timeline"]["case_id"] = "CASE_OTHER"
    artifacts["timeline"]["report"]["case_id"] = "CASE_OTHER"
    with pytest.raises(ArtifactContractError, match="CASE_OTHER"):
        bundle_from_documents(case, artifacts)


def test_stale_phase_two_artifacts_are_ignored():
    case, artifacts = current_documents()
    artifacts["graph"]["report"]["nodes"] = [{
        "id": "evidence:EVID_010",
        "node_type": "evidence",
        "properties": {"file_name": "replaced-old-file.png"},
    }]

    bundle = bundle_from_documents(case, artifacts)

    assert bundle.timeline == ()
    assert bundle.relationships == ()
    assert bundle.summary["related_pair_count"] == 0
    assert bundle.warnings == (
        "Ignored stale Phase-2 artifacts because their evidence filenames do not "
        "match the current case records: EVID_010",
    )


def test_cross_case_graph_relationships_are_not_imported():
    case, artifacts = current_documents()
    artifacts["graph"]["report"]["edges"] = [{
        "source": "evidence:EVID_010",
        "target": "evidence:EVID_OTHER",
        "edge_type": "cross_case_relationship",
        "confidence": 0.9,
        "source_evidence_ids": ["EVID_010", "EVID_OTHER"],
    }]

    bundle = bundle_from_documents(case, artifacts)

    assert len(bundle.relationships) == 1
    assert bundle.relationships[0].evidence_a == "EVID_010"
    assert bundle.relationships[0].evidence_b == "EVID_011"


def test_implausible_reconstructed_year_is_rejected():
    case, artifacts = current_documents()
    artifacts["timeline"]["report"]["events"][0]["timestamp"] = (
        "0111-06-26T00:42:00+00:00"
    )

    bundle = bundle_from_documents(case, artifacts)

    assert bundle.timeline == ()
    assert bundle.warnings == (
        "Ignored implausible reconstructed timestamp(s): "
        "EVID_010=0111-06-26T00:42:00+00:00",
    )


def test_report_legal_priority_and_primary_sources_become_searchable_sections():
    case, artifacts = current_documents()
    artifacts.update({
        "priority": {"case_id": "CASE_NOW", "report": {
            "case_id": "CASE_NOW",
            "priority_level": "HIGH",
            "explanation": "Payment loss and credential theft indicators",
        }},
        "report": {"case_id": "CASE_NOW", "report": {
            "case_id": "CASE_NOW",
            "sections": {
                "evidence_summary": [
                    {"evidence_id": "EVID_010", "file": "message.png"},
                    {"evidence_id": "EVID_011", "file": "receipt.pdf"},
                ],
                "legal_basis": {
                    "summary": "Section 52 is engaged by the payment evidence.",
                    "provisions": [{
                        "section": "52",
                        "evidence_ids": ["EVID_010", "EVID_011"],
                    }],
                    "sources": [{
                        "source_id": "eta_2063",
                        "authority": "Nepal Law Commission",
                        "title": "Electronic Transactions Act, 2063",
                        "url": "https://lawcommission.gov.np/content/13397/",
                    }],
                },
            },
        }},
    })

    bundle = bundle_from_documents(case, artifacts)
    sections = {section.source_id: section for section in bundle.artifact_sections}

    assert "REPORT_LEGAL_BASIS" in sections
    assert sections["REPORT_LEGAL_BASIS"].evidence_ids == (
        "EVID_010", "EVID_011"
    )
    assert sections["SOURCE_ETA_2063"].source_url.startswith("https://")
    assert "ARTIFACT_PRIORITY" in sections
    assert "TIMELINE_EVID_010" in sections
    assert sections["TIMELINE_EVID_010"].evidence_ids == (
        "EVID_010", "EVID_011"
    )


def test_stale_full_analysis_is_withheld_after_new_evidence():
    case, artifacts = current_documents()
    case["evidence"].append({
        "evidence_id": "EVID_012",
        "file_name": "new-message.txt",
        "raw_text": "Newly uploaded evidence",
        "cleaning": {},
    })
    artifacts["analysis_manifest"] = {
        "case_id": "CASE_NOW",
        "report": {
            "case_id": "CASE_NOW",
            "evidence_ids": ["EVID_010", "EVID_011"],
        },
    }
    artifacts["report"] = {
        "case_id": "CASE_NOW",
        "report": {
            "case_id": "CASE_NOW",
            "sections": {"legal_basis": {"summary": "old legal result"}},
        },
    }

    bundle = bundle_from_documents(case, artifacts)

    assert all(
        section.source_id != "REPORT_LEGAL_BASIS"
        for section in bundle.artifact_sections
    )
    assert any("predate the current evidence set" in item for item in bundle.warnings)
    assert {item.evidence_id for item in bundle.evidence} == {
        "EVID_010", "EVID_011", "EVID_012"
    }
