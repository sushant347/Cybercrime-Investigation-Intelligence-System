"""Direct unit tests for the engine bridge helpers (no HTTP)."""
import pytest



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


def test_threat_intel_is_available_without_the_ml_stack(api):
    """With the ML flag off there is still a working provider.

    Previously this returned ``None``, which left analysis with only the static
    indicator file - a file that is not shipped - so every case reported
    "threat intelligence unavailable". The chain now always includes the
    rule-based provider, which needs no model, data file or network.
    """
    from django.test import override_settings
    from api import engine

    engine._threat_intel_provider.cache_clear()
    with override_settings(ML_THREAT_INTEL_ENABLED=False):
        provider = engine._threat_intel_provider()
        assert provider is not None
        assert provider.available is True
        assert "heuristics" in provider.source_name
        # And it produces an explained verdict, not just a boolean.
        hit = provider.lookup("https://esewa-cashback-offer.xyz/claim")
        assert hit["verdict"] == "malicious"
        assert hit["reasons"]
    engine._threat_intel_provider.cache_clear()


def test_threat_intel_provider_enabled_loads_or_degrades(api, settings):
    """Enabling the ML flag never raises, whether or not the model loads."""
    from api import engine

    engine._threat_intel_provider.cache_clear()
    settings.ML_THREAT_INTEL_ENABLED = True
    provider = engine._threat_intel_provider()  # must not raise
    assert provider.available is True           # heuristics guarantee this
    engine._threat_intel_provider.cache_clear()


def test_entity_count_helper():
    from api import engine

    class Res:
        def __init__(self, entities):
            self.entities = entities

    summary = {"semantic_results": [Res({"urls": [1, 2], "emails": [3]})]}
    assert engine._entity_count(summary) == 3
    assert engine._entity_count(None) is None


def test_live_timeline_graph_refresh_uses_focused_pipeline(monkeypatch, api):
    from backend.modules.investigation import pipeline as pipeline_module
    from api import engine

    called = []

    class Pipeline:
        def refresh_timeline_graph(self, case_id):
            called.append(case_id)
            return {"timeline": object(), "graph": object()}

    monkeypatch.setattr(pipeline_module, "build_default_pipeline", lambda **_kw: Pipeline())
    monkeypatch.setattr(engine, "_threat_intel_provider", lambda: None)
    result = engine._refresh_timeline_graph("CASE_0001")
    assert result is not None
    assert called == ["CASE_0001"]
