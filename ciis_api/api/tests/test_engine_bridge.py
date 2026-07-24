"""Direct unit tests for the engine bridge helpers (no HTTP)."""
import pytest

pytestmark = pytest.mark.django_db


def test_engine_health_reports_storage(api):
    from api import engine

    health = engine.engine_health()
    assert health["storage_ok"] is True
    assert "engine_root" in health


def test_enrich_disabled_flag(monkeypatch, api):
    """ENGINE_RUN_FULL_PIPELINE=0 => enrichment is skipped (OCR-only)."""
    from django.test import override_settings
    from api import engine

    with override_settings(ENGINE_RUN_FULL_PIPELINE=False):
        assert engine._enrich_evidence("CASE_0001") is None


def test_enrich_failure_is_isolated(monkeypatch, api):
    """A crash in the orchestrator must not propagate out of _enrich_evidence."""
    from api import engine

    class Boom:
        def process_case(self, case_id):
            raise RuntimeError("kaboom")

    monkeypatch.setattr(engine, "_evidence_orchestrator", lambda: Boom())
    # Returns None instead of raising: the OCR result is preserved.
    assert engine._enrich_evidence("CASE_0001") is None


def test_threat_intel_provider_disabled_by_default(api):
    """With the ML flag off, analysis uses the static intel (provider is None)."""
    from django.test import override_settings
    from api import engine

    engine._threat_intel_provider.cache_clear()
    with override_settings(ML_THREAT_INTEL_ENABLED=False):
        assert engine._threat_intel_provider() is None
    engine._threat_intel_provider.cache_clear()


def test_threat_intel_provider_enabled_loads_or_degrades(api, settings):
    """Enabling the flag returns an available ML provider, or None if the ML
    system/deps are absent (graceful degradation) — never raises."""
    from api import engine

    engine._threat_intel_provider.cache_clear()
    settings.ML_THREAT_INTEL_ENABLED = True
    provider = engine._threat_intel_provider()  # must not raise
    if provider is not None:
        assert provider.available is True
    engine._threat_intel_provider.cache_clear()


def test_entity_count_helper():
    from api import engine

    class Res:
        def __init__(self, entities):
            self.entities = entities

    summary = {"semantic_results": [Res({"urls": [1, 2], "emails": [3]})]}
    assert engine._entity_count(summary) == 3
    assert engine._entity_count(None) is None
