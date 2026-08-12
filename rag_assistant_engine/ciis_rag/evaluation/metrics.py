"""Dependency-free metrics suitable for a labelled RAG evaluation set."""

from __future__ import annotations


def retrieval_metrics(
    expected: dict[str, set[str]],
    retrieved: dict[str, list[str]],
) -> dict[str, float]:
    """Macro Recall@K, Precision@K, and reciprocal rank by query id."""
    recalls: list[float] = []
    precisions: list[float] = []
    reciprocal_ranks: list[float] = []
    for query_id, relevant in expected.items():
        ranked = retrieved.get(query_id, [])
        found = relevant & set(ranked)
        recalls.append(len(found) / len(relevant) if relevant else 1.0)
        precisions.append(len(found) / len(ranked) if ranked else 0.0)
        rank = next((index for index, value in enumerate(ranked, 1) if value in relevant), None)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
    count = max(1, len(expected))
    return {
        "query_count": float(len(expected)),
        "recall_at_k": sum(recalls) / count,
        "precision_at_k": sum(precisions) / count,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / count,
    }


def citation_metrics(expected: set[str], predicted: set[str]) -> dict[str, float]:
    true_positive = len(expected & predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}
