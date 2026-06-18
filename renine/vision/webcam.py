"""Webcam capture module for Renine.

Provides webcam access with mandatory per-session user consent.
The webcam will NEVER activate silently — explicit consent is
required before any frame can be captured.

Uses OpenCV for camera access and PIL for image conversion.

Inputs:
    - Device index (optional, defaults to config value).
    - User consent grant via grant_consent().
    - config/settings.yaml for resolution and device settings.

Outputs:
    - Captured frame as PIL Image object.

Raises:
    WebcamConsentError: If webcam is used without consent.
    WebcamError: If camera open/capture/release fails.
"""
from __future__ import annotations

from typing import Any

import cv2
from PIL import Image

from renine.core.config import get_settings
from renine.core.exceptions import WebcamConsentError, WebcamError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


def _get_webcam_config() -> dict[str, Any]:
    """Extract webcam-specific configuration from settings.

    Returns:
        Dictionary with device index, resolution, and consent settings.
    """
    settings = get_settings()
    return settings.get("vision", {}).get("webcam", {})


class WebcamManager:
    """Manages webcam access with mandatory consent gating.

    The webcam will not open unless consent has been explicitly granted
    for the current session. Consent resets when the manager is
    re-instantiated or revoke_consent() is called.

    Attributes:
        _consent_granted: Whether the user has granted camera consent.
        _capture: OpenCV VideoCapture instance (None when closed).
        _device_index: Camera device index.
    """

    def __init__(self, device_index: int | None = None) -> None:
        """Initialize the webcam manager.

        Args:
            device_index: Camera device index. Defaults to config value.
        """
        config = _get_webcam_config()
        self._device_index = (
            device_index
            if device_index is not None
            else config.get("device_index", 0)
        )
        self._consent_granted: bool = False
        self._capture: cv2.VideoCapture | None = None
        logger.info(
            "webcam_manager_initialized",
            device_index=self._device_index,
        )

    @property
    def is_consent_granted(self) -> bool:
        """Check if webcam consent has been granted.

        Returns:
            True if consent is active for this session.
        """
        return self._consent_granted

    @property
    def is_open(self) -> bool:
        """Check if the webcam is currently open.

        Returns:
            True if camera is open and ready.
        """
        return (
            self._capture is not None
            and self._capture.isOpened()
        )

    def grant_consent(self) -> None:
        """Grant webcam access consent for the current session.

        Must be called before any capture operations.
        """
        self._consent_granted = True
        logger.info("webcam_consent_granted")

    def revoke_consent(self) -> None:
        """Revoke webcam access consent and release the camera.

        Automatically closes the camera if it was open.
        """
        self._consent_granted = False
        self.release()
        logger.info("webcam_consent_revoked")

    def _check_consent(self) -> None:
        """Verify that consent has been granted.

        Raises:
            WebcamConsentError: If consent has not been granted.
        """
        if not self._consent_granted:
            msg = (
                "Webcam access requires explicit user consent. "
                "Call grant_consent() before capturing."
            )
            logger.warning("webcam_consent_denied")
            raise WebcamConsentError(msg)

    def open(self) -> None:
        """Open the webcam device.

        Applies configured resolution settings after opening.

        Raises:
            WebcamConsentError: If consent has not been granted.
            WebcamError: If the camera cannot be opened.
        """
        self._check_consent()

        if self.is_open:
            logger.debug("webcam_already_open")
            return

        config = _get_webcam_config()
        width = config.get("resolution_width", 640)
        height = config.get("resolution_height", 480)

        try:
            self._capture = cv2.VideoCapture(self._device_index)
            if not self._capture.isOpened():
                self._capture = None
                raise WebcamError(
                    f"Failed to open webcam device {self._device_index}"
                )

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            logger.info(
                "webcam_opened",
                device=self._device_index,
                resolution=(width, height),
            )
        except WebcamError:
            raise
        except Exception as e:
            self._capture = None
            logger.exception("webcam_open_failed")
            raise WebcamError(f"Webcam open failed: {e}") from e

    def capture_frame(self) -> Image.Image:
        """Capture a single frame from the webcam.

        Opens the camera if not already open.

        Returns:
            PIL Image of the captured frame (RGB).

        Raises:
            WebcamConsentError: If consent has not been granted.
            WebcamError: If frame capture fails.
        """
        self._check_consent()

        if not self.is_open:
            self.open()

        try:
            ret, frame = self._capture.read()  # type: ignore[union-attr]
            if not ret or frame is None:
                raise WebcamError("Failed to read frame from webcam")

            # OpenCV uses BGR, convert to RGB for PIL
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb_frame)

            logger.debug(
                "webcam_frame_captured",
                size=image.size,
            )
            return image

        except WebcamError:
            raise
        except Exception as e:
            logger.exception("webcam_capture_failed")
            raise WebcamError(f"Frame capture failed: {e}") from e

    def release(self) -> None:
        """Release the webcam device and free resources.

        Safe to call even if the camera is not open.
        """
        if self._capture is not None:
            try:
                self._capture.release()
                logger.info("webcam_released", device=self._device_index)
            except Exception as e:
                logger.exception("webcam_release_failed")
                raise WebcamError(f"Webcam release failed: {e}") from e
            finally:
                self._capture = None

    def __enter__(self) -> WebcamManager:
        """Context manager entry — opens the camera.

        Returns:
            Self for use in with-statement.

        Raises:
            WebcamConsentError: If consent has not been granted.
            WebcamError: If camera open fails.
        """
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit — releases the camera."""
        self.release()

    def __del__(self) -> None:
        """Destructor — ensures camera is released on garbage collection."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
