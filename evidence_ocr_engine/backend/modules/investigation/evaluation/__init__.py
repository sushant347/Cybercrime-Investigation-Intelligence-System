"""Phase-2 accuracy evaluation harnesses (correlation + timeline).

These measure whether the investigation engine's *conclusions* are correct
against human-annotated ground truth, complementing the unit tests (which only
prove the code runs). They are pure functions over simple inputs so they can be
unit-tested without executing the full pipeline; helpers are provided to pull
the predicted structures out of the services' analysis objects.
"""

from .correlation_eval import (
    CorrelationEval,
    evaluate_correlation,
    predicted_related_pairs,
)
from .timeline_eval import (
    TimelineEval,
    evaluate_timeline,
    predicted_order,
)

__all__ = [
    "CorrelationEval",
    "evaluate_correlation",
    "predicted_related_pairs",
    "TimelineEval",
    "evaluate_timeline",
    "predicted_order",
]
