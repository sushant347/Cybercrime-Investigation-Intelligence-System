"""
Central configuration for the Phishing URL Detection Engine.

Loads settings from environment variables (via .env file) with sensible defaults.
All paths, thresholds, brand lists, and model parameters are centralized here.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import yaml
from dotenv import load_dotenv


# Load .env file from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _load_yaml_config(file_path: Path) -> dict[str, Any]:
    """Helper to safely load YAML config with graceful fallback."""
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                return content if isinstance(content, dict) else {}
        except Exception as e:
            # Standalone engine: print warning and continue
            print(f"Warning: Failed to load configuration from {file_path}: {e}")
    return {}


_CONFIG_DIR = _PROJECT_ROOT / "config"
_SETTINGS_YAML = _load_yaml_config(_CONFIG_DIR / "settings.yaml")
_OFFICIAL_DOMAINS_YAML = _load_yaml_config(_CONFIG_DIR / "official_domains.yaml")


def _resolve_dataset_dir() -> Path:
    """Resolve the configurable training-dataset directory.

    Resolution order:
        1. ``DATASET_PATH`` environment variable (``.env`` supported).
        2. ``dataset_path`` key in ``config/settings.yaml``.
        3. Default: ``../sample`` relative to the project root.

    Relative paths are resolved against the project root so the setting
    behaves identically regardless of the current working directory.
    """
    raw_value = os.getenv("DATASET_PATH") or _SETTINGS_YAML.get("dataset_path") or "../sample"
    path = Path(raw_value)
    if not path.is_absolute():
        path = (_PROJECT_ROOT / path).resolve()
    return path


@dataclass(frozen=True)
class PathSettings:
    """File system path configuration."""

    project_root: Path = _PROJECT_ROOT
    dataset_dir: Path = field(default_factory=_resolve_dataset_dir)
    raw_data_dir: Path = field(default_factory=lambda: Path(
        os.getenv("RAW_DATA_DIR", str(_PROJECT_ROOT.parent / "threat-intelligent-system" / "raw"))
    ))
    processed_data_dir: Path = field(default_factory=lambda: Path(
        os.getenv("PROCESSED_DATA_DIR", str(_PROJECT_ROOT / "data" / "processed"))
    ))
    checkpoint_dir: Path = field(default_factory=lambda: Path(
        os.getenv("CHECKPOINT_DIR", str(_PROJECT_ROOT / "checkpoints"))
    ))
    results_dir: Path = field(default_factory=lambda: Path(
        os.getenv("RESULTS_DIR", str(_PROJECT_ROOT / "results"))
    ))


@dataclass(frozen=True)
class DatasetSettings:
    """Dataset processing configuration."""

    train_ratio: float = field(
        default_factory=lambda: float(os.getenv("TRAIN_RATIO", "0.70"))
    )
    validation_ratio: float = field(
        default_factory=lambda: float(os.getenv("VALIDATION_RATIO", "0.15"))
    )
    test_ratio: float = field(
        default_factory=lambda: float(os.getenv("TEST_RATIO", "0.15"))
    )
    tranco_sample_size: int = field(
        default_factory=lambda: int(os.getenv("TRANCO_SAMPLE_SIZE", "300000"))
    )
    random_seed: int = field(
        default_factory=lambda: int(os.getenv("RANDOM_SEED", "42"))
    )
    # Class-balance guard for merged training data: when the majority /
    # minority ratio exceeds this value the majority class is downsampled.
    balance_max_ratio: float = field(
        default_factory=lambda: float(os.getenv("BALANCE_MAX_RATIO", "1.5"))
    )
    # Optional cap on total rows used for training (0 = use everything).
    max_training_rows: int = field(
        default_factory=lambda: int(os.getenv("MAX_TRAINING_ROWS", "0"))
    )

    # Dataset file names
    phiusiil_filename: str = "PhiUSIIL_Phishing_URL_Dataset.csv"
    malicious_phish_filename: str = "malicious_phish.csv"
    phishtank_filename: str = "PhishTank_2026.csv"
    openphish_filename: str = "open_phish.txt"
    tranco_filename: str = "tranco_64W6X.csv"


@dataclass(frozen=True)
class TransformerSettings:
    """Transformer model training configuration."""

    batch_size: int = field(
        default_factory=lambda: int(os.getenv("TRANSFORMER_BATCH_SIZE", "32"))
    )
    learning_rate: float = field(
        default_factory=lambda: float(os.getenv("TRANSFORMER_LEARNING_RATE", "2e-5"))
    )
    num_epochs: int = field(
        default_factory=lambda: int(os.getenv("TRANSFORMER_EPOCHS", "5"))
    )
    mixed_precision: bool = field(
        default_factory=lambda: os.getenv("MIXED_PRECISION", "true").lower() == "true"
    )
    early_stopping_patience: int = field(
        default_factory=lambda: int(os.getenv("EARLY_STOPPING_PATIENCE", "3"))
    )
    max_length: int = 256
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    gradient_accumulation_steps: int = 1

    # Supported model identifiers
    model_registry: dict[str, str] = field(default_factory=lambda: {
        "distilbert": "distilbert-base-uncased",
        "bert": "bert-base-uncased",
        "roberta": "roberta-base",
        "mbert": "bert-base-multilingual-cased",
        "xlm-roberta": "xlm-roberta-base",
    })


@dataclass(frozen=True)
class TrainingSettings:
    """ML training pipeline configuration (cross-validation, tuning, extraction)."""

    # Stratified K-Fold cross-validation
    cv_folds: int = field(
        default_factory=lambda: int(os.getenv("CV_FOLDS", "5"))
    )
    # Stratified row cap for the CV stage only (0 = full training split)
    cv_sample_size: int = field(
        default_factory=lambda: int(os.getenv("CV_SAMPLE_SIZE", "0"))
    )
    # Optuna hyperparameter optimization
    tuning_trials: int = field(
        default_factory=lambda: int(os.getenv("OPTUNA_TRIALS", "25"))
    )
    # Stratified row cap for tuning trials only (0 = full training split)
    tuning_sample_size: int = field(
        default_factory=lambda: int(os.getenv("TUNING_SAMPLE_SIZE", "0"))
    )
    # Early-stopping patience for gradient-boosting trials
    early_stopping_rounds: int = field(
        default_factory=lambda: int(os.getenv("EARLY_STOPPING_ROUNDS", "30"))
    )
    # URLs per feature-extraction chunk (memory bound for huge datasets)
    extraction_chunk_size: int = field(
        default_factory=lambda: int(os.getenv("EXTRACTION_CHUNK_SIZE", "50000"))
    )


@dataclass(frozen=True)
class APISettings:
    """External API configuration."""

    virustotal_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("VIRUSTOTAL_API_KEY") or None
    )
    maxmind_license_key: Optional[str] = field(
        default_factory=lambda: os.getenv("MAXMIND_LICENSE_KEY") or None
    )
    request_timeout: int = 10
    max_retries: int = 3


@dataclass(frozen=True)
class ThreatSettings:
    """Threat detection thresholds and reference data."""

    # Risk level thresholds / classification thresholds (0-100 score)
    risk_thresholds: dict[str, int] = field(default_factory=lambda: {
        "Critical": 80,
        "High": 60,
        "Medium": 40,
        "Low": 20,
        "Safe": 0,
    })

    # Class thresholds for 3-class system
    classification_thresholds: dict[str, int] = field(default_factory=lambda: {
        "legitimate_max": _SETTINGS_YAML.get("classification_thresholds", {}).get("legitimate_max", 30),
        "suspicious_max": _SETTINGS_YAML.get("classification_thresholds", {}).get("suspicious_max", 60),
        "phishing_max": _SETTINGS_YAML.get("classification_thresholds", {}).get("phishing_max", 100),
    })

    # Hybrid decision engine weights
    decision_weights: dict[str, float] = field(default_factory=lambda: {
        "ml_probability": _SETTINGS_YAML.get("decision_weights", {}).get("ml_probability", 0.35),
        "rule_engine": _SETTINGS_YAML.get("decision_weights", {}).get("rule_engine", 0.30),
        "threat_intelligence": _SETTINGS_YAML.get("decision_weights", {}).get("threat_intelligence", 0.20),
        "domain_trust_signals": _SETTINGS_YAML.get("decision_weights", {}).get("domain_trust_signals", 0.15),
    })

    # Ensemble prediction weights (Phase 3-B)
    ensemble_weights: dict[str, float] = field(default_factory=lambda: {
        "xgboost": _SETTINGS_YAML.get("ensemble_weights", {}).get("xgboost", 0.35),
        "transformer": _SETTINGS_YAML.get("ensemble_weights", {}).get("transformer", 0.20),
        "rules": _SETTINGS_YAML.get("ensemble_weights", {}).get("rules", 0.20),
        "threat_intelligence": _SETTINGS_YAML.get("ensemble_weights", {}).get("threat_intelligence", 0.15),
        "trust": _SETTINGS_YAML.get("ensemble_weights", {}).get("trust", 0.10),
    })

    # Threat score weights (for component threat score)
    score_weights: dict[str, float] = field(default_factory=lambda: {
        "ai_prediction": 0.35,
        "domain_age": 0.10,
        "whois": 0.10,
        "virustotal": 0.15,
        "ssl": 0.08,
        "dns": 0.07,
        "brand_similarity": 0.10,
        "tld_risk": 0.05,
    })

    # Official brand domains registry
    official_domains: dict[str, list[str]] = field(default_factory=lambda: dict(_OFFICIAL_DOMAINS_YAML) or {
        "facebook": ["facebook.com", "fb.com", "instagram.com", "whatsapp.com"],
        "google": ["google.com", "gmail.com", "youtube.com", "android.com"],
        "github": ["github.com", "github.io", "githubusercontent.com"],
        "paypal": ["paypal.com", "paypal.me"],
        "amazon": ["amazon.com", "amazon.co.uk", "amazon.ca", "amazon.de", "amazon.co.jp"],
        "apple": ["apple.com", "icloud.com", "itunes.com"],
        "microsoft": ["microsoft.com", "office.com", "outlook.com", "live.com", "windows.com"],
        "linkedin": ["linkedin.com", "lnkd.in"],
        "discord": ["discord.com", "discord.gg"],
        "cloudflare": ["cloudflare.com"],
    })

    # Known brands for impersonation detection
    known_brands: list[str] = field(default_factory=lambda: list(
        _OFFICIAL_DOMAINS_YAML.keys() if _OFFICIAL_DOMAINS_YAML else [
            "paypal", "apple", "amazon", "google", "microsoft", "facebook",
            "netflix", "instagram", "twitter", "linkedin", "dropbox", "chase",
            "wellsfargo", "bankofamerica", "citibank", "usbank", "capitalone",
            "americanexpress", "discover", "hsbc", "barclays", "santander",
            "yahoo", "outlook", "hotmail", "gmail", "icloud", "adobe",
            "spotify", "uber", "airbnb", "ebay", "walmart", "target",
            "costco", "bestbuy", "homedepot", "lowes", "macys", "nordstrom",
            "dhl", "fedex", "ups", "usps", "royalmail", "hermes",
            "whatsapp", "telegram", "signal", "zoom", "slack", "teams",
            "coinbase", "binance", "kraken", "blockchain", "metamask",
            "steam", "epicgames", "playstation", "xbox", "nintendo",
            "github", "gitlab", "bitbucket", "stackoverflow",
            "stripe", "square", "venmo", "cashapp", "zelle",
        ]
    ))

    # Suspicious TLDs (commonly used in phishing)
    suspicious_tlds: list[str] = field(default_factory=lambda: list(
        _SETTINGS_YAML.get("threat_lists", {}).get("suspicious_tlds", [
            "xyz", "top", "club", "online", "site", "website", "space",
            "fun", "icu", "buzz", "cf", "gq", "ml", "ga", "tk",
            "work", "click", "link", "info", "biz", "pw", "cc",
            "loan", "racing", "win", "bid", "stream", "download",
            "review", "accountant", "cricket", "science", "party",
            "date", "faith", "trade", "men", "gdn", "kim", "wang",
            "rest", "surf", "bar", "cam", "monster", "hair", "sbs",
            "cfd", "quest", "boats", "beauty", "makeup", "onl"
        ])
    ))

    # Known URL shortener domains
    url_shorteners: list[str] = field(default_factory=lambda: list(
        _SETTINGS_YAML.get("threat_lists", {}).get("url_shorteners", [
            "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd",
            "buff.ly", "ow.ly", "rebrand.ly", "cutt.ly", "shorturl.at",
            "tiny.cc", "lnkd.in", "youtu.be", "amzn.to", "rb.gy",
            "bl.ink", "short.io", "clck.ru", "v.gd", "qr.ae",
            "u.to", "t.ly", "surl.li", "s.id", "shrtco.de",
            "mcaf.ee", "dlvr.it", "snip.ly", "smarturl.it",
        ])
    ))

    # Suspicious keywords commonly found in phishing URLs
    suspicious_keywords: list[str] = field(default_factory=lambda: list(
        _SETTINGS_YAML.get("threat_lists", {}).get("suspicious_keywords", [
            "login", "signin", "sign-in", "log-in", "verify", "verification",
            "account", "update", "secure", "security", "confirm", "confirmation",
            "suspend", "suspended", "restrict", "restricted", "unlock",
            "password", "credential", "authenticate", "authentication",
            "banking", "payment", "wallet", "billing", "invoice",
            "alert", "warning", "urgent", "immediately", "expire",
            "validate", "recover", "recovery", "reset", "restore",
            "unusual", "activity", "unauthorized", "compromised",
            "support", "helpdesk", "service", "customer",
            "webscr", "cmd", "dispatch", "redirect",
            "free", "prize", "winner", "congratulation", "reward",
            "offer", "bonus", "gift", "promo", "promotion",
        ])
    ))

    # Homograph character mapping (Unicode lookalikes)
    homograph_map: dict[str, str] = field(default_factory=lambda: dict(
        _SETTINGS_YAML.get("threat_lists", {}).get("homograph_map", {
            "а": "a",  # Cyrillic а
            "е": "e",  # Cyrillic е
            "о": "o",  # Cyrillic о
            "р": "p",  # Cyrillic р
            "с": "c",  # Cyrillic с
            "у": "y",  # Cyrillic у
            "х": "x",  # Cyrillic х
            "і": "i",  # Cyrillic і
            "ԁ": "d",  # Cyrillic ԁ
            "ɡ": "g",  # Latin ɡ
            "һ": "h",  # Cyrillic һ
            "ј": "j",  # Cyrillic ј
            "Ӏ": "l",  # Cyrillic Ӏ
            "ҽ": "s",  # Cyrillic ҽ
            "ԛ": "q",  # Cyrillic ԛ
            "յ": "h",  # Armenian յ
        })
    ))


@dataclass(frozen=True)
class LoggingSettings:
    """Logging configuration."""

    level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    log_file: Optional[str] = field(
        default_factory=lambda: os.getenv("LOG_FILE") or None
    )
    format: str = "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class Settings:
    """
    Master configuration object for the Phishing URL Detection Engine.

    Aggregates all sub-configurations into a single, immutable settings object.
    All values are loaded from environment variables with sensible defaults.

    Usage:
        settings = get_settings()
        print(settings.paths.raw_data_dir)
        print(settings.threat.known_brands)
    """

    paths: PathSettings = field(default_factory=PathSettings)
    dataset: DatasetSettings = field(default_factory=DatasetSettings)
    training: TrainingSettings = field(default_factory=TrainingSettings)
    transformer: TransformerSettings = field(default_factory=TransformerSettings)
    api: APISettings = field(default_factory=APISettings)
    threat: ThreatSettings = field(default_factory=ThreatSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for path in [
            self.paths.processed_data_dir,
            self.paths.checkpoint_dir,
            self.paths.results_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


# Module-level singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the global Settings singleton.

    Returns:
        Settings: The application-wide configuration object.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
