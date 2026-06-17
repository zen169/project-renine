"""Centralized structured logging setup for Renine.

Configures structlog with JSON output, daily file rotation, and
module-specific log level overrides. All modules MUST use the
logger provided by this module — never use print().

Inputs:
    - config/logging.yaml for log levels, rotation, and output settings.

Outputs:
    - Configured structlog logger accessible via get_logger().
    - Log files written to logs/ directory with daily rotation.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from renine.core.config import get_logging_config, get_project_root


_configured = False


def _ensure_log_directory(log_dir: Path) -> None:
    """Create the log directory if it does not exist.

    Args:
        log_dir: Path to the log directory.
    """
    log_dir.mkdir(parents=True, exist_ok=True)


def _build_file_handler(config: dict[str, Any]) -> logging.Handler:
    """Create a timed rotating file handler from config.

    Args:
        config: File logging configuration dictionary.

    Returns:
        Configured TimedRotatingFileHandler.
    """
    project_root = get_project_root()
    log_dir = project_root / config.get("directory", "logs")
    _ensure_log_directory(log_dir)

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    pattern = config.get("filename_pattern", "renine_{date}.log")
    filename = pattern.replace("{date}", today)
    log_path = log_dir / filename

    handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_path),
        when="midnight",
        interval=1,
        backupCount=config.get("retention_days", 30),
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    return handler


def _build_console_handler(config: dict[str, Any]) -> logging.Handler:
    """Create a console stream handler from config.

    Args:
        config: Console logging configuration dictionary.

    Returns:
        Configured StreamHandler.
    """
    handler = logging.StreamHandler(sys.stdout)
    level_name = config.get("level", "DEBUG")
    handler.setLevel(getattr(logging, level_name.upper(), logging.DEBUG))
    return handler


def configure_logging() -> None:
    """Initialize the structlog and stdlib logging pipeline.

    Reads configuration from config/logging.yaml and sets up:
    - JSON-formatted structured log output
    - File handler with daily rotation
    - Console handler with optional colors
    - Module-specific log level overrides

    This function is idempotent — calling it multiple times has no effect.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    try:
        log_config = get_logging_config().get("logging", {})
    except FileNotFoundError:
        log_config = {}

    root_level = log_config.get("level", "INFO")
    if isinstance(root_level, str) and root_level.startswith("$"):
        root_level = "INFO"

    # --- Configure stdlib root logger ---
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, root_level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # File handler
    file_config = log_config.get("file", {})
    if file_config.get("enabled", True):
        root_logger.addHandler(_build_file_handler(file_config))

    # Console handler
    console_config = log_config.get("console", {})
    if console_config.get("enabled", True):
        root_logger.addHandler(_build_console_handler(console_config))

    # Module-specific overrides
    overrides = log_config.get("overrides", {})
    for module_name, level in overrides.items():
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # --- Configure structlog ---
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, root_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.
              If None, returns an unnamed logger.

    Returns:
        Bound structlog logger instance.
    """
    configure_logging()
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()
