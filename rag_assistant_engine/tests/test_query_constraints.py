from __future__ import annotations

from ciis_rag.retrieval.constraints import extract_query_constraints


def test_query_constraints_normalize_exact_values():
    constraints = extract_query_constraints(
        "Compare EVID_0007, NPR 250,000, user@example.com and +977-9800000001"
    )
    values = {(item.kind, item.normalized) for item in constraints}
    assert ("evidence_id", "EVID_0007") in values
    assert ("money", "250000") in values
    assert ("email", "user@example.com") in values
    assert ("phone", "9779800000001") in values
    assert next(item.display for item in constraints if item.kind == "money") == (
        "NPR 250,000"
    )


def test_money_digits_are_not_misclassified_as_phone():
    constraints = extract_query_constraints("Find NPR 250000 in this case")
    assert [(item.kind, item.normalized) for item in constraints] == [
        ("money", "250000")
    ]
