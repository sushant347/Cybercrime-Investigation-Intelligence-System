"""Smoke test: import every module and run basic checks."""
import sys
sys.path.insert(0, ".")

print("=" * 60)
print("IMPORT TESTS")
print("=" * 60)

modules_ok = 0
modules_fail = 0

def test_import(name, import_fn):
    global modules_ok, modules_fail
    try:
        import_fn()
        print(f"  [OK] {name}")
        modules_ok += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        modules_fail += 1

# Foundation
test_import("config.settings", lambda: __import__("src.config.settings", fromlist=["get_settings"]))
test_import("utils.logger", lambda: __import__("src.utils.logger", fromlist=["get_logger"]))
test_import("utils.exceptions", lambda: __import__("src.utils.exceptions", fromlist=["PhishingEngineError"]))
test_import("utils.helpers", lambda: __import__("src.utils.helpers", fromlist=["normalize_url"]))

# Parser
test_import("parser.url_validator", lambda: __import__("src.parser.url_validator", fromlist=["URLValidator"]))
test_import("parser.url_parser", lambda: __import__("src.parser.url_parser", fromlist=["URLParser"]))

# Feature Engineering
test_import("feature_engineering.base", lambda: __import__("src.feature_engineering.base", fromlist=["BaseFeatureExtractor"]))
test_import("feature_engineering.length_features", lambda: __import__("src.feature_engineering.length_features", fromlist=["LengthFeatureExtractor"]))
test_import("feature_engineering.entropy_features", lambda: __import__("src.feature_engineering.entropy_features", fromlist=["EntropyFeatureExtractor"]))
test_import("feature_engineering.character_features", lambda: __import__("src.feature_engineering.character_features", fromlist=["CharacterFeatureExtractor"]))
test_import("feature_engineering.structural_features", lambda: __import__("src.feature_engineering.structural_features", fromlist=["StructuralFeatureExtractor"]))
test_import("feature_engineering.lexical_features", lambda: __import__("src.feature_engineering.lexical_features", fromlist=["LexicalFeatureExtractor"]))
test_import("feature_engineering.brand_features", lambda: __import__("src.feature_engineering.brand_features", fromlist=["BrandFeatureExtractor"]))
test_import("feature_engineering.security_features", lambda: __import__("src.feature_engineering.security_features", fromlist=["SecurityFeatureExtractor"]))
test_import("feature_engineering.tld_features", lambda: __import__("src.feature_engineering.tld_features", fromlist=["TLDFeatureExtractor"]))
test_import("feature_engineering.pipeline", lambda: __import__("src.feature_engineering.pipeline", fromlist=["FeaturePipeline"]))

# Datasets
test_import("datasets.loader", lambda: __import__("src.datasets.loader", fromlist=["DatasetLoader"]))
test_import("datasets.cleaner", lambda: __import__("src.datasets.cleaner", fromlist=["DatasetCleaner"]))
test_import("datasets.validator", lambda: __import__("src.datasets.validator", fromlist=["DatasetValidator"]))
test_import("datasets.merger", lambda: __import__("src.datasets.merger", fromlist=["DatasetMerger"]))
test_import("datasets.statistics", lambda: __import__("src.datasets.statistics", fromlist=["DatasetStatistics"]))

# Models
test_import("models.base_model", lambda: __import__("src.models.base_model", fromlist=["BaseModel"]))
test_import("models.baseline_models", lambda: __import__("src.models.baseline_models", fromlist=["create_baseline_model"]))
test_import("models.transformer_models", lambda: __import__("src.models.transformer_models", fromlist=["TransformerURLClassifier"]))

# Training
test_import("training.baseline_trainer", lambda: __import__("src.training.baseline_trainer", fromlist=["BaselineTrainer"]))
test_import("training.transformer_trainer", lambda: __import__("src.training.transformer_trainer", fromlist=["TransformerTrainer"]))

# Evaluation
test_import("evaluation.evaluator", lambda: __import__("src.evaluation.evaluator", fromlist=["ModelEvaluator"]))

# Preprocessing
test_import("preprocessing.text_preprocessor", lambda: __import__("src.preprocessing.text_preprocessor", fromlist=["URLTextPreprocessor"]))

# Intelligence
test_import("intelligence.base_connector", lambda: __import__("src.intelligence.base_connector", fromlist=["BaseConnector"]))
test_import("intelligence.virustotal", lambda: __import__("src.intelligence.virustotal", fromlist=["VirusTotalConnector"]))
test_import("intelligence.whois_connector", lambda: __import__("src.intelligence.whois_connector", fromlist=["WhoisConnector"]))
test_import("intelligence.dns_connector", lambda: __import__("src.intelligence.dns_connector", fromlist=["DNSConnector"]))
test_import("intelligence.ssl_connector", lambda: __import__("src.intelligence.ssl_connector", fromlist=["SSLConnector"]))
test_import("intelligence.geoip_connector", lambda: __import__("src.intelligence.geoip_connector", fromlist=["GeoIPConnector"]))
test_import("intelligence.aggregator", lambda: __import__("src.intelligence.aggregator", fromlist=["IntelligenceAggregator"]))

# Scoring
test_import("scoring.threat_scorer", lambda: __import__("src.scoring.threat_scorer", fromlist=["ThreatScorer"]))

# Explainability
test_import("explainability.reason_generator", lambda: __import__("src.explainability.reason_generator", fromlist=["ReasonGenerator"]))

# Prediction
test_import("prediction.result", lambda: __import__("src.prediction.result", fromlist=["PredictionResult"]))
test_import("prediction.predictor", lambda: __import__("src.prediction.predictor", fromlist=["PhishingPredictor"]))

print()
print(f"Results: {modules_ok} OK, {modules_fail} FAILED out of {modules_ok + modules_fail}")
