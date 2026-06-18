"""Tests for webcam capture module with consent gating."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from renine.core.exceptions import WebcamConsentError, WebcamError
from renine.vision.webcam import WebcamManager


@pytest.fixture
def mock_settings():
    """Provide mock settings for webcam config."""
    return {
        "vision": {
            "webcam": {
                "device_index": 0,
                "resolution_width": 640,
                "resolution_height": 480,
                "require_consent": True,
            },
        },
    }


@pytest.fixture
def webcam_manager(mock_settings):
    """Create a WebcamManager with mocked config."""
    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ):
        manager = WebcamManager()
    return manager


def test_consent_default_denied(webcam_manager) -> None:
    """Consent is not granted by default."""
    assert webcam_manager.is_consent_granted is False


def test_grant_and_revoke_consent(webcam_manager) -> None:
    """grant/revoke consent toggles access state."""
    webcam_manager.grant_consent()
    assert webcam_manager.is_consent_granted is True
    webcam_manager.revoke_consent()
    assert webcam_manager.is_consent_granted is False


def test_open_without_consent_raises(webcam_manager, mock_settings) -> None:
    """open() raises WebcamConsentError without consent."""
    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ):
        with pytest.raises(WebcamConsentError):
            webcam_manager.open()


def test_capture_without_consent_raises(webcam_manager, mock_settings) -> None:
    """capture_frame() raises WebcamConsentError without consent."""
    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ):
        with pytest.raises(WebcamConsentError):
            webcam_manager.capture_frame()


def test_open_with_consent(webcam_manager, mock_settings) -> None:
    """open() succeeds when consent is granted."""
    webcam_manager.grant_consent()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.vision.webcam.cv2.VideoCapture",
        return_value=mock_cap,
    ):
        webcam_manager.open()

    assert webcam_manager.is_open is True


def test_open_fails_raises(webcam_manager, mock_settings) -> None:
    """open() raises WebcamError when camera fails."""
    webcam_manager.grant_consent()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.vision.webcam.cv2.VideoCapture",
        return_value=mock_cap,
    ):
        with pytest.raises(WebcamError, match="Failed to open"):
            webcam_manager.open()


def test_capture_frame_returns_image(webcam_manager, mock_settings) -> None:
    """capture_frame() returns a valid PIL Image."""
    webcam_manager.grant_consent()
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    rgb_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, fake_frame)

    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.vision.webcam.cv2.VideoCapture",
        return_value=mock_cap,
    ), patch(
        "renine.vision.webcam.cv2.cvtColor",
        return_value=rgb_frame,
    ):
        image = webcam_manager.capture_frame()

    assert image.size == (640, 480)
    assert image.mode == "RGB"


def test_release_closes_camera(webcam_manager, mock_settings) -> None:
    """release() frees camera resources."""
    webcam_manager.grant_consent()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.vision.webcam.cv2.VideoCapture",
        return_value=mock_cap,
    ):
        webcam_manager.open()
        webcam_manager.release()

    assert webcam_manager._capture is None
    mock_cap.release.assert_called_once()


def test_context_manager_no_leaks(webcam_manager, mock_settings) -> None:
    """Context manager opens on enter and releases on exit."""
    webcam_manager.grant_consent()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.vision.webcam.cv2.VideoCapture",
        return_value=mock_cap,
    ):
        with webcam_manager as wm:
            assert wm.is_open is True

    mock_cap.release.assert_called_once()
    assert webcam_manager._capture is None


def test_release_safe_when_not_open(webcam_manager) -> None:
    """release() is safe when camera was never opened."""
    webcam_manager.release()
    assert webcam_manager._capture is None


def test_revoke_releases_camera(webcam_manager, mock_settings) -> None:
    """revoke_consent() auto-releases the camera."""
    webcam_manager.grant_consent()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.vision.webcam.cv2.VideoCapture",
        return_value=mock_cap,
    ):
        webcam_manager.open()
        webcam_manager.revoke_consent()

    assert webcam_manager.is_consent_granted is False
    assert webcam_manager._capture is None
    mock_cap.release.assert_called_once()
