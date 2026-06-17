"""Speech-to-Text interface for Renine.

Provides integration with faster-whisper for CUDA-accelerated
local speech recognition. Supports both file-based and in-memory
audio transcription.

Inputs:
    - Audio data (file path or numpy array).
    - config/settings.yaml for model size, device, and compute type.

Outputs:
    - Transcribed text string.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from renine.core.config import get_settings
from renine.core.exceptions import STTError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)

# Module-level model cache to avoid repeated loading
_model: Any = None


def _get_stt_config() -> dict[str, Any]:
    """Load STT configuration from settings.

    Returns:
        Dictionary with model_size, device, and compute_type.
    """
    settings = get_settings()
    return settings.get("voice", {}).get("stt", {})


def _load_model() -> Any:
    """Load or return the cached faster-whisper model.

    Returns:
        WhisperModel instance.

    Raises:
        STTError: If model loading fails.
    """
    global _model  # noqa: PLW0603
    if _model is not None:
        return _model

    try:
        from faster_whisper import WhisperModel

        config = _get_stt_config()
        model_size = config.get("model_size", "base.en")
        device = config.get("device", "cuda")
        compute_type = config.get("compute_type", "float16")

        logger.info(
            "loading_stt_model",
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )

        _model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

        logger.info("stt_model_loaded", model_size=model_size)
        return _model

    except Exception as e:
        logger.exception("stt_model_load_failed")
        raise STTError(f"Failed to load STT model: {e}") from e


def transcribe_audio(audio_data: np.ndarray, sample_rate: int = 16000) -> str:
    """Transcribe audio data to text.

    Args:
        audio_data: Audio samples as a numpy float32 array.
        sample_rate: Audio sample rate (default 16000 Hz).

    Returns:
        Transcribed text string.

    Raises:
        STTError: If transcription fails.
    """
    try:
        model = _load_model()
        segments, info = model.transcribe(
            audio_data,
            beam_size=5,
            language="en",
            vad_filter=True,
        )

        transcript = " ".join(seg.text.strip() for seg in segments)

        logger.info(
            "audio_transcribed",
            duration=f"{info.duration:.1f}s",
            language=info.language,
            transcript_length=len(transcript),
        )

        return transcript.strip()

    except STTError:
        raise
    except Exception as e:
        logger.exception("transcription_failed")
        raise STTError(f"Transcription failed: {e}") from e


def transcribe_file(file_path: str | Path) -> str:
    """Transcribe an audio file to text.

    Args:
        file_path: Path to the audio file (WAV, MP3, etc.).

    Returns:
        Transcribed text string.

    Raises:
        STTError: If the file cannot be read or transcription fails.
        FileNotFoundError: If the audio file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    try:
        model = _load_model()
        segments, info = model.transcribe(
            str(path),
            beam_size=5,
            language="en",
            vad_filter=True,
        )

        transcript = " ".join(seg.text.strip() for seg in segments)

        logger.info(
            "file_transcribed",
            file=str(path),
            duration=f"{info.duration:.1f}s",
            transcript_length=len(transcript),
        )

        return transcript.strip()

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.exception("file_transcription_failed", file=str(path))
        raise STTError(f"File transcription failed: {e}") from e


def unload_model() -> None:
    """Unload the STT model from memory to free VRAM."""
    global _model  # noqa: PLW0603
    if _model is not None:
        _model = None
        logger.info("stt_model_unloaded")
