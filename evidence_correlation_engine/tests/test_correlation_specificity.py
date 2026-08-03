"""Value-level specificity: how identifying one shared entity value is.

The behaviour under test is the answer to "both items mention NPR 2,000, so
are they related?" - no, and the engine must say so without also becoming
blind to amounts that genuinely are distinctive.
"""

from __future__ import annotations

import pytest

from backend.modules.evidence.config import EvidenceConfig
from ciis_correlation.core.config import InvestigationConfig
from ciis_correlation.correlation.specificity import (
    EntitySpecificityModel,
)


class StubIndex:
    """Corpus statistics without touching the filesystem."""

    def __init__(self, corpus_size: int, frequencies: dict) -> None:
        self._n = corpus_size
        self._df = frequencies

    def total_documents(self) -> int:
        return self._n

    def document_frequency(self, entity_type: str, value: str) -> int:
        return self._df.get(value, 1)


@pytest.fixture()
def cfg(tmp_path):
    return InvestigationConfig.from_evidence_config(
        EvidenceConfig(base_dir=tmp_path, storage_dir=tmp_path / "storage")
    )


def model(cfg, corpus_size=0, frequencies=None):
    return EntitySpecificityModel(cfg, StubIndex(corpus_size, frequencies or {}))


# ------------------------------------------------------------ corpus rarity


def test_value_in_most_of_the_corpus_is_heavily_discounted(cfg):
    m = model(cfg, corpus_size=14, frequencies={"2000": 8})
    score = m.specificity("money", "2000")
    assert score.specificity < 0.3
    assert score.is_common
    assert "common" in score.reason


def test_value_in_only_the_two_matching_items_keeps_full_weight(cfg):
    m = model(cfg, corpus_size=14, frequencies={"9812345678": 2})
    assert m.specificity("phones", "9812345678").specificity > 0.9


def test_rarity_falls_monotonically_as_a_value_spreads(cfg):
    scores = [
        model(cfg, corpus_size=20, frequencies={"x9f2k": df})
        .specificity("wallets", "x9f2k").specificity
        for df in (2, 5, 10, 20)
    ]
    assert scores == sorted(scores, reverse=True), scores


# -------------------------------------------------------- intrinsic prior


def test_round_amounts_are_discounted_before_any_corpus_exists(cfg):
    """A fresh deployment has no statistics, so the prior must carry it."""
    m = model(cfg, corpus_size=0)
    round_amount = m.specificity("money", "2000").specificity
    odd_amount = m.specificity("money", "17432.55").specificity
    assert round_amount < 0.35
    assert odd_amount > round_amount * 2


def test_roundness_scales_with_how_round_the_number_is(cfg):
    m = model(cfg, corpus_size=0)
    values = ["100000", "10000", "1000", "1500", "1537"]
    scores = [m.specificity("money", v).specificity for v in values]
    assert scores == sorted(scores), list(zip(values, scores))


def test_long_alphanumeric_identifiers_score_as_fingerprints(cfg):
    m = model(cfg, corpus_size=0)
    assert m.specificity("btc_wallets", "1a1zp1ep5qgefi2dmptftl5slmv7divfna").specificity > 0.9


def test_currency_prefix_does_not_hide_a_round_number(cfg):
    """'Rs 2,000' and '2000' are the same uninformative amount."""
    m = model(cfg, corpus_size=0)
    assert m.specificity("money", "rs 2,000").specificity < 0.35


@pytest.mark.parametrize("written", ["200", "npr 200", "Rs 200", "rs. 200", "200/-"])
def test_the_currency_unit_adds_no_information(cfg, written):
    """However the unit is written, the amount is worth the same.

    The unit is identical on every amount in the corpus, so counting its
    letters as information made "NPR 200" outrank a bare "200" purely for
    being written with its currency attached.
    """
    m = model(cfg, corpus_size=0)
    bare = m.specificity("money", "200").specificity
    assert m.specificity("money", written).specificity == pytest.approx(bare, abs=0.01)


def test_a_value_starting_with_currency_letters_is_not_truncated(cfg):
    """Stripping the unit must not chew into a real identifier."""
    m = model(cfg, corpus_size=0)
    assert m.specificity("transaction_ids", "rsx99f2k7q1").specificity > 0.6


# --------------------------------------------- the contract, end to end
#
# These pin the *outcome* rather than any constant, so the discount table can
# be retuned freely as long as the conclusion an investigator reads stays right.


@pytest.mark.parametrize("amount", ["2000", "5000", "10000", "500", "100000"])
def test_a_shared_round_amount_alone_is_not_a_relationship(cfg, amount):
    """The reported bug: matching NPR 2,000 does not make two items related."""
    import math

    m = model(cfg, corpus_size=10, frequencies={amount: 2})
    contribution = cfg.correlation_weights["money"] * m.specificity("money", amount).specificity
    confidence = 1.0 - math.exp(-contribution / cfg.correlation_confidence_normaliser)
    assert confidence < cfg.relationship_bands["NO_RELATIONSHIP"], (
        f"a lone shared '{amount}' scored {confidence:.4f} and would be "
        f"reported as a relationship"
    )


def test_an_amount_still_adds_weight_once_a_real_identifier_is_present(cfg):
    """Discounting must not mean ignoring: amounts still corroborate."""
    import math

    m = model(cfg, corpus_size=10, frequencies={"2000": 2, "9812345678": 2})
    phone = cfg.correlation_weights["phones"] * m.specificity("phones", "9812345678").specificity
    amount = cfg.correlation_weights["money"] * m.specificity("money", "2000").specificity
    alone = 1.0 - math.exp(-phone / cfg.correlation_confidence_normaliser)
    together = 1.0 - math.exp(-(phone + amount) / cfg.correlation_confidence_normaliser)
    assert together > alone


# ------------------------------------------------------------- guardrails


def test_specificity_never_reaches_zero(cfg):
    """A ubiquitous value is still a fact worth reporting, just not a link."""
    m = model(cfg, corpus_size=500, frequencies={"2000": 500})
    assert m.specificity("money", "2000").specificity >= cfg.correlation_specificity_floor


def test_disabling_the_model_restores_plain_type_weighting(cfg):
    disabled = InvestigationConfig.from_evidence_config(
        EvidenceConfig(base_dir=cfg.investigation_dir.parent,
                       storage_dir=cfg.investigation_dir.parent / "storage")
    )
    object.__setattr__(disabled, "correlation_specificity_enabled", False)
    m = EntitySpecificityModel(disabled, StubIndex(14, {"2000": 8}))
    assert m.specificity("money", "2000").specificity == 1.0


def test_a_broken_index_does_not_stop_analysis(cfg):
    class Exploding:
        def total_documents(self):
            raise RuntimeError("corpus unavailable")

        def document_frequency(self, *_):
            raise RuntimeError("corpus unavailable")

    m = EntitySpecificityModel(cfg, Exploding())
    score = m.specificity("phones", "9812345678")
    assert 0.0 < score.specificity <= 1.0
