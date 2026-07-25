"""Reusable classification metrics — verified on known-answer toy inputs.

The ROC-AUC / PR-AUC implementations are checked against hand-computed values
so they need no sklearn dependency to be trusted.
"""

import math

import pytest

from backend.modules.investigation.evaluation.classification_metrics import (
    confusion_matrix,
    pr_auc,
    roc_auc,
)


def test_confusion_matrix_counts_and_derived():
    y_true = [1, 1, 1, 0, 0, 0]
    y_pred = [1, 1, 0, 0, 0, 1]  # tp=2, fn=1, tn=2, fp=1
    cm = confusion_matrix(y_true, y_pred)
    assert (cm.tp, cm.fn, cm.tn, cm.fp) == (2, 1, 2, 1)
    assert cm.matrix() == [[2, 1], [1, 2]]  # [[tn,fp],[fn,tp]]
    assert cm.accuracy == pytest.approx(4 / 6)
    assert cm.precision == pytest.approx(2 / 3)
    assert cm.recall == pytest.approx(2 / 3)
    assert cm.f1 == pytest.approx(2 / 3)
    assert cm.false_negative_rate == pytest.approx(1 / 3)


def test_confusion_matrix_length_mismatch_raises():
    with pytest.raises(ValueError):
        confusion_matrix([1, 0], [1])


def test_roc_auc_perfect_separation_is_one():
    y_true = [0, 0, 1, 1]
    scores = [0.1, 0.2, 0.8, 0.9]
    assert roc_auc(y_true, scores) == pytest.approx(1.0)


def test_roc_auc_reversed_is_zero():
    y_true = [0, 0, 1, 1]
    scores = [0.9, 0.8, 0.2, 0.1]
    assert roc_auc(y_true, scores) == pytest.approx(0.0)


def test_roc_auc_known_value_with_ties():
    # 2 pos, 2 neg; one tie between a pos and a neg at 0.5.
    y_true = [1, 0, 1, 0]
    scores = [0.9, 0.5, 0.5, 0.1]
    # pairs (pos,neg): (0.9,0.5)=1, (0.9,0.1)=1, (0.5,0.5)=0.5, (0.5,0.1)=1
    # AUC = (1+1+0.5+1)/4 = 0.875
    assert roc_auc(y_true, scores) == pytest.approx(0.875)


def test_roc_auc_single_class_is_half():
    assert roc_auc([1, 1, 1], [0.1, 0.2, 0.3]) == pytest.approx(0.5)


def test_pr_auc_perfect_is_one():
    y_true = [0, 0, 1, 1]
    scores = [0.1, 0.2, 0.8, 0.9]
    assert pr_auc(y_true, scores) == pytest.approx(1.0)


def test_pr_auc_known_value():
    # ranked desc: 0.9(pos),0.8(neg),0.4(pos),0.1(neg)
    #   after 0.9: P=1/1, R=1/2 -> (0.5-0)*1   = 0.5
    #   after 0.8: P=1/2, R=1/2 -> (0.5-0.5)*.5= 0
    #   after 0.4: P=2/3, R=1   -> (1-0.5)*2/3 = 0.3333
    #   after 0.1: P=2/4, R=1   -> 0
    y_true = [1, 0, 1, 0]
    scores = [0.9, 0.8, 0.4, 0.1]
    assert pr_auc(y_true, scores) == pytest.approx(0.5 + 1 / 3, abs=1e-6)


def test_pr_auc_no_positives_is_zero():
    assert pr_auc([0, 0, 0], [0.1, 0.2, 0.3]) == 0.0
