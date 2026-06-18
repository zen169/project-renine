"""Screen capture module for Renine.

Captures screenshots of individual monitors or the full desktop using
the `mss` library. Images are saved to the configured output directory
and returned as PIL Image objects for downstream processing.

Inputs:
    - Monitor index (optional, defaults to config value).
    - config/settings.yaml for output directory and format settings.

Outputs:
    - Saved screenshot file path.
    - PIL Image object for in-memory processing.

Raises:
    ScreenshotError: If screen capture fails.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import mss
from PIL import Image

from renine.core.config import get_project_root, get_settings
from renine.core.exceptions import ScreenshotError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


def _get_vision_config() -> dict[str, Any]:
    """Extract vision-specific configuration from settings.

    Returns:
        Dictionary with vision settings.
    """
    settings = get_settings()
    return settings.get("vision", {})


def _get_screenshot_config() -> dict[str, Any]:
    """Extract screenshot-specific configuration.

    Returns:
        Dictionary with screenshot output dir, format, and monitor.
    """
    vision = _get_vision_config()
    return vision.get("screenshot", {})


def _ensure_output_dir() -> Path:
    """Create the screenshot output directory if it does not exist.

    Returns:
        Absolute path to the output directory.
    """
    config = _get_screenshot_config()
    relative_dir = config.get("output_dir", "data/screenshots")
    output_dir = get_project_root() / relative_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _generate_filename(image_format: str) -> str:
    """Generate a timestamped filename for a screenshot.

    Args:
        image_format: File extension without dot (e.g. "png").

    Returns:
        Filename string like "screenshot_20260618_164500.png".
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"screenshot_{timestamp}.{image_format}"


def _resize_if_needed(image: Image.Image, max_dim: int) -> Image.Image:
    """Downscale an image if either dimension exceeds max_dim.

    Maintains aspect ratio. Returns original image if no resize needed.

    Args:
        image: PIL Image to potentially resize.
        max_dim: Maximum allowed width or height in pixels.

    Returns:
        Resized or original PIL Image.
    """
    width, height = image.size
    if width <= max_dim and height <= max_dim:
        return image

    scale = min(max_dim / width, max_dim / height)
    new_size = (int(width * scale), int(height * scale))
    logger.debug(
        "screenshot_resized",
        original=(width, height),
        new_size=new_size,
    )
    return image.resize(new_size, Image.LANCZOS)


def capture(
    monitor: int | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Capture a screenshot of the specified monitor.

    Args:
        monitor: Monitor index (1-based). 0 or None captures all monitors
                 combined. Defaults to config value.
        save: Whether to save the screenshot to disk.

    Returns:
        Dictionary with keys:
            - "image": PIL Image object.
            - "path": Absolute file path (if saved), else None.
            - "width": Image width in pixels.
            - "height": Image height in pixels.
            - "monitor": Monitor index used.

    Raises:
        ScreenshotError: If capture fails.
    """
    config = _get_screenshot_config()
    target_monitor = monitor if monitor is not None else config.get(
        "default_monitor", 1
    )
    image_format = config.get("image_format", "png")
    max_dim = config.get("max_dimension", 1920)

    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            if target_monitor >= len(monitors):
                raise ScreenshotError(
                    f"Monitor {target_monitor} not found. "
                    f"Available: 0-{len(monitors) - 1}"
                )

            raw = sct.grab(monitors[target_monitor])
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        image = _resize_if_needed(image, max_dim)

        file_path: str | None = None
        if save:
            output_dir = _ensure_output_dir()
            filename = _generate_filename(image_format)
            full_path = output_dir / filename
            image.save(str(full_path), format=image_format.upper())
            file_path = str(full_path)
            logger.info(
                "screenshot_captured",
                path=file_path,
                size=image.size,
                monitor=target_monitor,
            )

        return {
            "image": image,
            "path": file_path,
            "width": image.size[0],
            "height": image.size[1],
            "monitor": target_monitor,
        }

    except ScreenshotError:
        raise
    except Exception as e:
        logger.exception("screenshot_capture_failed")
        raise ScreenshotError(f"Failed to capture screenshot: {e}") from e


def list_monitors() -> list[dict[str, int]]:
    """List all available monitors and their dimensions.

    Returns:
        List of dicts with 'index', 'left', 'top', 'width', 'height' keys.
        Index 0 is the combined virtual screen.

    Raises:
        ScreenshotError: If monitor enumeration fails.
    """
    try:
        with mss.mss() as sct:
            result = []
            for idx, mon in enumerate(sct.monitors):
                result.append({
                    "index": idx,
                    "left": mon["left"],
                    "top": mon["top"],
                    "width": mon["width"],
                    "height": mon["height"],
                })
            logger.info("monitors_listed", count=len(result))
            return result
    except Exception as e:
        logger.exception("monitor_list_failed")
        raise ScreenshotError(f"Failed to list monitors: {e}") from e
