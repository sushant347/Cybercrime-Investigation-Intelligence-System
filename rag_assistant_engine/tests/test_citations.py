from ciis_rag.generation.citations import extract_cited_ids, validate_cited_ids


def test_prefix_evidence_ids_do_not_collide():
    cited = extract_cited_ids(
        "Supported by [EVID_0010].", ["EVID_001", "EVID_0010"]
    )
    assert cited == {"EVID_0010"}


def test_only_retrieved_structured_citations_are_accepted():
    assert validate_cited_ids(
        ["EVID_001", "EVID_NOT_RETRIEVED"], ["EVID_001", "EVID_002"]
    ) == ("EVID_001",)
