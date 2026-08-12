from __future__ import annotations

from dataclasses import replace

from ciis_rag.documents import build_chunks, split_text


def test_chunking_is_bounded_and_overlapping():
    text = " ".join(f"word-{index}" for index in range(300))
    chunks = split_text(text, max_chars=500, overlap_chars=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)
    assert "word-0" in chunks[0]
    assert "word-299" in chunks[-1]


def test_documents_use_reconstructed_time_and_case_scoped_ids(bundle, config):
    chunks = build_chunks(bundle, config)
    evidence_chunks = [c for c in chunks if c.evidence_id == "EVID_001"]
    assert evidence_chunks
    assert "Time: 2026-01-01T10:00:00Z" in evidence_chunks[0].text
    assert "source=content_chat_timestamp" in evidence_chunks[0].text
    assert "inferred=false" in evidence_chunks[0].text
    assert "Cleaned OCR text:" in evidence_chunks[0].text
    assert "Raw OCR text:" in evidence_chunks[0].text
    assert evidence_chunks[0].chunk_id.startswith("CASE_A:EVID_001:")
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_long_evidence_creates_stable_numbered_chunks(bundle, config):
    long_evidence = replace(
        bundle.evidence[0], cleaned_text="section " * 400
    )
    changed = replace(bundle, evidence=(long_evidence, bundle.evidence[1]))
    chunks = [
        chunk for chunk in build_chunks(changed, config)
        if chunk.evidence_id == "EVID_001"
    ]
    assert len(chunks) > 2
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
