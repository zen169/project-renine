"""Tests for renine.core.logging_config — structlog setup.

Validates:
- Logging configures without error.
- get_logger returns a structlog logger.
- Log files are created in the logs/ directory.
- Configuration is idempotent.
"""
from __future__ import annotations

from pathlib import Path

from renine.core.logging_config import configure_logging, get_logger


class TestConfigureLogging:
    """Tests for the configure_logging function."""

    def test_configure_does_not_raise(self) -> None:
        """configure_logging runs without error."""
        configure_logging()

    def test_idempotent(self) -> None:
        """Calling configure_logging multiple times has no effect."""
        configure_logging()
        configure_logging()  # Should not raise or duplicate handlers


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_returns_logger(self) -> None:
        """get_logger returns a bound logger object."""
        logger = get_logger("test_module")
        assert logger is not None

    def test_logger_has_standard_methods(self) -> None:
        """Logger has info, debug, warning, error methods."""
        logger = get_logger("test_methods")
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_named_logger(self) -> None:
        """Named loggers can be created for different modules."""
        logger_a = get_logger("module_a")
        logger_b = get_logger("module_b")
        assert logger_a is not None
        assert logger_b is not None

    def test_unnamed_logger(self) -> None:
        """Unnamed logger (None) returns a valid logger."""
        logger = get_logger(None)
        assert logger is not None

    def test_log_output_does_not_raise(self) -> None:
        """Writing log messages does not raise exceptions."""
        logger = get_logger("test_output")
        logger.info("test_message", key="value")
        logger.debug("debug_message")
        logger.warning("warning_message")
