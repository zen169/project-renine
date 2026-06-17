"""Text-to-Speech interface for Renine.

Provides integration with Piper TTS for local neural text-to-speech
synthesis. Audio is generated as WAV data that can be played through
the system audio output.

Inputs:
    - Text string to synthesize.
    - config/settings.yaml for model path and voice settings.

Outputs:
    - Audio data as numpy array or saved WAV file.
"""
from __future__ import annotations

import io
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any

import numpy as np

from renine.core.config import get_project_root, get_settings
from renine.core.exceptions import TTSError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


def _get_tts_config() -> dict[str, Any]:
    """Load TTS configuration from settings.

    Returns:
        Dictionary with model_path, config_path, and voice settings.
    """
    settings = get_settings()
    return settings.get("voice", {}).get("tts", {})


def _resolve_model_path() -> Path:
    """Resolve the Piper model path relative to project root.

    Returns:
        Absolute path to the Piper ONNX model.

    Raises:
        TTSError: If the model file does not exist.
    """
    config = _get_tts_config()
    model_path = config.get("model_path", "models/piper/en_US-lessac-medium.onnx")
    absolute_path = get_project_root() / model_path

    if not absolute_path.exists():
        raise TTSError(
            f"Piper TTS model not found at: {absolute_path}. "
            f"Download from https://github.com/rhasspy/piper/releases"
        )

    return absolute_path


def synthesize(text: str) -> np.ndarray:
    """Synthesize speech from text using Piper TTS.

    Uses Piper's command-line interface via subprocess for maximum
    compatibility. Audio is returned as a numpy float32 array.

    Args:
        text: Text to convert to speech.

    Returns:
        Audio samples as numpy float32 array (16kHz mono).

    Raises:
        TTSError: If synthesis fails.
    """
    if not text or not text.strip():
        raise TTSError("Cannot synthesize empty text.")

    try:
        model_path = _resolve_model_path()
        config = _get_tts_config()

        # Run Piper via subprocess
        result = subprocess.run(
            [
                "piper",
                "--model", str(model_path),
                "--output-raw",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
            shell=False,  # Security: never use shell=True
        )

        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="replace")
            raise TTSError(f"Piper TTS failed: {error_msg}")

        # Convert raw PCM to numpy array (16-bit signed, 22050Hz)
        audio_data = np.frombuffer(result.stdout, dtype=np.int16)
        audio_float = audio_data.astype(np.float32) / 32768.0

        logger.info(
            "speech_synthesized",
            text_length=len(text),
            audio_samples=len(audio_float),
        )

        return audio_float

    except TTSError:
        raise
    except subprocess.TimeoutExpired:
        raise TTSError("Piper TTS timed out after 30 seconds.")
    except FileNotFoundError:
        raise TTSError(
            "Piper TTS binary not found. Ensure 'piper' is installed "
            "and available in PATH."
        )
    except Exception as e:
        logger.exception("tts_synthesis_failed")
        raise TTSError(f"Speech synthesis failed: {e}") from e


def synthesize_to_file(text: str, output_path: str | Path) -> Path:
    """Synthesize speech and save to a WAV file.

    Args:
        text: Text to convert to speech.
        output_path: Path for the output WAV file.

    Returns:
        Path to the saved WAV file.

    Raises:
        TTSError: If synthesis or file writing fails.
    """
    audio_data = synthesize(text)
    output = Path(output_path)

    try:
        # Convert float32 back to int16 for WAV
        audio_int16 = (audio_data * 32767).astype(np.int16)

        with wave.open(str(output), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(22050)
            wav_file.writeframes(audio_int16.tobytes())

        logger.info("speech_saved_to_file", path=str(output))
        return output

    except Exception as e:
        logger.exception("tts_file_save_failed", path=str(output))
        raise TTSError(f"Failed to save audio file: {e}") from e
