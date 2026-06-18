"""OCR and image understanding module for Renine.

Uses Qwen2.5-VL via Ollama to perform OCR and visual question answering
on images. Images are encoded as base64 and sent as multimodal messages
to the vision-language model.

Inputs:
    - Image file path or PIL Image object.
    - Optional text prompt for visual question answering.
    - config/settings.yaml for model and size limit settings.

Outputs:
    - Extracted text (OCR mode) or descriptive answer (VQA mode).

Raises:
    OCRError: If image processing or model inference fails.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image

from renine.core.config import get_settings
from renine.core.exceptions import OCRError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)

# Default prompts for common operations
_OCR_PROMPT = (
    "Extract all visible text from this image. "
    "Return only the extracted text, preserving layout where possible."
)
_DESCRIBE_PROMPT = (
    "Describe what you see in this image in detail. "
    "Include any visible text, objects, people, and layout."
)


def _get_vision_config() -> dict[str, Any]:
    """Extract vision-specific configuration from settings.

    Returns:
        Dictionary with vision settings.
    """
    settings = get_settings()
    return settings.get("vision", {})


def _get_ocr_config() -> dict[str, Any]:
    """Extract OCR-specific configuration.

    Returns:
        Dictionary with max size and supported format settings.
    """
    vision = _get_vision_config()
    return vision.get("ocr", {})


def _validate_image_path(image_path: str) -> Path:
    """Validate that an image path exists and has a supported format.

    Args:
        image_path: Path string to the image file.

    Returns:
        Resolved Path object.

    Raises:
        OCRError: If path is invalid or format is unsupported.
    """
    path = Path(image_path).resolve()
    if not path.exists():
        raise OCRError(f"Image file not found: {image_path}")

    config = _get_ocr_config()
    supported = config.get(
        "supported_formats",
        [".png", ".jpg", ".jpeg", ".bmp", ".webp"],
    )
    if path.suffix.lower() not in supported:
        raise OCRError(
            f"Unsupported image format: {path.suffix}. "
            f"Supported: {supported}"
        )

    max_size = config.get("max_image_size_bytes", 20971520)
    file_size = path.stat().st_size
    if file_size > max_size:
        raise OCRError(
            f"Image too large: {file_size} bytes. "
            f"Maximum: {max_size} bytes."
        )

    return path


def _image_to_base64(image: Image.Image, fmt: str = "PNG") -> str:
    """Convert a PIL Image to a base64-encoded string.

    Args:
        image: PIL Image object.
        fmt: Image format for encoding (e.g. "PNG", "JPEG").

    Returns:
        Base64-encoded image string.
    """
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def _load_image_as_base64(image_path: str) -> str:
    """Load an image file and return it as base64.

    Args:
        image_path: Path to the image file.

    Returns:
        Base64-encoded image string.

    Raises:
        OCRError: If the file cannot be read.
    """
    path = _validate_image_path(image_path)
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except OSError as e:
        raise OCRError(f"Failed to read image: {e}") from e


def _call_vision_model(
    image_b64: str,
    prompt: str,
    model: str | None = None,
) -> str:
    """Send an image + prompt to the vision model via Ollama.

    Args:
        image_b64: Base64-encoded image data.
        prompt: Text prompt accompanying the image.
        model: Model name override. Defaults to config value.

    Returns:
        Model response text.

    Raises:
        OCRError: If the model call fails.
    """
    import ollama as ollama_lib

    vision_config = _get_vision_config()
    target_model = model or vision_config.get("model", "qwen2.5vl:7b")

    settings = get_settings()
    host = settings.get("ollama", {}).get(
        "host", "http://localhost:11434"
    )

    try:
        client = ollama_lib.Client(host=host)
        response = client.chat(
            model=target_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
        )

        content = response.get("message", {}).get("content", "")
        logger.info(
            "vision_model_response",
            model=target_model,
            prompt_length=len(prompt),
            response_length=len(content),
        )
        return content

    except ollama_lib.ResponseError as e:
        logger.error("vision_model_error", model=target_model, error=str(e))
        raise OCRError(f"Vision model error: {e}") from e
    except Exception as e:
        logger.error("vision_model_connection_error", error=str(e))
        raise OCRError(f"Vision model connection failed: {e}") from e


def extract_text(
    image_source: str | Image.Image,
    model: str | None = None,
) -> str:
    """Extract text from an image using OCR via the vision model.

    Args:
        image_source: File path string or PIL Image object.
        model: Model name override. Defaults to config value.

    Returns:
        Extracted text string.

    Raises:
        OCRError: If OCR processing fails.
    """
    try:
        if isinstance(image_source, Image.Image):
            image_b64 = _image_to_base64(image_source)
        else:
            image_b64 = _load_image_as_base64(image_source)

        result = _call_vision_model(image_b64, _OCR_PROMPT, model=model)
        logger.info("ocr_extraction_complete", text_length=len(result))
        return result

    except OCRError:
        raise
    except Exception as e:
        logger.exception("ocr_extraction_failed")
        raise OCRError(f"OCR extraction failed: {e}") from e


def describe_image(
    image_source: str | Image.Image,
    prompt: str | None = None,
    model: str | None = None,
) -> str:
    """Describe an image or answer a visual question about it.

    Args:
        image_source: File path string or PIL Image object.
        prompt: Custom question/prompt. Defaults to general description.
        model: Model name override. Defaults to config value.

    Returns:
        Model's description or answer string.

    Raises:
        OCRError: If image analysis fails.
    """
    try:
        if isinstance(image_source, Image.Image):
            image_b64 = _image_to_base64(image_source)
        else:
            image_b64 = _load_image_as_base64(image_source)

        effective_prompt = prompt or _DESCRIBE_PROMPT
        result = _call_vision_model(
            image_b64, effective_prompt, model=model
        )
        logger.info(
            "image_description_complete",
            prompt_used=effective_prompt[:50],
            response_length=len(result),
        )
        return result

    except OCRError:
        raise
    except Exception as e:
        logger.exception("image_description_failed")
        raise OCRError(f"Image description failed: {e}") from e
