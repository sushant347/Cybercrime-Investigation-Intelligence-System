"""Tests for the Hybrid Character Confusion Resolution upgrade:
confusion matrix, script detection, mixed-script repair, layout awareness."""

from __future__ import annotations

import json

import pytest

from backend.modules.evidence.enhancement.character_confusion import (
    CharacterConfusionResolver,
    ConfusionMatrix,
)
from backend.modules.evidence.enhancement.enhancement_pipeline import (
    EnhancementPipeline,
)
from backend.modules.evidence.enhancement.layout_analyzer import LayoutAnalyzer
from backend.modules.evidence.enhancement.script_detector import ScriptDetector


@pytest.fixture(scope="module")
def resolver() -> CharacterConfusionResolver:
    return CharacterConfusionResolver()


# ------------------------------------------------------------ script detection


@pytest.mark.parametrize(
    "token,expected",
    [
        ("Season", "english"),
        ("धेरै", "nepali"),
        ("Seवson", "mixed_script"),
        ("F८", "mixed_script"),
        ("2026", "numeric"),
        ("!!", "other"),
    ],
)
def test_script_classification(token: str, expected: str) -> None:
    assert ScriptDetector().detect(token) == expected


def test_mixed_profile_reports_minority_positions() -> None:
    profile = ScriptDetector().profile("Seवson")
    assert profile.dominant_script == "english"
    assert [profile.token[i] for i in profile.minority_positions] == ["व"]


# ------------------------------------------------- character confusion repairs


@pytest.mark.parametrize(
    "token,expected",
    [
        ("Nepव", "Nepal"),          # cross-script substitution + vocab snap
        ("Seवson", "Season"),       # cross-script substitution, exact vocab
        ("F८", "FC"),               # Devanagari digit inside initialism
        ("धैरै", "धेरै"),             # matra confusion (via internal pairs)
        ("मं", "म"),                # spurious trailing anusvara
        ("ऋसार्वजनिक", "सार्वजनिक"),  # spurious leading character
    ],
)
def test_real_world_failure_patterns(resolver, token: str, expected: str) -> None:
    candidate = resolver.resolve(token)
    assert candidate is not None, f"no candidate for {token!r}"
    assert candidate.corrected == expected
    assert candidate.replacements  # character replacement is recorded


def test_valid_words_never_touched(resolver) -> None:
    assert resolver.resolve("account") is None
    assert resolver.resolve("बोर्ड") is None
    assert resolver.resolve("Season") is None


def test_unknown_gibberish_never_guessed(resolver) -> None:
    assert resolver.resolve("Xqव9z") is None  # substitution yields no vocab word


def test_matrix_is_editable_json(tmp_path) -> None:
    """New confusions can be added without code changes."""
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps({
        "cross_script": {"क": ["k"]},
        "latin_to_devanagari": {}, "groups": [], "multi_char": {},
        "nepali_internal": [], "spurious": {"leading": [], "trailing": []},
    }, ensure_ascii=False), encoding="utf-8")
    matrix = ConfusionMatrix(path)
    assert matrix.to_dominant("क", "english") == ["k"]


def test_pipeline_applies_confusion_fixes_with_gates() -> None:
    pages = [{"lines": [{"text": "Nepव FC ko Seवson ticket", "confidence": 0.44}]}]
    result = EnhancementPipeline().enhance("Nepव FC ko Seवson ticket", pages)
    assert "Nepal" in result.enhanced_text and "Season" in result.enhanced_text
    stats = result.correction_statistics
    assert stats.character_confusion_corrections >= 2
    assert stats.mixed_script_corrections >= 2
    assert stats.average_confidence_improvement > 0
    replacement_notes = {c.character_replacement for c in result.corrections}
    assert "व→a" in replacement_notes


def test_confusion_fixes_apply_even_at_high_confidence() -> None:
    # A mixed-script token is an unambiguous OCR error, so it is repaired even
    # on a high-confidence line (fuzzy guessing stays blocked elsewhere).
    pages = [{"lines": [{"text": "Seवson ticket now", "confidence": 0.97}]}]
    result = EnhancementPipeline().enhance("Seवson ticket now", pages)
    assert "Season" in result.enhanced_text
    assert "Seवson" not in result.enhanced_text


# --------------------------------------------------------------- layout aware


SCREENSHOT = (
    "10:42  87%  4G\n"
    "Ramesh Sharma\n"
    "online\n"
    "paisa pathaunus hai\n"
    "Today\n"
    "hunchha, kati?\n"
    "Type a message\n"
    "✓✓"
)


def test_ui_lines_separated_from_messages() -> None:
    layout = LayoutAnalyzer().analyze(SCREENSHOT)
    assert "10:42  87%  4G" in layout.ui_text
    assert "Type a message" in layout.ui_text
    assert "✓✓" in layout.ui_text
    assert "online" in layout.ui_text
    assert "paisa pathaunus hai" in layout.message_text
    assert "hunchha, kati?" in layout.message_text
    assert "Type a message" not in layout.message_text


def test_sender_and_timestamp_roles() -> None:
    layout = LayoutAnalyzer().analyze(SCREENSHOT)
    roles = {line.text: line.role for line in layout.lines}
    assert roles["Ramesh Sharma"] == "sender"
    assert roles["Today"] == "timestamp"
    assert roles["paisa pathaunus hai"] == "message"


def test_message_boundaries_never_merged() -> None:
    """UI/timestamp lines between messages keep the messages separate."""
    layout = LayoutAnalyzer().analyze(SCREENSHOT)
    messages = layout.message_text.splitlines()
    assert "paisa pathaunus hai" in messages
    assert "hunchha, kati?" in messages
    assert len(messages) >= 4  # sender + msg + timestamp + msg stay distinct


def test_pipeline_exposes_layout_views_without_modifying_text() -> None:
    pages = [{"lines": [{"text": line, "confidence": 0.95}
                        for line in SCREENSHOT.splitlines()]}]
    result = EnhancementPipeline().enhance(SCREENSHOT, pages)
    assert result.enhanced_text == SCREENSHOT  # views never modify the text
    assert result.ui_text and result.message_text
    assert result.correction_statistics.layout_ui_lines >= 3
    assert any(entry.role == "status_bar" for entry in result.layout)
