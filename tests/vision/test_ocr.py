"""Tests for OCR module using Qwen2.5-VL via Ollama."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from renine.core.exceptions import OCRError
from renine.vision.ocr import (
    _image_to_base64,
    _validate_image_path,
    describe_image,
    extract_text,
)


@pytest.fixture
def mock_settings():
    """Provide mock settings for vision OCR config."""
    return {
        "vision": {
            "model": "qwen2.5vl:7b",
            "ocr": {
                "max_image_size_bytes": 20971520,
                "supported_formats": [".png", ".jpg", ".jpeg", ".bmp", ".webp"],
            },
        },
        "ollama": {
            "host": "http://localhost:11434",
        },
    }


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a small test PNG image."""
    img_path = tmp_path / "test_image.png"
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    img.save(str(img_path), format="PNG")
    return img_path


@pytest.fixture
def oversized_image(tmp_path: Path) -> Path:
    """Create a test image that exceeds the max size limit."""
    img_path = tmp_path / "large_image.png"
    # Write dummy bytes larger than 1KB to simulate oversized
    img_path.write_bytes(b"\x89PNG" + b"\x00" * 2000)
    return img_path


def test_image_to_base64() -> None:
    """PIL Image converts to base64 string successfully."""
    img = Image.new("RGB", (50, 50), color=(100, 150, 200))
    b64 = _image_to_base64(img)
    assert isinstance(b64, str)
    assert len(b64) > 0

    # Should be valid base64
    import base64
    decoded = base64.b64decode(b64)
    assert len(decoded) > 0


def test_validate_image_path_valid(sample_image: Path, mock_settings) -> None:
    """Valid image paths pass validation."""
    with patch("renine.vision.ocr.get_settings", return_value=mock_settings):
        result = _validate_image_path(str(sample_image))
        assert result == sample_image


def test_validate_image_path_missing(mock_settings) -> None:
    """Missing image path raises OCRError."""
    with patch("renine.vision.ocr.get_settings", return_value=mock_settings):
        with pytest.raises(OCRError, match="not found"):
            _validate_image_path("/nonexistent/path.png")


def test_validate_image_path_unsupported_format(tmp_path: Path, mock_settings) -> None:
    """Unsupported image format raises OCRError."""
    bad_file = tmp_path / "test.gif"
    bad_file.write_bytes(b"GIF89a")

    with patch("renine.vision.ocr.get_settings", return_value=mock_settings):
        with pytest.raises(OCRError, match="Unsupported"):
            _validate_image_path(str(bad_file))


def test_validate_image_path_oversized(tmp_path: Path) -> None:
    """Oversized image raises OCRError."""
    large_file = tmp_path / "big.png"
    large_file.write_bytes(b"\x00" * 100)

    tiny_limit_settings = {
        "vision": {
            "ocr": {
                "max_image_size_bytes": 50,
                "supported_formats": [".png"],
            },
        },
    }

    with patch("renine.vision.ocr.get_settings", return_value=tiny_limit_settings):
        with pytest.raises(OCRError, match="too large"):
            _validate_image_path(str(large_file))


def test_extract_text_from_file(sample_image: Path, mock_settings) -> None:
    """extract_text() calls vision model and returns extracted text."""
    mock_response = {
        "message": {"content": "Hello World from OCR test"},
    }

    mock_client = MagicMock()
    mock_client.chat.return_value = mock_response

    with patch("renine.vision.ocr.get_settings", return_value=mock_settings), \
         patch("renine.vision.ocr.ollama_lib.Client", return_value=mock_client):

        result = extract_text(str(sample_image))

    assert result == "Hello World from OCR test"
    mock_client.chat.assert_called_once()

    # Verify the call included images
    call_kwargs = mock_client.chat.call_args
    messages = call_kwargs.kwargs.get("messages", call_kwargs[1].get("messages", []))
    assert len(messages) == 1
    assert "images" in messages[0]


def test_extract_text_from_pil_image(mock_settings) -> None:
    """extract_text() works with PIL Image input."""
    img = Image.new("RGB", (100, 50), color=(200, 200, 200))
    mock_response = {
        "message": {"content": "Detected text from PIL image"},
    }

    mock_client = MagicMock()
    mock_client.chat.return_value = mock_response

    with patch("renine.vision.ocr.get_settings", return_value=mock_settings), \
         patch("renine.vision.ocr.ollama_lib.Client", return_value=mock_client):

        result = extract_text(img)

    assert result == "Detected text from PIL image"


def test_describe_image_default_prompt(sample_image: Path, mock_settings) -> None:
    """describe_image() uses default description prompt."""
    mock_response = {
        "message": {"content": "A blank white image."},
    }

    mock_client = MagicMock()
    mock_client.chat.return_value = mock_response

    with patch("renine.vision.ocr.get_settings", return_value=mock_settings), \
         patch("renine.vision.ocr.ollama_lib.Client", return_value=mock_client):

        result = describe_image(str(sample_image))

    assert result == "A blank white image."


def test_describe_image_custom_prompt(sample_image: Path, mock_settings) -> None:
    """describe_image() forwards custom prompts to the model."""
    mock_response = {
        "message": {"content": "There are 3 cats in the image."},
    }

    mock_client = MagicMock()
    mock_client.chat.return_value = mock_response

    with patch("renine.vision.ocr.get_settings", return_value=mock_settings), \
         patch("renine.vision.ocr.ollama_lib.Client", return_value=mock_client):

        result = describe_image(str(sample_image), prompt="How many cats?")

    assert "cats" in result

    call_kwargs = mock_client.chat.call_args
    messages = call_kwargs.kwargs.get("messages", call_kwargs[1].get("messages", []))
    assert messages[0]["content"] == "How many cats?"


def test_extract_text_model_error(sample_image: Path, mock_settings) -> None:
    """extract_text() raises OCRError when model fails."""
    import ollama as ollama_lib_mod

    mock_client = MagicMock()
    mock_client.chat.side_effect = ollama_lib_mod.ResponseError("model not found")

    with patch("renine.vision.ocr.get_settings", return_value=mock_settings), \
         patch("renine.vision.ocr.ollama_lib.Client", return_value=mock_client):

        with pytest.raises(OCRError, match="Vision model error"):
            extract_text(str(sample_image))
