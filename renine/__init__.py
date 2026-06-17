"""Renine — A free, hybrid, local AI butler.

Main package entry point. All subpackages are organized by domain:
- core: foundational infrastructure (config, logging, exceptions, events)
- brain: LLM interface and orchestration
- agents: LangGraph agent implementations
- memory: four-layer memory system
- databases: SQLAlchemy models and migrations
- tools: tool registry and implementations
- voice: STT, TTS, and audio pipeline
- vision: screenshot, OCR, webcam (Phase 5)
- security: encryption, validation, confirmation gates
"""
from __future__ import annotations

__version__ = "0.1.0"
__app_name__ = "Renine"
