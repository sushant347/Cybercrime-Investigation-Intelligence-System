"""Unit tests for entity-extraction Precision/Recall/F1."""
import math

from backend.modules.evidence.evaluation import entity_metrics as em


def test_perfect_match():
    gold = {"urls": ["http://x.com"], "emails": ["a@b.com"]}
    score = em.entity_prf1(gold, gold)
    assert score.micro.precision == 1.0
    assert score.micro.recall == 1.0
    assert score.macro_f1 == 1.0


def test_partial_recall():
    gold = {"urls": ["http://x.com"], "emails": ["a@b.com"]}
    pred = {"urls": ["http://x.com"]}  # missed the email
    score = em.entity_prf1(gold, pred)
    assert score.per_type["urls"].f1 == 1.0
    assert score.per_type["emails"].f1 == 0.0
    assert math.isclose(score.micro.recall, 0.5)
    assert math.isclose(score.micro.precision, 1.0)
    assert math.isclose(score.macro_f1, 0.5)


def test_false_positive_lowers_precision():
    gold = {"urls": ["http://x.com"]}
    pred = {"urls": ["http://x.com", "http://spam.com"]}
    score = em.entity_prf1(gold, pred)
    assert math.isclose(score.per_type["urls"].precision, 0.5)
    assert score.per_type["urls"].recall == 1.0


def test_url_trailing_slash_normalized_as_match():
    gold = {"urls": ["http://x.com"]}
    pred = {"urls": ["http://x.com/"]}
    score = em.entity_prf1(gold, pred)
    assert score.per_type["urls"].f1 == 1.0


def test_phone_spacing_normalized():
    gold = {"phones": ["+977 9812345678"]}
    pred = {"phones": ["+9779812345678"]}
    score = em.entity_prf1(gold, pred)
    assert score.per_type["phones"].tp == 1


def test_corpus_micro_macro():
    s1 = em.entity_prf1({"urls": ["a"]}, {"urls": ["a"]})
    s2 = em.entity_prf1({"emails": ["b"]}, {"emails": ["c"]})  # wrong
    combined = em.micro_macro_average([s1, s2])
    assert combined.micro.tp == 1
    assert combined.micro.fp == 1
    assert combined.micro.fn == 1
    d = combined.to_dict()
    assert "per_type" in d and "micro" in d
