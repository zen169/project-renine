"""Tests for renine.voice.stt — Speech-to-Text interface.

All tests use mocked faster-whisper — no GPU or model required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from renine.core.exceptions import STTError


class TestTranscribeAudio:
    """Tests for transcribe_audio."""

    @patch("renine.voice.stt._load_model")
    def test_returns_text(self, mock_load: MagicMock) -> None:
        """Audio data is transcribed to text."""
        from renine.voice.stt import transcribe_audio

        seg = MagicMock()
        seg.text = "Hello world"
        info = MagicMock(duration=1.0, language="en")
        mock_load.return_value.transcribe.return_value = ([seg], info)

        assert transcribe_audio(np.zeros(16000, dtype=np.float32)) == "Hello world"

    @patch("renine.voice.stt._load_model")
    def test_error_raises_stt_error(self, mock_load: MagicMock) -> None:
        """Transcription failure raises STTError."""
        from renine.voice.stt import transcribe_audio

        mock_load.return_value.transcribe.side_effect = RuntimeError("CUDA")
        with pytest.raises(STTError):
            transcribe_audio(np.zeros(16000, dtype=np.float32))


class TestTranscribeFile:
    """Tests for transcribe_file."""

    def test_nonexistent_file(self) -> None:
        """Non-existent file raises FileNotFoundError."""
        from renine.voice.stt import transcribe_file
        with pytest.raises(FileNotFoundError):
            transcribe_file("/nonexistent/audio.wav")


class TestUnloadModel:
    """Tests for model unloading."""

    def test_unload(self) -> None:
        """unload_model clears cached model."""
        from renine.voice import stt
        stt._model = MagicMock()
        stt.unload_model()
        assert stt._model is None
