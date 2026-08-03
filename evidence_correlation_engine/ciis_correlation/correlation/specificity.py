"""How *identifying* one concrete entity value is (Module 1 scoring input).

The correlation engine used to weight a shared entity purely by its type: any
two items sharing an ``money`` value scored the same, so "both mention NPR
2,000" - the single most common amount in a scam corpus - produced the same
factor as "both mention NPR 17,432.55". Type weight answers "how identifying
is this *kind* of thing"; it cannot answer "how identifying is *this value*".
That is the question this module answers.

Two independent estimates are combined.

**Corpus rarity (learned, unsupervised).** Straight inverse document frequency
over the case corpus: a value carried by 8 of 14 evidence items tells you
almost nothing about a link between two of them, while a value carried by
exactly the two items being compared is close to a fingerprint. This is learned
from ``entities.csv`` and needs no labels, which matters because nobody has
ground truth for "these two items are genuinely related".

**Intrinsic information (prior).** How much information the string itself
carries: its length and character diversity in bits, discounted for round
numbers. A fresh deployment has no corpus to learn from, and even a large one
has never seen a brand-new scammer wallet - the prior is what stops a
first-sighting round number scoring as a fingerprint.

They are combined as a weighted geometric mean whose weight is how much corpus
there is to trust (a log-linear opinion pool). With a large corpus the
evidence dominates; with a small one the prior does. A geometric mean also
means *both* must be high to call a value identifying, which is the
conservative direction for a forensic tool: it costs a little sensitivity and
buys a lot of precision, and a false link between two cases is far more
expensive than a missed weak one.

No supervised model is used anywhere here, deliberately - see the module
README section in ``service.py``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

# Values that are pure digits are scored against a decimal alphabet, mixed
# alphanumerics against a much larger one - 10 digits of phone number carry
# far less information than 34 characters of wallet address.
_DIGITS = re.compile(r"^\d+$")
_DECIMAL = re.compile(r"^\d+(?:[.,]\d+)?$")
_NON_ALNUM = re.compile(r"[^a-z0-9]")
#: Currency markers carry no identifying information - every amount in a
#: Nepali corpus is prefixed the same way - so they are removed before the
#: value's information content is measured.
_CURRENCY_PREFIX = re.compile(r"^\s*(?:npr|nrs|rs|inr|usd|eur|gbp|[$€£₹])\.?\s*",
                              re.IGNORECASE)
_CURRENCY_SUFFIX = re.compile(r"\s*(?:npr|nrs|rs|inr|usd|eur|gbp|/-|only)\.?\s*$",
                              re.IGNORECASE)


@dataclass(frozen=True)
class ValueSpecificity:
    """Why one shared value was, or was not, treated as identifying."""

    entity_type: str
    value: str
    #: Final multiplier applied to the entity type's weight, in [floor, 1].
    specificity: float
    #: Distinct evidence items in the corpus carrying this value.
    document_frequency: int
    #: Distinct evidence items in the corpus overall.
    corpus_size: int
    rarity: float
    intrinsic: float
    #: How much the corpus estimate was trusted against the prior, in [0, 1].
    corpus_trust: float
    reason: str = ""

    @property
    def is_common(self) -> bool:
        """True when the corpus says this value is too widespread to identify."""
        return self.corpus_size > 2 and self.document_frequency > 2 and self.rarity < 0.5


class EntitySpecificityModel:
    """Scores how identifying each entity value is, learned from the corpus.

    ``index`` is any object exposing ``document_frequency(type, value)`` and
    ``total_documents()`` - in production the :class:`CrossCaseEntityIndex`,
    which already holds every entity occurrence in memory. Results are memoised
    per instance because a case analysis asks about the same handful of values
    once per evidence pair.
    """

    def __init__(self, config, index=None) -> None:
        self._cfg = config
        self._index = index
        self._cache: Dict[str, ValueSpecificity] = {}

    # ------------------------------------------------------------------ public

    def specificity(self, entity_type: str, value: str) -> ValueSpecificity:
        key = f"{entity_type}\x1f{value}"
        hit = self._cache.get(key)
        if hit is None:
            hit = self._compute(entity_type, value)
            self._cache[key] = hit
        return hit

    def multiplier(self, entity_type: str, value: str) -> float:
        """Just the number, for callers that do not need the explanation."""
        return self.specificity(entity_type, value).specificity

    # ----------------------------------------------------------------- scoring

    def _compute(self, entity_type: str, value: str) -> ValueSpecificity:
        cfg = self._cfg
        normalized = (value or "").strip().lower()

        if not getattr(cfg, "correlation_specificity_enabled", True) or not normalized:
            return ValueSpecificity(
                entity_type=entity_type, value=normalized, specificity=1.0,
                document_frequency=0, corpus_size=0, rarity=1.0, intrinsic=1.0,
                corpus_trust=0.0, reason="value-level specificity disabled",
            )

        corpus_size, document_frequency = self._corpus_counts(entity_type, normalized)
        rarity = self._rarity(corpus_size, document_frequency)
        intrinsic = self._intrinsic(entity_type, normalized)
        trust = self._corpus_trust(corpus_size)

        # Weighted geometric mean; both terms are strictly positive.
        floor = float(getattr(cfg, "correlation_specificity_floor", 0.02))
        blended = math.exp(
            trust * math.log(max(rarity, 1e-6))
            + (1.0 - trust) * math.log(max(intrinsic, 1e-6))
        )
        specificity = max(floor, min(1.0, blended))

        return ValueSpecificity(
            entity_type=entity_type,
            value=normalized,
            specificity=round(specificity, 4),
            document_frequency=document_frequency,
            corpus_size=corpus_size,
            rarity=round(rarity, 4),
            intrinsic=round(intrinsic, 4),
            corpus_trust=round(trust, 4),
            reason=self._reason(normalized, corpus_size, document_frequency,
                                specificity, rarity, intrinsic, trust),
        )

    def _corpus_counts(self, entity_type: str, normalized: str):
        """(corpus size, document frequency), or (0, 0) with no index."""
        if self._index is None:
            return 0, 0
        try:
            total = int(self._index.total_documents())
            df = int(self._index.document_frequency(entity_type, normalized))
        except Exception:  # noqa: BLE001 - a stats failure must not stop analysis
            return 0, 0
        return max(0, total), max(0, df)

    @staticmethod
    def _rarity(corpus_size: int, document_frequency: int) -> float:
        """Inverse document frequency, normalised so df=2 scores 1.0.

        Two items sharing a value means df is at least 2, so that is the
        rarest a *shared* value can be and therefore the top of the scale.
        A value in every item scores near zero.
        """
        if corpus_size < 3 or document_frequency <= 0:
            return 1.0  # nothing to learn from yet; the prior carries the score
        df = min(document_frequency, corpus_size)
        best = math.log1p(corpus_size / 2.0)
        if best <= 0:
            return 1.0
        return max(0.0, min(1.0, math.log1p(corpus_size / df) / best))

    def _corpus_trust(self, corpus_size: int) -> float:
        """How far to trust the corpus estimate over the prior, in [0, 1]."""
        k = float(getattr(self._cfg, "correlation_corpus_prior_strength", 12.0))
        if corpus_size <= 0:
            return 0.0
        return corpus_size / (corpus_size + max(k, 1e-6))

    def _intrinsic(self, entity_type: str, normalized: str) -> float:
        """Information carried by the string itself, in [0, 1].

        Shannon-style: length times the bits per symbol of the alphabet the
        value is drawn from, scaled against the point where a value is long
        and varied enough to be treated as a unique identifier.
        """
        # Measure the part that varies. A currency marker is the same on every
        # amount in the corpus, so counting "npr" as three alphanumeric symbols
        # credits ~15 bits to a value that carries none - enough to lift
        # "NPR 200" above a bare "200" purely because it was written with its
        # unit attached.
        payload = self._payload(normalized)
        if not payload:
            return 0.05

        alphabet = self._alphabet_size(payload)
        bits = len(payload) * math.log2(alphabet)
        full = float(getattr(self._cfg, "correlation_intrinsic_bits_full", 40.0))
        score = min(1.0, bits / max(full, 1.0))

        score *= self._roundness_discount(entity_type, normalized)
        return max(0.01, min(1.0, score))

    @staticmethod
    def _payload(normalized: str) -> str:
        """The information-bearing part: alphanumerics minus any currency unit."""
        numeric = _CURRENCY_PREFIX.sub("", normalized).strip()
        numeric = _CURRENCY_SUFFIX.sub("", numeric).strip()
        candidate = _NON_ALNUM.sub("", numeric)
        # Only treat it as an amount when what remains is purely numeric;
        # otherwise the original string was never a currency value.
        if candidate and _DIGITS.match(candidate):
            return candidate
        return _NON_ALNUM.sub("", normalized)

    @staticmethod
    def _alphabet_size(stripped: str) -> int:
        has_digit = any(c.isdigit() for c in stripped)
        has_alpha = any(c.isalpha() for c in stripped)
        if has_digit and has_alpha:
            return 36
        if has_alpha:
            return 26
        return 10

    @staticmethod
    def _roundness_discount(entity_type: str, normalized: str) -> float:
        """Round numbers are the values a scam corpus repeats endlessly.

        "2,000" is not 4 digits of evidence - it is one of a few dozen amounts
        that appear in most cases. Applied to any numeric value, because a
        round figure is equally uninformative whether the extractor filed it
        under money, a transaction id or an account number.
        """
        # Strip the currency marker as a whole token. A character-class strip
        # would also eat the leading digits of values like "5rs" or chew into
        # any value that happens to start with one of those letters.
        candidate = _CURRENCY_PREFIX.sub("", normalized)
        candidate = _CURRENCY_SUFFIX.sub("", candidate)
        candidate = candidate.replace(",", "").replace(" ", "").strip()
        if not _DECIMAL.match(candidate):
            return 1.0
        try:
            number = float(candidate)
        except ValueError:
            return 1.0
        if number <= 0:
            return 0.4
        if not float(number).is_integer():
            return 1.0  # a value with decimals is already distinctive
        integral = int(number)
        # Calibrated so that a shared round amount on its own cannot reach the
        # NO_RELATIONSHIP threshold: two items both mentioning "Rs 2,000" are
        # not related, and saying "weak relationship" is simply wrong. The
        # scale stays graded, so a less round figure keeps proportionally more
        # of its weight, and any amount still counts once something genuinely
        # identifying is present alongside it.
        if integral % 100000 == 0:
            return 0.10
        if integral % 10000 == 0:
            return 0.15
        if integral % 1000 == 0:
            return 0.20
        if integral % 100 == 0:
            return 0.40
        if integral % 10 == 0:
            return 0.70
        return 1.0

    @staticmethod
    def _reason(value: str, corpus_size: int, document_frequency: int,
                specificity: float, rarity: float, intrinsic: float,
                trust: float) -> str:
        if corpus_size >= 3 and document_frequency > 0:
            seen = (f"seen in {document_frequency} of {corpus_size} evidence "
                    f"items in the corpus")
            if rarity >= 0.85:
                verdict = "distinctive"
            elif rarity >= 0.5:
                verdict = "moderately common"
            else:
                verdict = "common - heavily discounted"
            return (f"'{value}' is {verdict} ({seen}); "
                    f"specificity {specificity:.2f}")
        return (
            f"'{value}' scored on its own information content "
            f"({intrinsic:.2f}) because the corpus is too small to judge "
            f"rarity yet; specificity {specificity:.2f}"
        )


@dataclass
class SpecificityStats:
    """Aggregate view used in explanations and audit lines."""

    counted: int = 0
    discounted: int = 0
    detail: Dict[str, float] = field(default_factory=dict)

    def add(self, score: ValueSpecificity) -> None:
        self.counted += 1
        if score.is_common:
            self.discounted += 1
        self.detail[score.value] = score.specificity


def build_model(config, index=None) -> Optional[EntitySpecificityModel]:
    """Factory kept separate so callers need not import the class directly."""
    return EntitySpecificityModel(config, index)
