from __future__ import annotations

import sys
from pathlib import Path

import pytest


ENGINE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ENGINE_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    # GitHub Actions runs pytest with rag_assistant_engine as its working
    # directory. Add the repository parent as well so package-level imports
    # such as ``from rag_assistant_engine import cli`` work there and when the
    # suite is launched from the repository root.
    sys.path.insert(0, str(PROJECT_ROOT))
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from ciis_rag.core.config import RAGConfig
from ciis_rag.core.models import (
    CaseKnowledgeBundle,
    EntityMention,
    EvidenceItem,
    Relationship,
    TimelineFact,
)


@pytest.fixture
def config(tmp_path):
    return RAGConfig(
        storage_dir=tmp_path / "rag",
        top_k=4,
        minimum_relevance=0.12,
        chunk_size_chars=500,
        chunk_overlap_chars=50,
    )


@pytest.fixture
def bundle():
    evidence_a = EvidenceItem(
        case_id="CASE_A",
        evidence_id="EVID_001",
        file_name="chat.txt",
        raw_text="Send the payment to wallet 9800000001 immediately.",
        cleaned_text="Send payment to wallet 9800000001 immediately.",
        upload_time="2026-01-03T00:00:00Z",
        file_hash="hash-a",
        entities=(EntityMention("phone_numbers", "9800000001", "9800000001"),),
        risk_signals=("financial", "urgency"),
    )
    evidence_b = EvidenceItem(
        case_id="CASE_A",
        evidence_id="EVID_002",
        file_name="receipt.txt",
        raw_text="Receipt for the related transfer.",
        cleaned_text="Receipt for related transfer.",
        upload_time="2026-01-04T00:00:00Z",
        file_hash="hash-b",
    )
    return CaseKnowledgeBundle(
        case_id="CASE_A",
        evidence=(evidence_a, evidence_b),
        timeline=(TimelineFact(
            "EVID_001", "2026-01-01T10:00:00Z", "content_chat_timestamp", "high", False
        ),),
        relationships=(Relationship(
            "EVID_001", "EVID_002", "correlation", 0.91,
            ("phone_numbers=9800000001",), "same wallet contact",
        ),),
        summary={"related_pair_count": 1, "node_count": 5, "edge_count": 4},
        source_hashes={"case_json": "source-a"},
    )
