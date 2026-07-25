"""Reusable binary-classification metrics — dependency-free.

The trained URL classifier's metrics (Table 6.3) are produced by sklearn inside
``threat_intelligence_system`` and stored in the retraining report; this module
provides the *same* quantities as small, pure-Python, test-backed functions so
any evaluation in this repo can compute a confusion matrix, accuracy,
precision / recall / F1, false-negative/positive rate, ROC-AUC and PR-AUC
without a heavy dependency — and so the stored report can be cross-checked for
internal consistency (see ``tests`` and the Table 6.3 verification test).

Nothing here fabricates a result: every function is a deterministic
transformation of labels/scores you pass in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass
class ConfusionMatrix:
    """2x2 counts with the positive class as label ``1``."""

    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0

    @property
    def false_negative_rate(self) -> float:
        d = self.fn + self.tp
        return self.fn / d if d else 0.0

    @property
    def false_positive_rate(self) -> float:
        d = self.fp + self.tn
        return self.fp / d if d else 0.0

    def matrix(self) -> List[List[int]]:
        """Row 0 = actual negative, row 1 = actual positive; col order [neg, pos]."""
        return [[self.tn, self.fp], [self.fn, self.tp]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "confusion_matrix": self.matrix(),
            "tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn,
            "accuracy": round(self.accuracy, 6),
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "false_negative_rate": round(self.false_negative_rate, 6),
            "false_positive_rate": round(self.false_positive_rate, 6),
        }


def confusion_matrix(
    y_true: Sequence[int], y_pred: Sequence[int], positive_label: int = 1
) -> ConfusionMatrix:
    """Build a 2x2 confusion matrix from true/predicted labels."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    cm = ConfusionMatrix()
    for actual, predicted in zip(y_true, y_pred):
        a = actual == positive_label
        p = predicted == positive_label
        if a and p:
            cm.tp += 1
        elif not a and p:
            cm.fp += 1
        elif not a and not p:
            cm.tn += 1
        else:
            cm.fn += 1
    return cm


def _pos_neg_scores(
    y_true: Sequence[int], scores: Sequence[float], positive_label: int
) -> Tuple[List[float], List[float]]:
    pos = [s for t, s in zip(y_true, scores) if t == positive_label]
    neg = [s for t, s in zip(y_true, scores) if t != positive_label]
    return pos, neg


def roc_auc(
    y_true: Sequence[int], scores: Sequence[float], positive_label: int = 1
) -> float:
    """ROC-AUC via the Mann-Whitney U statistic (rank-based, ties handled).

    Equivalent to the probability that a random positive scores higher than a
    random negative. Returns 0.5 when one class is absent (undefined AUC).
    """
    if len(y_true) != len(scores):
        raise ValueError("y_true and scores must be the same length")
    pos, neg = _pos_neg_scores(y_true, scores, positive_label)
    n_pos, n_neg = len(pos), len(neg)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    # Rank all scores (average ranks for ties), sum ranks of positives.
    ordered = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and scores[ordered[j + 1]] == scores[ordered[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based average rank
        for k in range(i, j + 1):
            ranks[ordered[k]] = avg_rank
        i = j + 1
    rank_sum_pos = sum(r for r, t in zip(ranks, y_true) if t == positive_label)
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def pr_auc(
    y_true: Sequence[int], scores: Sequence[float], positive_label: int = 1
) -> float:
    """Average precision (area under the precision-recall curve).

    Uses the sklearn ``average_precision_score`` definition:
    ``AP = sum_n (R_n - R_{n-1}) * P_n`` over thresholds set at each score.
    """
    if len(y_true) != len(scores):
        raise ValueError("y_true and scores must be the same length")
    total_pos = sum(1 for t in y_true if t == positive_label)
    if total_pos == 0:
        return 0.0
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    tp = fp = 0
    prev_recall = 0.0
    ap = 0.0
    idx = 0
    n = len(order)
    while idx < n:
        threshold = scores[order[idx]]
        # advance through all points at this threshold (a single decision cut)
        while idx < n and scores[order[idx]] == threshold:
            if y_true[order[idx]] == positive_label:
                tp += 1
            else:
                fp += 1
            idx += 1
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / total_pos
        ap += (recall - prev_recall) * precision
        prev_recall = recall
    return ap
