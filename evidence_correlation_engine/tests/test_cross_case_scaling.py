"""Cross-case correlation must not become quadratic.

It is the one component with a genuinely super-linear shape available to it:
for every entity of the case under analysis it consults every occurrence of
that value across every other case. Measured, it currently grows as roughly
n^1.1 - near-linear - and handles 256,000 entities in about 3.4 seconds.

That property is easy to lose. Replacing an index lookup with a scan, or
moving a filter inside a loop, turns it quadratic while every functional test
still passes, and nobody notices until a real unit has a year of cases in it.

This pins the shape rather than the speed. Absolute timings vary by machine and
would be flaky; the *ratio* between two sizes on the same machine is stable to
a few percent, and the gap between near-linear (~1.0) and quadratic (2.0) is
enormous. The bound is set at 1.5 - far above anything observed, far below
quadratic - so it fails on a genuine regression and not on a slow runner.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scale_cross_case.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("scale_cross_case", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    assert _SCRIPT.is_file(), f"scale harness missing: {_SCRIPT}"
    return _load_harness()


def test_cross_case_correlation_stays_sub_quadratic(harness):
    small = harness.measure(cases=25, evidence_per_case=8,
                            entities_per_item=20, shared_every=25)
    large = harness.measure(cases=100, evidence_per_case=8,
                            entities_per_item=20, shared_every=25)

    assert small["correlate_s"] > 0, "timer resolution too coarse to judge"
    size_ratio = large["entities"] / small["entities"]
    time_ratio = large["correlate_s"] / small["correlate_s"]
    exponent = math.log(time_ratio) / math.log(size_ratio)

    assert exponent < 1.5, (
        f"cross-case correlation now grows as n^{exponent:.2f} "
        f"({small['entities']} entities in {small['correlate_s']}s, "
        f"{large['entities']} in {large['correlate_s']}s). It was ~n^1.1. "
        "Something in the lookup path has become a scan."
    )


def test_the_synthetic_corpus_actually_produces_links(harness):
    """A sweep that links nothing would measure the wrong code path.

    Without collisions the matcher exits early and the timing above would be
    of an empty loop, so the guard would pass while measuring nothing.
    """
    result = harness.measure(cases=10, evidence_per_case=8,
                             entities_per_item=20, shared_every=25)
    assert result["links"] > 0, "synthetic corpus produced no cross-case links"
