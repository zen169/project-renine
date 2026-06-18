"""Tests for VisionAgent orchestration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from renine.agents.vision_agent import VisionAgent


@pytest.fixture
def mock_settings():
    """Provide mock settings for vision agent."""
    return {
        "vision": {
            "model": "qwen2.5vl:7b",
            "screenshot": {
                "output_dir": "data/screenshots",
                "default_monitor": 1,
                "image_format": "png",
                "max_dimension": 1920,
            },
            "webcam": {
                "device_index": 0,
                "resolution_width": 640,
                "resolution_height": 480,
                "require_consent": True,
            },
            "ocr": {
                "max_image_size_bytes": 20971520,
                "supported_formats": [".png", ".jpg"],
            },
        },
        "ollama": {"host": "http://localhost:11434"},
    }


@pytest.fixture
def vision_agent(mock_settings):
    """Create VisionAgent with mocked config."""
    with patch(
        "renine.vision.webcam.get_settings",
        return_value=mock_settings,
    ):
        agent = VisionAgent()
    return agent


def test_manifest(vision_agent) -> None:
    """VisionAgent manifest declares correct capabilities."""
    m = vision_agent.get_manifest()
    assert m.name == "vision"
    assert m.active_phase == 5
    assert "screenshot" in m.required_tools
    assert "ocr" in m.required_tools
    assert "webcam" in m.required_tools


def test_screenshot_routing(vision_agent, mock_settings) -> None:
    """Screenshot request routes to screenshot handler."""
    mock_result = {
        "image": Image.new("RGB", (100, 80)),
        "path": "/fake/screenshot.png",
        "width": 100,
        "height": 80,
        "monitor": 1,
    }

    with patch(
        "renine.agents.vision_agent.screenshot.capture",
        return_value=mock_result,
    ):
        res = vision_agent.process("take a screenshot")

    assert res["success"] is True
    assert "100x80" in res["content"]


def test_ocr_screen_routing(vision_agent, mock_settings) -> None:
    """OCR screen request captures then extracts text."""
    mock_cap = {
        "image": Image.new("RGB", (100, 80)),
        "path": None,
        "width": 100,
        "height": 80,
        "monitor": 1,
    }

    with patch(
        "renine.agents.vision_agent.screenshot.capture",
        return_value=mock_cap,
    ), patch(
        "renine.agents.vision_agent.ocr.extract_text",
        return_value="Hello from screen",
    ):
        res = vision_agent.process("ocr screen")

    assert res["success"] is True
    assert "Hello from screen" in res["content"]


def test_webcam_requires_consent(vision_agent) -> None:
    """Webcam request without consent returns consent prompt."""
    res = vision_agent.process("open webcam")
    assert res["success"] is False
    assert res.get("requires_consent") is True


def test_webcam_consent_grant(vision_agent) -> None:
    """Grant consent via natural language."""
    res = vision_agent.process("grant camera consent")
    assert res["success"] is True
    assert vision_agent._webcam.is_consent_granted is True


def test_help_response(vision_agent) -> None:
    """Ambiguous input returns help text."""
    res = vision_agent.process("hello")
    assert res["success"] is True
    assert "vision tasks" in res["content"]


def test_describe_screen(vision_agent, mock_settings) -> None:
    """Describe screen request captures and describes."""
    mock_cap = {
        "image": Image.new("RGB", (100, 80)),
        "path": None,
        "width": 100,
        "height": 80,
        "monitor": 1,
    }

    with patch(
        "renine.agents.vision_agent.screenshot.capture",
        return_value=mock_cap,
    ), patch(
        "renine.agents.vision_agent.ocr.describe_image",
        return_value="A desktop with icons",
    ):
        res = vision_agent.process("describe screen")

    assert res["success"] is True
    assert "desktop" in res["content"]


def test_error_handling(vision_agent) -> None:
    """Process catches exceptions and returns error dict."""
    with patch(
        "renine.agents.vision_agent.screenshot.capture",
        side_effect=RuntimeError("mss crash"),
    ):
        res = vision_agent.process("take a screenshot")

    assert res["success"] is False
    assert "mss crash" in res["error"]
