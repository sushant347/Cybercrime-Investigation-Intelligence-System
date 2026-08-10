from __future__ import annotations

from dataclasses import replace

from ciis_rag.core.models import EvidenceItem
from ciis_rag.indexing import InMemoryVectorStore, IndexService, ManifestRepository


def service(config, store):
    return IndexService(config, store, ManifestRepository(config.manifest_dir))


def test_sync_is_incremental_and_detects_fresh_index(bundle, config):
    store = InMemoryVectorStore()
    indexing = service(config, store)
    first = indexing.sync(bundle)
    assert first.added_or_updated == first.total_chunks
    assert indexing.status(bundle) == "fresh"

    second = indexing.sync(bundle)
    assert second.status == "fresh"
    assert second.added_or_updated == 0
    assert second.deleted == 0
    assert second.unchanged == second.total_chunks


def test_embedding_model_change_forces_reembedding(bundle, config):
    store = InMemoryVectorStore()
    manifests = ManifestRepository(config.manifest_dir)
    service(config, store).sync(bundle)
    changed_config = replace(config, embedding_model="different-embedding-model")
    result = IndexService(changed_config, store, manifests).sync(bundle)
    assert result.added_or_updated == result.total_chunks
    assert result.unchanged == 0


def test_new_and_removed_evidence_update_only_derived_chunks(bundle, config):
    store = InMemoryVectorStore()
    indexing = service(config, store)
    indexing.sync(bundle)
    added = EvidenceItem(
        case_id=bundle.case_id,
        evidence_id="EVID_003",
        file_name="new.txt",
        raw_text="Newly uploaded evidence",
        cleaned_text="Newly uploaded evidence",
        upload_time="2026-01-05T00:00:00Z",
        file_hash="hash-c",
    )
    expanded = replace(
        bundle,
        evidence=bundle.evidence + (added,),
        source_hashes={"case_json": "source-b"},
    )
    result = indexing.sync(expanded)
    assert result.added_or_updated >= 2  # new evidence + changed overview
    assert any(c.evidence_id == "EVID_003" for c in store.list_chunks(bundle.case_id))

    reduced = replace(
        expanded,
        evidence=(bundle.evidence[0],),
        source_hashes={"case_json": "source-c"},
    )
    result = indexing.sync(reduced)
    assert result.deleted >= 2
    assert {c.evidence_id for c in store.list_chunks(bundle.case_id)} == {
        "EVID_001", f"CASE_OVERVIEW_{bundle.case_id}"
    }


def test_same_evidence_id_is_isolated_between_cases(bundle, config):
    store = InMemoryVectorStore()
    indexing = service(config, store)
    indexing.sync(bundle)
    other_evidence = replace(bundle.evidence[0], case_id="CASE_B", raw_text="other case")
    other = replace(
        bundle,
        case_id="CASE_B",
        evidence=(other_evidence,),
        relationships=(),
        timeline=(),
        source_hashes={"case_json": "other"},
    )
    indexing.sync(other)
    assert all(c.case_id == "CASE_A" for c in store.list_chunks("CASE_A"))
    assert all(c.case_id == "CASE_B" for c in store.list_chunks("CASE_B"))
    assert len(store.list_chunks("CASE_A")) != 0
    assert len(store.list_chunks("CASE_B")) != 0
