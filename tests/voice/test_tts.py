"""Tests for renine.voice.tts — Text-to-Speech interface."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from renine.core.exceptions import TTSError


class TestSynthesize:
    """Tests for the synthesize function."""

    def test_empty_text_raises(self) -> None:
        """Empty text raises TTSError."""
        from renine.voice.tts import synthesize
        with pytest.raises(TTSError):
            synthesize("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only text raises TTSError."""
        from renine.voice.tts import synthesize
        with pytest.raises(TTSError):
            synthesize("   ")

    @patch("renine.voice.tts._resolve_model_path")
    @patch("renine.voice.tts.subprocess.run")
    def test_successful_synthesis(self, mock_run: MagicMock, mock_path: MagicMock) -> None:
        """Successful synthesis returns numpy array."""
        from renine.voice.tts import synthesize

        mock_path.return_value = MagicMock()
        # Simulate raw PCM output (100 samples of silence)
        pcm_data = np.zeros(100, dtype=np.int16).tobytes()
        mock_run.return_value = MagicMock(returncode=0, stdout=pcm_data, stderr=b"")

        result = synthesize("Hello")
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) == 100

    @patch("renine.voice.tts._resolve_model_path")
    @patch("renine.voice.tts.subprocess.run")
    def test_piper_failure_raises(self, mock_run: MagicMock, mock_path: MagicMock) -> None:
        """Non-zero exit code raises TTSError."""
        from renine.voice.tts import synthesize

        mock_path.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"Error")

        with pytest.raises(TTSError):
            synthesize("Hello")
