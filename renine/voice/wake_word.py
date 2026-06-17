"""Wake word detection for Renine.

Listens for the wake word "Renine" in audio input to activate
the assistant. Uses a simple energy-based VAD (Voice Activity
Detection) combined with keyword matching from the STT output.

In Phase 1, wake word detection uses faster-whisper to transcribe
short audio segments and checks for the keyword. Future phases may
integrate a dedicated lightweight keyword spotter.

Inputs:
    - Audio frames from the microphone.
    - config/settings.yaml for wake word configuration.

Outputs:
    - Event published on "voice.wake_word_detected" when triggered.
"""
from __future__ import annotations

from typing import Any

from renine.core.config import get_settings
from renine.core.events import event_bus
from renine.core.logging_config import get_logger

logger = get_logger(__name__)

# Variants of the wake word to match against
_WAKE_WORD_VARIANTS = frozenset([
    "renine",
    "rennine",
    "reneen",
    "renin",
    "rénine",
    "hey renine",
])


def _get_wake_word() -> str:
    """Load the primary wake word from config.

    Returns:
        Lowercase wake word string.
    """
    settings = get_settings()
    return settings.get("voice", {}).get("wake_word", "renine").lower()


def check_wake_word(transcript: str) -> bool:
    """Check if a transcript contains the wake word.

    Performs case-insensitive matching against the wake word
    and common phonetic variants.

    Args:
        transcript: Transcribed text to check.

    Returns:
        True if the wake word is detected.
    """
    if not transcript:
        return False

    normalized = transcript.lower().strip()
    wake_word = _get_wake_word()

    # Check exact match or variant match
    for variant in _WAKE_WORD_VARIANTS:
        if variant in normalized:
            _on_wake_word_detected(transcript)
            return True

    # Check the configured wake word
    if wake_word in normalized:
        _on_wake_word_detected(transcript)
        return True

    return False


def extract_command_after_wake_word(transcript: str) -> str:
    """Extract the command portion after the wake word.

    Example: "Renine, what time is it?" -> "what time is it?"

    Args:
        transcript: Full transcript including wake word.

    Returns:
        Command text with wake word removed, or empty string.
    """
    if not transcript:
        return ""

    normalized = transcript.lower().strip()
    wake_word = _get_wake_word()

    # Try each variant
    for variant in [wake_word, *_WAKE_WORD_VARIANTS]:
        idx = normalized.find(variant)
        if idx != -1:
            command = transcript[idx + len(variant):].strip()
            # Remove leading punctuation/comma
            command = command.lstrip(",").lstrip(".").strip()
            return command

    return transcript


def _on_wake_word_detected(transcript: str) -> None:
    """Handle wake word detection — publish event and log.

    Args:
        transcript: The transcript that triggered detection.
    """
    logger.info("wake_word_detected", transcript=transcript)
    event_bus.publish("voice.wake_word_detected", {
        "transcript": transcript,
    })
