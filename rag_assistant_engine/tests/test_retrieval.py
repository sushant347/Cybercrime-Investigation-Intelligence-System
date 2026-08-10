from ciis_rag.indexing import InMemoryVectorStore, IndexService, ManifestRepository
from ciis_rag.retrieval import RetrievalService


def test_exact_entity_retrieval_expands_to_correlated_evidence(bundle, config):
    store = InMemoryVectorStore()
    IndexService(config, store, ManifestRepository(config.manifest_dir)).sync(bundle)
    hits = RetrievalService(config, store).retrieve(
        bundle.case_id, "Who used 9800000001?"
    )
    ids = {hit.chunk.evidence_id for hit in hits}
    assert "EVID_001" in ids
    assert "EVID_002" in ids
    assert any("exact_entity" in hit.reasons for hit in hits)
    assert any("graph_neighbor" in hit.reasons for hit in hits)


def test_retrieval_never_crosses_case_collection(bundle, config):
    store = InMemoryVectorStore()
    indexing = IndexService(config, store, ManifestRepository(config.manifest_dir))
    indexing.sync(bundle)
    hits = RetrievalService(config, store).retrieve("CASE_UNKNOWN", "9800000001")
    assert hits == []


def test_shorter_identifier_is_not_exact_match_inside_longer_value(bundle, config):
    store = InMemoryVectorStore()
    IndexService(config, store, ManifestRepository(config.manifest_dir)).sync(bundle)
    hits = RetrievalService(config, store).retrieve(
        bundle.case_id, "Investigate account 98000000010"
    )
    assert all("exact_entity" not in hit.reasons for hit in hits)


def test_explicit_evidence_ids_retrieve_their_own_chunks(bundle, config):
    store = InMemoryVectorStore()
    IndexService(config, store, ManifestRepository(config.manifest_dir)).sync(bundle)
    hits = RetrievalService(config, store).retrieve(
        bundle.case_id, "Compare EVID_001 and EVID_002"
    )
    exact_ids = {
        hit.chunk.evidence_id for hit in hits
        if "exact_evidence_id" in hit.reasons
    }
    assert exact_ids == {"EVID_001", "EVID_002"}
