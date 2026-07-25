"""Entity-preservation metric (Table 6.1, 3rd column)."""

from backend.modules.evidence.evaluation.ocr_metrics import entity_preservation_rate


def test_all_preserved():
    gold = ["9812345678", "http://scam.top/login", "OTP 4521"]
    text = "call 9812345678 at http://scam.top/login enter otp 4521 now"
    result = entity_preservation_rate(gold, text)
    assert result["rate"] == 1.0
    assert result["preserved"] == 3
    assert result["missing"] == []


def test_dropped_digit_counts_as_missing():
    # OCR dropped a digit of the wallet id -> the entity did NOT survive verbatim.
    gold = ["9812345678"]
    text = "send to 981234567"  # one digit short
    result = entity_preservation_rate(gold, text)
    assert result["rate"] == 0.0
    assert result["missing"] == ["9812345678"]


def test_case_insensitive_by_default():
    assert entity_preservation_rate(["Esewa"], "pay via esewa")["rate"] == 1.0
    assert entity_preservation_rate(["Esewa"], "pay via esewa",
                                    case_insensitive=False)["rate"] == 0.0


def test_empty_gold_is_zero_not_error():
    assert entity_preservation_rate([], "anything")["rate"] == 0.0
