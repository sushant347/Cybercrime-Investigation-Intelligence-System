"""
Unified phishing URL predictor -- the main entry point for the engine.

Orchestrates URL validation, parsing, feature extraction, rule-based
pre-screening, model inference, threat intelligence gathering, threat
scoring, and reason generation to produce a complete PredictionResult.

New in v2.0
-----------
* :class:`~src.rules.rule_engine.RuleEngine` pre-screens every URL with
  15 deterministic rules before the ML model is consulted.
* :class:`~src.parser.url_resolver.URLResolver` transparently follows
  redirects for URLs served by known URL-shortening services.
* Rule findings are merged into the ``reasons`` list and embedded in
  ``PredictionResult.metadata`` for downstream consumers.
"""

from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.config.settings import get_settings
from src.parser.url_validator import URLValidator
from src.parser.url_parser import URLParser
from src.feature_engineering.pipeline import FeaturePipeline
from src.prediction.result import PredictionResult
from src.utils.exceptions import PhishingEngineError, ModelError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PhishingPredictor:
    """
    Main entry point for phishing URL detection.

    Combines all engine components into a single, easy-to-use interface.
    Given a URL, produces a complete PredictionResult containing the AI
    prediction, confidence, threat score, intelligence data, and
    human-readable reasons.

    This class is designed to be imported and used by other CIIE modules.

    Example:
        >>> predictor = PhishingPredictor(model_type="xgboost")
        >>> result = predictor.predict("https://paypal-login-security.xyz/login")
        >>> print(result.to_json(indent=2))
        >>> print(result.summary())

    Attributes:
        model_type: The ML model type being used for predictions.
        use_intelligence: Whether to gather external threat intelligence.
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        checkpoint_dir: Path | None = None,
        use_intelligence: bool = True,
        intelligence_timeout: int = 10,
        use_rules: bool = True,
        resolve_shorteners: bool = True,
        use_transformer: bool = True,
        use_ensemble: bool = True,
    ) -> None:
        """
        Initialize the phishing URL predictor.

        Args:
            model_type: Model to use for predictions. Options:
                Baseline: 'logistic_regression', 'random_forest', 'decision_tree',
                          'extra_trees', 'naive_bayes', 'svm', 'xgboost', 'lightgbm'.
                Transformer: 'distilbert', 'bert', 'roberta'.
            checkpoint_dir: Directory containing saved model checkpoints.
                If None, uses settings default.
            use_intelligence: Whether to query external threat intelligence
                sources (VirusTotal, WHOIS, DNS, SSL, GeoIP).
            intelligence_timeout: Timeout in seconds for intelligence queries.
            use_rules: Whether to run the deterministic rule engine as a
                pre-screening step before the ML model.
            resolve_shorteners: Whether to follow redirects for URLs served
                by known URL-shortening services before analysis.
            use_transformer: Whether to run the optional URL transformer
                (Phase 3-A) when torch and a checkpoint are available.
            use_ensemble: Whether the Ensemble Engine (Phase 3-B) makes the
                final decision. Set False for the legacy Phase 2 path.
        """
        settings = get_settings()
        self.model_type = model_type
        self.use_intelligence = use_intelligence
        self.use_rules = use_rules
        self.resolve_shorteners = resolve_shorteners
        self.use_transformer = use_transformer
        self.use_ensemble = use_ensemble
        self._checkpoint_dir = Path(checkpoint_dir or settings.paths.checkpoint_dir)

        # Initialize components
        self._validator = URLValidator()
        self._parser = URLParser()
        self._feature_pipeline = FeaturePipeline()

        # Lazy-loaded components
        self._model = None
        self._is_transformer = model_type in ("distilbert", "bert", "roberta", "mbert", "xlm-roberta")

        # Intelligence components (lazy)
        self._intelligence_aggregator = None
        self._threat_scorer = None
        self._reason_generator = None

        # Rule engine and URL resolver (lazy)
        self._rule_engine = None
        self._url_resolver = None

        # Phase 3 components (lazy)
        self._transformer_model = None
        self._transformer_load_attempted = False
        self._ensemble_engine = None
        self._shap_explainer = None
        self._shap_load_attempted = False

        logger.info(
            "PhishingPredictor initialized -- model=%s, intelligence=%s, "
            "rules=%s, resolve_shorteners=%s",
            model_type, use_intelligence, use_rules, resolve_shorteners,
        )

    def _load_model(self) -> None:
        """Lazily load the ML model from checkpoint."""
        if self._model is not None:
            return

        try:
            if self._is_transformer:
                from src.models.transformer_models import create_transformer_model
                self._model = create_transformer_model(self.model_type)
                checkpoint_path = self._checkpoint_dir / f"transformer_{self.model_type}"
                if checkpoint_path.exists():
                    self._model.load(checkpoint_path)
                    logger.info("Loaded transformer model from %s", checkpoint_path)
                else:
                    logger.warning(
                        "No transformer checkpoint found at %s. "
                        "Model must be trained before prediction.",
                        checkpoint_path,
                    )
            else:
                from src.models.baseline_models import create_baseline_model
                self._model = create_baseline_model(self.model_type)
                checkpoint_path = self._checkpoint_dir / f"{self.model_type}.pkl"
                if checkpoint_path.exists():
                    self._model.load(checkpoint_path)
                    logger.info("Loaded baseline model from %s", checkpoint_path)
                else:
                    logger.warning(
                        "No baseline checkpoint found at %s. "
                        "Model must be trained before prediction.",
                        checkpoint_path,
                    )
        except Exception as e:
            raise ModelError(self.model_type, "load", str(e)) from e

    def _load_intelligence(self) -> None:
        """Lazily load intelligence components."""
        if self._intelligence_aggregator is not None:
            return

        try:
            from src.intelligence.aggregator import IntelligenceAggregator
            from src.scoring.threat_scorer import ThreatScorer
            from src.explainability.reason_generator import ReasonGenerator

            self._intelligence_aggregator = IntelligenceAggregator()
            self._threat_scorer = ThreatScorer()
            self._reason_generator = ReasonGenerator()
        except Exception as e:
            logger.warning("Failed to load intelligence components: %s", e)
            self._intelligence_aggregator = None
            self._threat_scorer = None
            self._reason_generator = None

    def _load_rules(self) -> None:
        """Lazily load the deterministic rule engine."""
        if self._rule_engine is not None:
            return
        try:
            from src.rules.rule_engine import RuleEngine
            self._rule_engine = RuleEngine()
        except Exception as e:
            logger.warning("Failed to load rule engine: %s", e)
            self._rule_engine = None

    def _load_resolver(self) -> None:
        """Lazily load the URL shortener resolver."""
        if self._url_resolver is not None:
            return
        try:
            from src.parser.url_resolver import URLResolver
            self._url_resolver = URLResolver()
        except Exception as e:
            logger.warning("Failed to load URL resolver: %s", e)
            self._url_resolver = None

    def _load_transformer(self) -> None:
        """Lazily load the URL transformer (Phase 3-A, optional).

        Degrades gracefully: when PyTorch or the checkpoint is missing the
        transformer stays ``None`` and the engine works without it.
        """
        if self._transformer_load_attempted:
            return
        self._transformer_load_attempted = True
        try:
            from src.models.url_transformer import load_url_transformer_if_available
            self._transformer_model = load_url_transformer_if_available(
                self._checkpoint_dir
            )
            if self._transformer_model is not None:
                logger.info("URL transformer loaded for ensemble prediction.")
        except Exception as e:
            logger.warning("Failed to load URL transformer: %s", e)
            self._transformer_model = None

    def _load_ensemble(self) -> None:
        """Lazily load the ensemble engine (Phase 3-B)."""
        if self._ensemble_engine is not None:
            return
        try:
            from src.ensemble.ensemble_engine import EnsembleEngine
            self._ensemble_engine = EnsembleEngine()
        except Exception as e:
            logger.warning("Failed to load ensemble engine: %s", e)
            self._ensemble_engine = None

    def _load_shap(self) -> None:
        """Lazily build the SHAP explainer for the XGBoost model (Phase 3-C)."""
        if self._shap_load_attempted:
            return
        self._shap_load_attempted = True
        try:
            if self._is_transformer:
                return
            self._load_model()
            if self._model is None or not self._model.is_trained:
                return
            from src.explainability.shap_explainer import SHAPExplainer
            self._shap_explainer = SHAPExplainer(
                self._model, self._feature_pipeline.get_feature_names()
            )
        except Exception as e:
            logger.warning("Failed to initialise SHAP explainer: %s", e)
            self._shap_explainer = None

    def predict(self, url: str, diagnostics: bool = False) -> PredictionResult:
        """
        Analyze a URL and produce a complete phishing detection result.

        This is the primary method for the engine. It performs:
        1. URL validation and parsing.
        2. Feature extraction (~50 features).
        3. ML model inference (prediction + confidence).
        4. Threat intelligence gathering (if enabled).
        5. Composite threat scoring.
        6. Human-readable reason generation.

        Args:
            url: The URL to analyze.
            diagnostics: Optional flag to print diagnostics info to stdout.

        Returns:
            PredictionResult with prediction, confidence, risk score,
            features, intelligence, and reasons.
        """
        logger.info("Analyzing URL: %s", url)

        # Always load scorer and reason generator to compute trust scores and flags
        self._load_intelligence()

        # --- Step 0: Resolve URL shorteners (if enabled) ---------------
        original_url = url
        resolution_metadata: dict[str, Any] = {}
        if self.resolve_shorteners:
            try:
                self._load_resolver()
                if self._url_resolver is not None:
                    resolution = self._url_resolver.resolve(url)
                    if resolution.was_resolved:
                        logger.info(
                            "Expanded shortened URL: %s → %s",
                            url[:50],
                            resolution.resolved_url[:50],
                        )
                        url = resolution.resolved_url
                        resolution_metadata = resolution.to_dict()
            except Exception as e:
                logger.warning("URL resolution failed: %s", e)

        # --- Step 1: Validate URL ---------------------------------------
        validation = self._validator.validate(url)
        if not validation.is_valid:
            logger.warning("URL validation failed: %s", validation.validation_errors)
            return PredictionResult(
                url=original_url,
                prediction="unknown",
                confidence=0.0,
                risk_score=0,
                risk_level="Unknown",
                reasons=[f"Invalid URL: {'; '.join(validation.validation_errors)}"],
                model_type=self.model_type,
                metadata={"original_url": original_url},
            )

        # --- Step 2: Parse URL ------------------------------------------
        parsed = self._parser.parse(validation.normalized_url)

        # --- Step 3: Extract features -----------------------------------
        try:
            features = self._feature_pipeline.extract(url)
        except Exception as e:
            logger.error("Feature extraction failed: %s", e)
            features = {}

        # --- Step 3b: Rule engine pre-screening ------------------------
        rule_result_data: dict[str, Any] = {}
        rule_reasons: list[str] = []
        rule_is_definite = False

        if self.use_rules:
            try:
                self._load_rules()
                if self._rule_engine is not None:
                    rule_result = self._rule_engine.evaluate(parsed, features)
                    rule_result_data = rule_result.to_dict()
                    rule_is_definite = rule_result.is_definite_phishing
                    # Collect rule-generated reasons
                    rule_reasons = [
                        f.description
                        for f in rule_result.findings
                        if f.severity in ("critical", "high")
                    ]
                    if rule_is_definite:
                        logger.info(
                            "Rule engine flagged URL as DEFINITE PHISHING: %s",
                            url[:60],
                        )
            except Exception as e:
                logger.warning("Rule engine evaluation failed: %s", e)

        # --- Step 4: Model prediction -----------------------------------
        prediction_label = "unknown"
        confidence = 0.0
        
        # Output verification fields
        raw_prob_val = 0.0
        cal_prob_val = 0.0
        pred_class_val = 0
        decision_threshold_val = 0.5

        # If a critical rule fired, we can short-circuit with high confidence
        if rule_is_definite:
            prediction_label = "phishing"
            confidence = 0.97
            raw_prob_val = 0.97
            cal_prob_val = 0.97
            pred_class_val = 1
            logger.info("Skipping ML model — rule engine returned definite phishing.")
        else:
            try:
                self._load_model()

                if self._model is not None and self._model.is_trained:
                    if self._is_transformer:
                        # Transformer takes raw URL strings
                        proba = self._model.predict_proba(np.array([url]))
                        pred = self._model.predict(np.array([url]))
                        raw_prob_val = float(proba[0]) if len(proba) > 0 else 0.0
                        cal_prob_val = raw_prob_val
                        pred_class_val = int(pred[0])
                    else:
                        # Baseline takes feature vectors
                        feature_names = self._feature_pipeline.get_feature_names()
                        
                        # Safe float helper
                        def safe_float(val: Any) -> float:
                            if val is None or (isinstance(val, float) and np.isnan(val)):
                                return 0.0
                            try:
                                return float(val)
                            except (ValueError, TypeError):
                                return 0.0
                                
                        feature_values = [safe_float(features.get(f)) for f in feature_names]
                        
                        # Log model input (verbose -- DEBUG level only)
                        logger.debug("Model input: %d features", len(feature_names))
                        logger.debug("Feature names: %s", feature_names)
                        logger.debug("Feature values: %s", feature_values)

                        # Expected features check
                        expected_features = self._model.metadata.feature_names

                        # Print Feature Comparison Table (diagnostics mode only)
                        if diagnostics:
                            print("\n" + "=" * 80)
                            print("FEATURE COMPARISON TABLE")
                            print("=" * 80)
                            print(f"{'Feature Name':<40} | {'Value':<10} | {'Expected Name':<30} | {'Match?':<6}")
                            print("-" * 80)
                            for idx, f in enumerate(feature_names):
                                exp_name = expected_features[idx] if expected_features and idx < len(expected_features) else "N/A"
                                match_str = "Yes" if not expected_features or f == exp_name else "NO"
                                print(f"{f[:40]:<40} | {safe_float(features.get(f)):<10.4f} | {exp_name[:30]:<30} | {match_str:<6}")
                            print("=" * 80 + "\n")

                        if expected_features:
                            if len(expected_features) != len(feature_names):
                                raise ModelError(
                                    self.model_type, "prediction",
                                    f"Feature count mismatch: model expects {len(expected_features)}, pipeline outputs {len(feature_names)}"
                                )
                            if expected_features != feature_names:
                                mismatch = []
                                for idx, (exp, cur) in enumerate(zip(expected_features, feature_names)):
                                    if exp != cur:
                                        mismatch.append(f"Index {idx}: expected '{exp}', got '{cur}'")
                                raise ModelError(
                                    self.model_type, "prediction",
                                    f"Feature mismatch or ordering error:\n" + "\n".join(mismatch)
                                )
                        
                        feature_vector = np.array([feature_values])
                        
                        # Generate raw prediction
                        if hasattr(self._model, "predict_proba_raw"):
                            proba_raw = self._model.predict_proba_raw(feature_vector)
                        else:
                            proba_raw = self._model.predict_proba(feature_vector)
                            
                        # Generate calibrated prediction
                        proba_cal = self._model.predict_proba(feature_vector)
                        pred = self._model.predict(feature_vector)
                        
                        raw_prob_val = float(proba_raw[0]) if len(proba_raw) > 0 else 0.0
                        cal_prob_val = float(proba_cal[0]) if len(proba_cal) > 0 else 0.0
                        pred_class_val = int(pred[0])

                    confidence = raw_prob_val
                    prediction_label = "phishing" if pred_class_val == 1 else "legitimate"
                    
                    logger.debug(
                        "Model output: raw_prob=%.6f cal_prob=%.6f class=%s(%d) threshold=%.4f",
                        raw_prob_val, cal_prob_val, prediction_label.upper(),
                        pred_class_val, decision_threshold_val,
                    )
                else:
                    logger.warning("Model not trained -- using feature-based heuristic")
                    prediction_label, confidence = self._heuristic_predict(features)
                    raw_prob_val = confidence if prediction_label == "phishing" else 1.0 - confidence
                    cal_prob_val = raw_prob_val
                    pred_class_val = 1 if prediction_label == "phishing" else 0

            except Exception as e:
                logger.warning("Model prediction failed: %s. Falling back to heuristic.", e)
                prediction_label, confidence = self._heuristic_predict(features)
                raw_prob_val = confidence if prediction_label == "phishing" else 1.0 - confidence
                cal_prob_val = raw_prob_val
                pred_class_val = 1 if prediction_label == "phishing" else 0

        # Step 5: Threat intelligence
        intelligence_data: dict[str, Any] = {}
        if self.use_intelligence:
            try:
                self._load_intelligence()
                if self._intelligence_aggregator is not None:
                    domain = parsed.registered_domain or parsed.hostname
                    intelligence_data = self._intelligence_aggregator.gather_dict(domain)
            except Exception as e:
                logger.warning("Intelligence gathering failed: %s", e)

        # Step 6: Threat scoring
        risk_score = 0
        risk_level = "Unknown"
        
        # Load rule engine score onto features so ThreatScorer can fetch it
        features["rule_score"] = rule_result_data.get("rule_score", 0.0)
        features["official_domain_match"] = features.get("official_domain_match", False)

        try:
            if self._threat_scorer is not None:
                risk_score, risk_level = self._threat_scorer.score(
                    prediction_confidence=cal_prob_val, # Use calibrated probability in the decision engine
                    prediction_label=prediction_label,
                    features=features,
                    intelligence=intelligence_data,
                )
            else:
                risk_score, risk_level = self._simple_score(cal_prob_val, prediction_label)
        except Exception as e:
            logger.warning("Threat scoring failed: %s", e)
            risk_score, risk_level = self._simple_score(cal_prob_val, prediction_label)

        # Classify into Legitimate, Suspicious, or Phishing based on thresholds
        settings = get_settings()
        thresholds = settings.threat.classification_thresholds
        leg_max = thresholds.get("legitimate_max", 30)
        susp_max = thresholds.get("suspicious_max", 60)

        if risk_score <= leg_max:
            final_prediction = "Legitimate"
        elif risk_score <= susp_max:
            final_prediction = "Suspicious"
        else:
            final_prediction = "Phishing"

        # Calculate calibrated confidences
        ml_conf = (
            cal_prob_val
            if prediction_label.lower() == "phishing"
            else 1.0 - cal_prob_val
        )
        dec_conf = risk_score / 100.0

        if final_prediction == "Phishing":
            overall_confidence = dec_conf
        elif final_prediction == "Legitimate":
            overall_confidence = 1.0 - dec_conf
        else:
            # Suspicious: max confidence (1.0) is at 45-50 risk score, scaling down
            overall_confidence = 1.0 - abs(dec_conf - 0.45) * 2.0
        
        overall_confidence = max(0.0, min(1.0, overall_confidence))

        # --- Step 6b: URL transformer inference (Phase 3-A, optional) --
        transformer_conf: Optional[float] = None
        if self.use_transformer:
            try:
                self._load_transformer()
                if self._transformer_model is not None:
                    transformer_conf = float(
                        self._transformer_model.predict_proba(np.array([url]))[0]
                    )
                    logger.debug("Transformer probability: %.4f", transformer_conf)
            except Exception as e:
                logger.warning("URL transformer inference failed: %s", e)
                transformer_conf = None

        # Aggregate threat-intelligence score (0-1), reused by the ensemble
        # and the decision breakdown below.
        intel_scores = {
            "domain_age": self._threat_scorer._score_domain_age(intelligence_data) if self._threat_scorer else 0.5,
            "whois": self._threat_scorer._score_whois(intelligence_data) if self._threat_scorer else 0.5,
            "virustotal": self._threat_scorer._score_virustotal(intelligence_data) if self._threat_scorer else 0.0,
            "ssl": self._threat_scorer._score_ssl(intelligence_data) if self._threat_scorer else 0.5,
            "dns": self._threat_scorer._score_dns(intelligence_data) if self._threat_scorer else 0.5,
            "tld_risk": self._threat_scorer._score_tld_risk(features) if self._threat_scorer else 0.3,
            "brand_similarity": self._threat_scorer._score_brand_similarity(features) if self._threat_scorer else 0.0,
        }
        weighted_intel_sum = 0.0
        total_intel_weight = 0.0
        for signal, val in intel_scores.items():
            w = settings.threat.score_weights.get(signal, 0.10)
            weighted_intel_sum += val * w
            total_intel_weight += w
        intel_score = (weighted_intel_sum / total_intel_weight) if total_intel_weight > 0 else 0.0

        # --- Step 6c: Ensemble decision engine (Phase 3-B, opt-in) -----
        ensemble_data: dict[str, Any] = {}
        if self.use_ensemble:
            try:
                self._load_ensemble()
                if self._ensemble_engine is not None:
                    from src.ensemble.ensemble_engine import EnsembleInputs
                    decision = self._ensemble_engine.combine(EnsembleInputs(
                        xgboost_probability=cal_prob_val,
                        transformer_probability=transformer_conf,
                        rule_score=float(features.get("rule_score", 0.0)),
                        threat_intel_score=intel_score,
                        trust_score=float(features.get("trust_score", 50)),
                    ))
                    ensemble_data = decision.to_dict()
                    final_prediction = decision.prediction
                    risk_score = decision.risk_score
                    overall_confidence = decision.confidence

                    # Keep parity with ThreatScorer: verified official domains
                    # are clamped into the Legitimate range.
                    if features.get("official_domain_match", False) and risk_score > 20:
                        risk_score = 20
                        final_prediction = "Legitimate"
                        overall_confidence = 1.0 - (risk_score / 100.0)
                        ensemble_data["official_domain_clamp"] = True

                    dec_conf = risk_score / 100.0
                    if self._threat_scorer is not None:
                        risk_level = self._threat_scorer._get_risk_level(risk_score)
                    logger.info(
                        "Ensemble decision applied: %s (risk=%d, conf=%.3f)",
                        final_prediction, risk_score, overall_confidence,
                    )
            except Exception as e:
                logger.warning("Ensemble decision failed: %s", e)

        # Step 7: Generate reasons
        reasons: list[str] = []
        try:
            if self._reason_generator is not None:
                # Pass confidence IN the predicted label (not raw P(phishing))
                # so explanation text never reports 'legitimate with 0% confidence'.
                reasons = self._reason_generator.generate(
                    features=features,
                    intelligence=intelligence_data,
                    prediction=prediction_label,
                    confidence=ml_conf,
                    final_prediction=final_prediction,
                    risk_score=risk_score,
                )
            else:
                reasons = self._simple_reasons(features, prediction_label)
        except Exception as e:
            logger.warning("Reason generation failed: %s", e)
            reasons = self._simple_reasons(features, prediction_label)

        # Merge rule-engine reasons (avoiding duplicates from reason generator)
        all_reasons = list(reasons)
        for rule_reason in rule_reasons:
            if rule_reason not in all_reasons:
                all_reasons.append(rule_reason)

        # Step 7b: Generate positive, negative, and neutral indicators (v2.0)
        indicators = {
            "positive_indicators": [],
            "negative_indicators": [],
            "neutral_indicators": [],
        }
        if self._reason_generator is not None:
            try:
                indicators = self._reason_generator.generate_indicators(
                    features=features,
                    intelligence=intelligence_data,
                    prediction=final_prediction,
                    confidence=overall_confidence,
                    risk_score=risk_score,
                )
            except Exception as e:
                logger.warning("Failed to generate indicators: %s", e)

        # Build comprehensive metadata
        result_metadata: dict[str, Any] = {}
        if resolution_metadata:
            result_metadata["url_resolution"] = resolution_metadata
            result_metadata["original_url"] = original_url
        if rule_result_data:
            result_metadata["rule_engine"] = rule_result_data
            
        result_metadata["raw_ml_prediction"] = prediction_label

        # Calculate decision engine breakdown contributions
        w_ml = settings.threat.decision_weights.get("ml_probability", 0.35)
        w_rule = settings.threat.decision_weights.get("rule_engine", 0.30)
        w_intel = settings.threat.decision_weights.get("threat_intelligence", 0.20)
        w_total = w_ml + w_rule + w_intel + settings.threat.decision_weights.get("domain_trust_signals", 0.15)
        
        ml_contrib = (cal_prob_val * w_ml) / w_total * 100
        rule_contrib = (features.get("rule_score", 0.0) * w_rule) / w_total * 100

        # Intelligence score was computed once in Step 6b -- reuse it here.
        intel_contrib = (intel_score * w_intel) / w_total * 100

        trust_contrib = risk_score - (ml_contrib + rule_contrib + intel_contrib)

        # Structured decision breakdown (Phase 3 output)
        decision_breakdown: dict[str, Any] = {
            "ml_contribution": round(ml_contrib, 2),
            "rule_engine_contribution": round(rule_contrib, 2),
            "threat_intelligence_contribution": round(intel_contrib, 2),
            "trust_score_contribution": round(trust_contrib, 2),
            "final_risk_score": risk_score,
        }
        if ensemble_data:
            decision_breakdown["ensemble"] = {
                "breakdown": ensemble_data.get("breakdown", {}),
                "weights_used": ensemble_data.get("weights_used", {}),
            }
            result_metadata["ensemble"] = ensemble_data

        # --- Step 7c: SHAP explanation for XGBoost (Phase 3-C) ---------
        top_shap: list[dict[str, Any]] = []
        if not self._is_transformer and not rule_is_definite:
            try:
                self._load_shap()
                if self._shap_explainer is not None and self._shap_explainer.is_available:
                    shap_names = self._feature_pipeline.get_feature_names()
                    shap_row: list[float] = []
                    for name in shap_names:
                        value = features.get(name)
                        try:
                            shap_row.append(float(value) if value is not None else 0.0)
                        except (TypeError, ValueError):
                            shap_row.append(0.0)
                    explanation = self._shap_explainer.explain_local(
                        np.array([shap_row])
                    )
                    if explanation.success:
                        top_shap = [c.to_dict() for c in explanation.top_features]
            except Exception as e:
                logger.warning("SHAP explanation failed: %s", e)

        # Build final result
        result = PredictionResult(
            url=original_url,  # Always report on the original URL
            prediction=final_prediction,
            confidence=round(overall_confidence, 4),
            risk_score=risk_score,
            risk_level=risk_level,
            features=features,
            threat_intelligence=intelligence_data,
            reasons=all_reasons,
            model_type=self.model_type,
            metadata=result_metadata,
            
            # New fields (v2.0)
            trust_score=features.get("trust_score", 50),
            ml_confidence=round(ml_conf, 4),
            rule_confidence=round(features.get("rule_score", 0.0), 4),
            decision_confidence=round(dec_conf, 4),
            brand_detected=features.get("brand_detected"),
            official_domain=features.get("official_domain_match", False),
            ssl_status=intelligence_data.get("ssl_ssl_status", "UNKNOWN"),
            positive_indicators=indicators.get("positive_indicators", []),
            negative_indicators=indicators.get("negative_indicators", []),
            neutral_indicators=indicators.get("neutral_indicators", []),
            
            # Verification fields
            raw_probability=round(raw_prob_val, 6),
            calibrated_probability=round(cal_prob_val, 6),
            predicted_class=prediction_label,
            decision_threshold=decision_threshold_val,

            # Versioning fields (v2.1)
            model_version=(
                self._model.metadata.model_version
                if self._model is not None and self._model.is_trained
                else "unknown"
            ),
            feature_version=(
                self._model.metadata.feature_version
                if self._model is not None and self._model.is_trained
                else "unknown"
            ),

            # Phase 3 output fields (v3.0)
            transformer_confidence=(
                round(transformer_conf, 6) if transformer_conf is not None else None
            ),
            threat_intelligence_score=round(intel_score, 4),
            decision_breakdown=decision_breakdown,
            top_shap_features=top_shap,
            dataset_version=(
                self._model.metadata.dataset_version
                if self._model is not None and self._model.is_trained
                else "unknown"
            ),
            calibration_version=(
                self._model.metadata.calibration_version
                if self._model is not None and self._model.is_trained
                else "unknown"
            ),
        )

        # Optional diagnostics printing
        if diagnostics:
            print("\n" + "=" * 80)
            print("MODEL DIAGNOSTICS MODE")
            print("=" * 80)
            print(f"URL: {url}")
            print("\nExtracted features:")
            for k, v in sorted(features.items()):
                print(f"  {k}: {v}")
            
            print("\nBrand features:")
            brand_keys = ["brand_in_domain", "brand_in_subdomain", "brand_in_path",
                          "brand_levenshtein_distance", "brand_similarity_score",
                          "is_typosquatting", "brand_detected", "brand_location",
                          "brand_similarity", "official_domain_match", "closest_brand"]
            for k in brand_keys:
                if k in features:
                    print(f"  {k}: {features[k]}")
                    
            print("\nRule scores:")
            if self.use_rules and rule_result_data:
                print(f"  Rule Score: {rule_result_data.get('rule_score')}")
                print(f"  Definite Phishing: {rule_result_data.get('is_definite_phishing')}")
                findings = rule_result_data.get("findings", [])
                print(f"  Findings Count: {len(findings)}")
                for f in findings:
                    print(f"    - [{f['severity'].upper()}] {f['rule_id']}: {f['description']}")
            else:
                print("  Rule engine not used or no findings.")
                
            print("\nThreat intelligence:")
            for k, v in sorted(intelligence_data.items()):
                print(f"  {k}: {v}")
                
            print("\nScoring & Decision Summary:")
            print(f"  Trust score           : {features.get('trust_score', 50)}")
            print(f"  ML probability (raw)  : {raw_prob_val:.6f}")
            print(f"  Calibrated probability: {cal_prob_val:.6f}")
            print(f"  Decision score (Risk) : {risk_score}")
            print(f"  Final class           : {final_prediction}")
            print("\nDecision Breakdown:")
            print(f"  ML Contribution       : {ml_contrib:+.1f}")
            print(f"  Rule Engine           : {rule_contrib:+.1f}")
            print(f"  Threat Intelligence   : {intel_contrib:+.1f}")
            print(f"  Trust Score           : {trust_contrib:+.1f}")
            print(f"  Final Risk            : {risk_score}")
            print("=" * 80 + "\n")

        logger.info("Analysis complete: %s", result.summary())
        return result

    def predict_batch(self, urls: list[str]) -> list[PredictionResult]:
        """
        Analyze multiple URLs.

        Args:
            urls: List of URLs to analyze.

        Returns:
            List of PredictionResult objects.
        """
        logger.info("Batch analysis: %d URLs", len(urls))
        return [self.predict(url) for url in urls]

    def _heuristic_predict(self, features: dict[str, Any]) -> tuple[str, float]:
        """
        Fallback heuristic prediction when no ML model is available.

        Uses feature values to make a rule-based prediction.
        Returns the confidence IN the predicted class (always 0.5-1.0).

        Args:
            features: Extracted feature dictionary.

        Returns:
            Tuple of (prediction_label, confidence_in_prediction).
        """
        phishing_score = 0.0
        max_possible = 0.0

        # Check suspicious indicators -- each contributes to phishing score
        checks = [
            ("is_suspicious_tld", 1.0),
            ("is_ip_based", 1.0),
            ("is_punycode", 0.8),
            ("has_homograph_chars", 0.9),
            ("is_url_shortener", 0.5),
            ("contains_suspicious_keyword", 0.7),
            ("brand_in_subdomain", 0.8),
            ("brand_in_domain", 0.6),
            ("is_typosquatting", 0.9),
        ]

        for feature_name, weight in checks:
            if feature_name in features:
                max_possible += weight
                if features[feature_name]:
                    phishing_score += weight

        # Length-based heuristics
        url_length = features.get("url_length", 0)
        max_possible += 0.3
        if url_length > 100:
            phishing_score += 0.3

        # HTTPS check
        max_possible += 0.3
        if not features.get("is_https", True):
            phishing_score += 0.3

        subdomain_count = features.get("subdomain_count", 0)
        max_possible += 0.4
        if subdomain_count > 3:
            phishing_score += 0.4

        # Normalize to 0-1 probability of being phishing
        if max_possible > 0:
            phishing_prob = phishing_score / max_possible
        else:
            phishing_prob = 0.5

        # Decide label and compute confidence in the chosen label
        if phishing_prob >= 0.25:
            prediction = "phishing"
            confidence = 0.5 + (phishing_prob * 0.5)  # Map 0.25-1.0 -> 0.625-1.0
        else:
            prediction = "legitimate"
            confidence = 0.5 + ((1.0 - phishing_prob) * 0.5)  # Map 0-0.25 -> 0.875-1.0

        return prediction, round(min(confidence, 1.0), 4)

    def _simple_score(self, confidence: float, prediction: str) -> tuple[int, str]:
        """
        Simple threat scoring without the full scoring engine.

        Risk score reflects danger level: high score = dangerous.
        For phishing predictions, high confidence -> high score.
        For legitimate predictions, high confidence -> LOW score.

        Args:
            confidence: Model confidence in the predicted label.
            prediction: Prediction label.

        Returns:
            Tuple of (risk_score, risk_level).
        """
        if prediction == "phishing":
            # High confidence in phishing -> high risk
            risk_score = int(confidence * 100)
        elif prediction == "legitimate":
            # High confidence in legitimate -> LOW risk
            risk_score = int((1.0 - confidence) * 100)
        else:
            risk_score = 50  # Unknown

        risk_score = max(0, min(100, risk_score))

        if risk_score >= 80:
            risk_level = "Critical"
        elif risk_score >= 60:
            risk_level = "High"
        elif risk_score >= 40:
            risk_level = "Medium"
        elif risk_score >= 20:
            risk_level = "Low"
        else:
            risk_level = "Safe"

        return risk_score, risk_level

    def _simple_reasons(self, features: dict, prediction: str) -> list[str]:
        """
        Generate simple reasons without the full reason generator.

        Args:
            features: Feature dictionary.
            prediction: Prediction label.

        Returns:
            List of reason strings.
        """
        reasons = []

        if prediction == "legitimate":
            reasons.append("URL appears legitimate based on analysis")
            return reasons

        if features.get("is_suspicious_tld"):
            reasons.append("Suspicious top-level domain (TLD)")
        if features.get("is_ip_based"):
            reasons.append("URL uses IP address instead of domain name")
        if features.get("is_punycode"):
            reasons.append("Domain uses Punycode encoding (potential IDN homograph attack)")
        if features.get("has_homograph_chars"):
            reasons.append("Domain contains Unicode homograph characters")
        if features.get("is_url_shortener"):
            reasons.append("URL uses a URL shortening service")
        if features.get("contains_suspicious_keyword"):
            reasons.append("URL contains suspicious keywords (login, verify, secure, etc.)")
        if features.get("brand_in_subdomain"):
            reasons.append("Known brand name found in subdomain (potential impersonation)")
        if features.get("is_typosquatting"):
            reasons.append("Domain closely resembles a known brand (typosquatting)")
        if not features.get("is_https", True):
            reasons.append("URL does not use HTTPS encryption")
        url_length = features.get("url_length", 0)
        if url_length > 100:
            reasons.append(f"Unusually long URL ({url_length} characters)")
        subdomain_count = features.get("subdomain_count", 0)
        if subdomain_count > 3:
            reasons.append(f"Excessive number of subdomains ({subdomain_count})")

        if not reasons:
            reasons.append("Classified as phishing by AI model")

        return reasons
