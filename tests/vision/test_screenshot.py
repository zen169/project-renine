"""Tests for screenshot capture module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from renine.core.exceptions import ScreenshotError
from renine.vision.screenshot import (
    _generate_filename,
    _resize_if_needed,
    capture,
    list_monitors,
)


@pytest.fixture
def mock_settings():
    """Provide mock settings for vision config."""
    return {
        "vision": {
            "screenshot": {
                "output_dir": "data/screenshots",
                "default_monitor": 1,
                "image_format": "png",
                "max_dimension": 1920,
            },
        },
    }


@pytest.fixture
def mock_mss_monitor_data():
    """Provide mock monitor geometry data."""
    return [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    ]


def _make_fake_raw(width: int = 100, height: int = 80):
    """Create a fake mss raw capture result."""
    raw = MagicMock()
    raw.size = (width, height)
    # BGRX format: 4 bytes per pixel
    raw.bgra = bytes([100, 150, 200, 255] * width * height)
    return raw


def test_generate_filename() -> None:
    """Generated filenames follow the expected pattern."""
    name = _generate_filename("png")
    assert name.startswith("screenshot_")
    assert name.endswith(".png")
    assert len(name) > len("screenshot_.png")


def test_resize_if_needed_no_resize() -> None:
    """Images within max_dim are returned unchanged."""
    from PIL import Image

    img = Image.new("RGB", (800, 600))
    result = _resize_if_needed(img, 1920)
    assert result.size == (800, 600)


def test_resize_if_needed_downscale() -> None:
    """Oversized images are downscaled while preserving aspect ratio."""
    from PIL import Image

    img = Image.new("RGB", (3840, 2160))
    result = _resize_if_needed(img, 1920)
    assert result.size[0] <= 1920
    assert result.size[1] <= 1920
    # Aspect ratio preserved (16:9)
    ratio = result.size[0] / result.size[1]
    assert abs(ratio - (3840 / 2160)) < 0.01


def test_capture_produces_valid_image(tmp_path: Path, mock_settings) -> None:
    """capture() returns a PIL image with correct metadata."""
    mock_settings["vision"]["screenshot"]["output_dir"] = str(tmp_path)

    fake_raw = _make_fake_raw(100, 80)

    mock_sct = MagicMock()
    mock_sct.monitors = [
        {"left": 0, "top": 0, "width": 200, "height": 160},
        {"left": 0, "top": 0, "width": 100, "height": 80},
    ]
    mock_sct.grab.return_value = fake_raw
    mock_sct.__enter__ = MagicMock(return_value=mock_sct)
    mock_sct.__exit__ = MagicMock(return_value=False)

    with patch("renine.vision.screenshot.get_settings", return_value=mock_settings), \
         patch("renine.vision.screenshot.get_project_root", return_value=tmp_path), \
         patch("renine.vision.screenshot.mss.mss", return_value=mock_sct):

        result = capture(monitor=1, save=True)

    assert result["width"] == 100
    assert result["height"] == 80
    assert result["monitor"] == 1
    assert result["image"] is not None
    assert result["path"] is not None
    assert Path(result["path"]).exists()


def test_capture_unsaved_returns_no_path(mock_settings) -> None:
    """capture(save=False) returns image without saving to disk."""
    fake_raw = _make_fake_raw(100, 80)

    mock_sct = MagicMock()
    mock_sct.monitors = [
        {"left": 0, "top": 0, "width": 200, "height": 160},
        {"left": 0, "top": 0, "width": 100, "height": 80},
    ]
    mock_sct.grab.return_value = fake_raw
    mock_sct.__enter__ = MagicMock(return_value=mock_sct)
    mock_sct.__exit__ = MagicMock(return_value=False)

    with patch("renine.vision.screenshot.get_settings", return_value=mock_settings), \
         patch("renine.vision.screenshot.mss.mss", return_value=mock_sct):

        result = capture(monitor=1, save=False)

    assert result["image"] is not None
    assert result["path"] is None


def test_capture_invalid_monitor_raises(mock_settings) -> None:
    """capture() raises ScreenshotError for invalid monitor index."""
    mock_sct = MagicMock()
    mock_sct.monitors = [
        {"left": 0, "top": 0, "width": 200, "height": 160},
    ]
    mock_sct.__enter__ = MagicMock(return_value=mock_sct)
    mock_sct.__exit__ = MagicMock(return_value=False)

    with patch("renine.vision.screenshot.get_settings", return_value=mock_settings), \
         patch("renine.vision.screenshot.mss.mss", return_value=mock_sct):

        with pytest.raises(ScreenshotError, match="Monitor 5 not found"):
            capture(monitor=5)


def test_list_monitors(mock_settings, mock_mss_monitor_data) -> None:
    """list_monitors() returns correct monitor information."""
    mock_sct = MagicMock()
    mock_sct.monitors = mock_mss_monitor_data
    mock_sct.__enter__ = MagicMock(return_value=mock_sct)
    mock_sct.__exit__ = MagicMock(return_value=False)

    with patch("renine.vision.screenshot.get_settings", return_value=mock_settings), \
         patch("renine.vision.screenshot.mss.mss", return_value=mock_sct):

        monitors = list_monitors()

    assert len(monitors) == 3
    assert monitors[0]["index"] == 0
    assert monitors[1]["width"] == 1920
    assert monitors[2]["left"] == 1920
