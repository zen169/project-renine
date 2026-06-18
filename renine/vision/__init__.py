"""Vision — screenshot, OCR, and webcam understanding (Phase 5)."""
from __future__ import annotations

from renine.vision.screenshot import capture, list_monitors
from renine.vision.ocr import describe_image, extract_text
from renine.vision.webcam import WebcamManager

__all__ = [
    "capture",
    "list_monitors",
    "describe_image",
    "extract_text",
    "WebcamManager",
]
