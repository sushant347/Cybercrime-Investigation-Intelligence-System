from ciis_rag.evaluation import citation_metrics, retrieval_metrics


def test_retrieval_metrics_report_recall_precision_and_rank():
    result = retrieval_metrics(
        {"q1": {"E1", "E2"}, "q2": {"E3"}},
        {"q1": ["E1", "NOISE"], "q2": ["NOISE", "E3"]},
    )
    assert result["recall_at_k"] == 0.75
    assert result["precision_at_k"] == 0.5
    assert result["mean_reciprocal_rank"] == 0.75


def test_citation_metrics():
    result = citation_metrics({"E1", "E2"}, {"E1", "E3"})
    assert result == {"precision": 0.5, "recall": 0.5, "f1": 0.5}
