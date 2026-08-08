"""Direct unit tests for the engine bridge helpers (no HTTP)."""



def test_engine_health_reports_storage(api):
    from api import engine

    health = engine.engine_health()
    assert health["storage_ok"] is True
    assert "engine_root" in health


def test_engine_health_states_which_optional_capabilities_are_live(api):
    """The two optional capabilities degrade silently; health must not.

    Semantic correction runs XLM-R or a dictionary heuristic, and threat intel
    runs the ML classifier or heuristics. Both are valid, but a forensic
    deployment has to be able to say which one processed its evidence, so the
    mode is reported rather than left to be inferred.
    """
    from api import engine

    health = engine.engine_health()

    assert isinstance(health["semantic_ml_available"], bool)
    # The name must agree with the availability flag, or the report would
    # describe a validator that never ran.
    expected = "xlm-roberta-base" if health["semantic_ml_available"] else "heuristic"
    assert health["semantic_validator"] == expected

    assert isinstance(health["threat_ml_enabled"], bool)
    assert isinstance(health["threat_ml_checkpoint"], bool)


def test_engine_health_never_loads_a_model(api, monkeypatch):
    """Health is called per dashboard request; it must stay cheap.

    Guards against the obvious regression: reaching for
    ``MLThreatIntelProvider.available``, which loads the classifier.
    """
    import importlib

    from api import engine

    loaded: list[str] = []
    real_import = importlib.import_module

    def spy(name, *args, **kwargs):
        loaded.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", spy)
    engine.engine_health()

    assert not any("ml_provider" in name or name == "torch" for name in loaded)


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
    from ciis_timeline_report import pipeline as pipeline_module
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


def test_forensics_backfill_skips_missing_original(monkeypatch, api):
    """Missing evidence must not produce a misleading confidence score."""
    from api import engine

    monkeypatch.setattr(engine, "list_evidence", lambda _case_id: [{
        "case_id": "CASE_0001",
        "evidence_id": "EVID_0001",
        "stored_file_name": "EVID_0001__missing__scan.png",
    }])

    def should_not_run(_evidence_id):
        raise AssertionError("Phase 1 must not run without the stored original")

    monkeypatch.setattr(engine, "_run_forensics", should_not_run)
    result = engine._backfill_forensics("CASE_0001")

    assert result["repaired"] == 0
    assert result["warnings"] == [
        "Original evidence files unavailable for 1 item(s): EVID_0001"
    ]


def test_forensics_backfill_sanitizes_module_failures(monkeypatch, api):
    """Job-facing warnings identify failed modules without leaking local paths."""
    from api import engine

    cfg = engine.evidence_config()
    stored_name = "EVID_0001__hash__scan.png"
    (cfg.originals_dir / stored_name).write_bytes(b"mocked Phase-1 input")
    row = {
        "case_id": "CASE_0001",
        "evidence_id": "EVID_0001",
        "stored_file_name": stored_name,
    }
    monkeypatch.setattr(engine, "list_evidence", lambda _case_id: [row])
    monkeypatch.setattr(
        engine,
        "_run_forensics",
        lambda _evidence_id: {
            "failures": [
                "integrity: Cannot read E:\\private\\scan.png",
                "image_load: Cannot decode E:\\private\\scan.png",
            ]
        },
    )

    result = engine._backfill_forensics("CASE_0001")

    assert result["repaired"] == 0
    assert result["warnings"] == [
        "EVID_0001: Phase-1 warnings in image_load, integrity"
    ]
    assert "private" not in " ".join(result["warnings"])
