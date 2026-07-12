"""
Structured logging for the Phishing URL Detection Engine.

Provides a centralized logging factory that respects configuration settings
and supports both console and file output.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


_initialized: bool = False


def _setup_root_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    fmt: str = "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
    date_fmt: str = "%Y-%m-%d %H:%M:%S",
) -> None:
    """
    Configure the root logger for the engine.

    This is called once on first use. Subsequent calls are no-ops.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to a log file. If None, logs go to console only.
        fmt: Log message format string.
        date_fmt: Date format string for log timestamps.
    """
    global _initialized
    if _initialized:
        return

    root_logger = logging.getLogger("phishing_engine")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent duplicate handlers
    if root_logger.handlers:
        _initialized = True
        return

    formatter = logging.Formatter(fmt, datefmt=date_fmt)

    # Console handler (always)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger under the phishing_engine namespace.

    Initializes the root logger on first call using settings from config.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        logging.Logger: A configured logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Feature extraction complete for URL: %s", url)
    """
    if not _initialized:
        try:
            from src.config.settings import get_settings
            settings = get_settings()
            _setup_root_logger(
                level=settings.logging.level,
                log_file=settings.logging.log_file,
                fmt=settings.logging.format,
                date_fmt=settings.logging.date_format,
            )
        except Exception:
            # Fallback if settings are unavailable (e.g., during testing)
            _setup_root_logger()

    # Create child logger under the engine namespace
    if name.startswith("src."):
        logger_name = f"phishing_engine.{name[4:]}"
    else:
        logger_name = f"phishing_engine.{name}"

    return logging.getLogger(logger_name)
