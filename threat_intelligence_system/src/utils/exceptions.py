"""
Custom exception hierarchy for the Phishing URL Detection Engine.

All engine-specific exceptions inherit from PhishingEngineError,
enabling fine-grained error handling throughout the system.
"""


class PhishingEngineError(Exception):
    """Base exception for all Phishing URL Detection Engine errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        base = self.message
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{base} [{detail_str}]"
        return base


class URLValidationError(PhishingEngineError):
    """Raised when URL validation fails."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            message=f"URL validation failed: {reason}",
            details={"url": url, "reason": reason},
        )
        self.url = url
        self.reason = reason


class URLParsingError(PhishingEngineError):
    """Raised when URL parsing encounters an unrecoverable error."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            message=f"URL parsing failed: {reason}",
            details={"url": url, "reason": reason},
        )
        self.url = url
        self.reason = reason


class FeatureExtractionError(PhishingEngineError):
    """Raised when feature extraction fails for a URL."""

    def __init__(self, url: str, extractor: str, reason: str) -> None:
        super().__init__(
            message=f"Feature extraction failed in {extractor}: {reason}",
            details={"url": url, "extractor": extractor, "reason": reason},
        )
        self.url = url
        self.extractor = extractor
        self.reason = reason


class ModelError(PhishingEngineError):
    """Raised when model training, loading, or inference fails."""

    def __init__(self, model_name: str, operation: str, reason: str) -> None:
        super().__init__(
            message=f"Model error in {model_name} during {operation}: {reason}",
            details={"model_name": model_name, "operation": operation, "reason": reason},
        )
        self.model_name = model_name
        self.operation = operation
        self.reason = reason


class IntelligenceError(PhishingEngineError):
    """Raised when threat intelligence lookup fails."""

    def __init__(self, connector: str, target: str, reason: str) -> None:
        super().__init__(
            message=f"Intelligence lookup failed in {connector} for {target}: {reason}",
            details={"connector": connector, "target": target, "reason": reason},
        )
        self.connector = connector
        self.target = target
        self.reason = reason


class DatasetError(PhishingEngineError):
    """Raised when dataset loading, cleaning, or processing fails."""

    def __init__(self, dataset: str, operation: str, reason: str) -> None:
        super().__init__(
            message=f"Dataset error in {dataset} during {operation}: {reason}",
            details={"dataset": dataset, "operation": operation, "reason": reason},
        )
        self.dataset = dataset
        self.operation = operation
        self.reason = reason


class ScoringError(PhishingEngineError):
    """Raised when threat scoring computation fails."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            message=f"Scoring failed for {url}: {reason}",
            details={"url": url, "reason": reason},
        )
        self.url = url
        self.reason = reason


class CheckpointError(PhishingEngineError):
    """Raised when checkpoint saving or loading fails."""

    def __init__(self, path: str, operation: str, reason: str) -> None:
        super().__init__(
            message=f"Checkpoint {operation} failed at {path}: {reason}",
            details={"path": path, "operation": operation, "reason": reason},
        )
        self.path = path
        self.operation = operation
        self.reason = reason
