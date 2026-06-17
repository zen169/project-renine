"""Custom exception hierarchy for Renine.

All exceptions inherit from RenineError to allow blanket catching
at module boundaries while preserving granularity for specific handlers.

Hierarchy:
    RenineError
    ├── ConfigError
    ├── BrainError
    │   ├── OllamaConnectionError
    │   ├── OllamaModelError
    │   └── ResponseBuildError
    ├── MemoryError_
    │   ├── MemoryLayerError
    │   └── MemoryRetrievalError
    ├── AgentError
    │   ├── AgentInitError
    │   └── AgentExecutionError
    ├── ToolError
    │   ├── ToolNotFoundError
    │   ├── ToolUnavailableError
    │   ├── ToolPermissionError
    │   └── ToolExecutionError
    ├── VoiceError
    │   ├── STTError
    │   ├── TTSError
    │   └── WakeWordError
    ├── SecurityError_
    │   ├── SanitizationError
    │   ├── InputValidationError
    │   ├── EncryptionError
    │   └── ConfirmationDeniedError
    └── UIError
"""
from __future__ import annotations


class RenineError(Exception):
    """Base exception for all Renine errors.

    All custom exceptions in the Renine project inherit from this class.
    This allows module boundaries to catch RenineError for structured
    error handling while preserving specific exception types for
    targeted recovery.
    """


# ============================================================
# Configuration Errors
# ============================================================


class ConfigError(RenineError):
    """Raised when a configuration file is missing or malformed."""


# ============================================================
# Brain / LLM Errors
# ============================================================


class BrainError(RenineError):
    """Base exception for brain/LLM-related errors."""


class OllamaConnectionError(BrainError):
    """Raised when the Ollama server cannot be reached."""


class OllamaModelError(BrainError):
    """Raised when the requested Ollama model is unavailable."""


class ResponseBuildError(BrainError):
    """Raised when the response builder fails to assemble a response."""


# ============================================================
# Memory Errors
# ============================================================


class MemoryError_(RenineError):
    """Base exception for memory-related errors.

    Named with trailing underscore to avoid shadowing the builtin
    MemoryError.
    """


class MemoryLayerError(MemoryError_):
    """Raised when a memory layer operation fails."""


class MemoryRetrievalError(MemoryError_):
    """Raised when memory retrieval (semantic search) fails."""


# ============================================================
# Agent Errors
# ============================================================


class AgentError(RenineError):
    """Base exception for agent-related errors."""


class AgentInitError(AgentError):
    """Raised when an agent fails to initialize."""


class AgentExecutionError(AgentError):
    """Raised when an agent encounters an error during execution."""


# ============================================================
# Tool Errors
# ============================================================


class ToolError(RenineError):
    """Base exception for tool-related errors."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not in the registry."""


class ToolUnavailableError(ToolError):
    """Raised when a tool exists but is disabled in config."""


class ToolPermissionError(ToolError):
    """Raised when the calling agent lacks permission for a tool."""


class ToolExecutionError(ToolError):
    """Raised when a tool fails during execution."""


# ============================================================
# Voice Errors
# ============================================================


class VoiceError(RenineError):
    """Base exception for voice pipeline errors."""


class STTError(VoiceError):
    """Raised when speech-to-text processing fails."""


class TTSError(VoiceError):
    """Raised when text-to-speech synthesis fails."""


class WakeWordError(VoiceError):
    """Raised when wake word detection fails."""


# ============================================================
# Security Errors
# ============================================================


class SecurityError_(RenineError):
    """Base exception for security-related errors.

    Named with trailing underscore to avoid shadowing potential
    future stdlib additions.
    """


class SanitizationError(SecurityError_):
    """Raised when context sanitization fails or detects a violation."""


class InputValidationError(SecurityError_):
    """Raised when user input fails validation checks."""


class EncryptionError(SecurityError_):
    """Raised when encryption or decryption operations fail."""


class ConfirmationDeniedError(SecurityError_):
    """Raised when a user denies a destructive operation confirmation."""


# ============================================================
# UI Errors
# ============================================================


class UIError(RenineError):
    """Raised when the UI layer encounters an error."""
