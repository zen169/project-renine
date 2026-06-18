"""Vision agent for Renine.

Orchestrates all vision tasks — screenshots, OCR, image description,
and webcam capture. Routes user intent to the appropriate vision module
and ensures all outputs pass through security boundaries.

Vision outputs are classified as potentially sensitive (screenshots
may contain passwords, private messages, etc.) and must go through
ContextSanitizer before any external API transmission.

Inputs:
    - User text input describing the desired vision task.
    - Optional conversation context.

Outputs:
    - Processing result dictionary with content, image path, and metadata.
"""
from __future__ import annotations

from typing import Any

from renine.agents.base_agent import (
    AgentManifest,
    BaseAgent,
    MemoryAccessLevel,
)
from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel
from renine.vision import ocr, screenshot
from renine.vision.webcam import WebcamManager

logger = get_logger(__name__)


class VisionAgent(BaseAgent):
    """Agent that orchestrates screenshot, OCR, and webcam tasks.

    The VisionAgent holds a WebcamManager instance for session-level
    webcam consent tracking. Screenshots and OCR operations are
    stateless and do not require consent.
    """

    def __init__(self) -> None:
        """Initialize the VisionAgent with a WebcamManager."""
        self._webcam = WebcamManager()
        super().__init__()

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the VisionAgent.

        Returns:
            AgentManifest with Layer 1 memory access and READ_ONLY
            permission level. Webcam access is gated by its own
            consent mechanism.
        """
        return AgentManifest(
            name="vision",
            description=(
                "Captures screenshots, performs OCR, describes "
                "images, and manages webcam access"
            ),
            required_tools=["screenshot", "ocr", "webcam"],
            memory_access_level=MemoryAccessLevel.LAYER1_ONLY,
            permission_level=PermissionLevel.READ_ONLY,
            active_phase=5,
        )

    def _handle_screenshot(self, user_input: str) -> dict[str, Any]:
        """Handle screenshot capture requests.

        Args:
            user_input: User instruction text.

        Returns:
            Result dictionary with screenshot details.
        """
        monitor = None
        query = user_input.lower()
        if "monitor" in query:
            for word in query.split():
                if word.isdigit():
                    monitor = int(word)
                    break

        if "list monitors" in query or "show monitors" in query:
            monitors = screenshot.list_monitors()
            monitor_str = "\n".join(
                f"  Monitor {m['index']}: "
                f"{m['width']}x{m['height']}"
                for m in monitors
            )
            return {
                "content": f"Available monitors:\n{monitor_str}",
                "success": True,
                "monitors": monitors,
                "source_agent": "vision",
            }

        result = screenshot.capture(monitor=monitor, save=True)
        return {
            "content": (
                f"Screenshot captured "
                f"({result['width']}x{result['height']}). "
                f"Saved to: {result['path']}"
            ),
            "success": True,
            "image_path": result["path"],
            "width": result["width"],
            "height": result["height"],
            "source_agent": "vision",
        }

    def _handle_ocr(self, user_input: str) -> dict[str, Any]:
        """Handle OCR text extraction requests.

        Supports both file-based OCR and screenshot-then-OCR.

        Args:
            user_input: User instruction text.

        Returns:
            Result dictionary with extracted text.
        """
        query = user_input.lower()

        # OCR on current screen
        if "screen" in query or "screenshot" in query:
            cap_result = screenshot.capture(save=False)
            text = ocr.extract_text(cap_result["image"])
            return {
                "content": f"Extracted text from screen:\n{text}",
                "success": True,
                "extracted_text": text,
                "source_agent": "vision",
            }

        # OCR from file path — extract path from input
        path = self._extract_path_from_input(user_input)
        if path:
            text = ocr.extract_text(path)
            return {
                "content": f"Extracted text from {path}:\n{text}",
                "success": True,
                "extracted_text": text,
                "source_agent": "vision",
            }

        return {
            "content": (
                "Please specify an image file path or say "
                "'OCR screen' to read the current screen."
            ),
            "success": False,
            "source_agent": "vision",
        }

    def _handle_describe(self, user_input: str) -> dict[str, Any]:
        """Handle image description / VQA requests.

        Args:
            user_input: User instruction with optional custom prompt.

        Returns:
            Result dictionary with image description.
        """
        query = user_input.lower()

        # Describe current screen
        if "screen" in query or "screenshot" in query:
            cap_result = screenshot.capture(save=False)
            description = ocr.describe_image(cap_result["image"])
            return {
                "content": f"Screen description:\n{description}",
                "success": True,
                "description": description,
                "source_agent": "vision",
            }

        # Describe from file
        path = self._extract_path_from_input(user_input)
        if path:
            custom_prompt = self._extract_prompt(user_input)
            description = ocr.describe_image(path, prompt=custom_prompt)
            return {
                "content": f"Image description:\n{description}",
                "success": True,
                "description": description,
                "source_agent": "vision",
            }

        return {
            "content": (
                "Please specify an image to describe, or say "
                "'describe screen' to analyze the current screen."
            ),
            "success": False,
            "source_agent": "vision",
        }

    def _handle_webcam(self, user_input: str) -> dict[str, Any]:
        """Handle webcam-related requests.

        Args:
            user_input: User instruction text.

        Returns:
            Result dictionary with webcam operation results.
        """
        query = user_input.lower()

        if "consent" in query or "allow" in query or "grant" in query:
            self._webcam.grant_consent()
            return {
                "content": "Webcam consent granted for this session.",
                "success": True,
                "source_agent": "vision",
            }

        if "revoke" in query or "deny" in query or "stop" in query:
            self._webcam.revoke_consent()
            return {
                "content": "Webcam consent revoked. Camera released.",
                "success": True,
                "source_agent": "vision",
            }

        if not self._webcam.is_consent_granted:
            return {
                "content": (
                    "Webcam access requires your explicit consent. "
                    "Please say 'allow webcam' to grant access "
                    "for this session."
                ),
                "success": False,
                "requires_consent": True,
                "source_agent": "vision",
            }

        # Capture a frame
        frame = self._webcam.capture_frame()
        description = ocr.describe_image(frame)
        return {
            "content": f"Webcam capture:\n{description}",
            "success": True,
            "description": description,
            "source_agent": "vision",
        }

    def _extract_path_from_input(self, user_input: str) -> str | None:
        """Extract a file path from user input text.

        Simple heuristic: looks for strings containing path separators
        or common image extensions.

        Args:
            user_input: Raw user input.

        Returns:
            Extracted path string or None.
        """
        extensions = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        for word in user_input.split():
            cleaned = word.strip("\"'")
            if any(cleaned.lower().endswith(ext) for ext in extensions):
                return cleaned
            if "\\" in cleaned or "/" in cleaned:
                return cleaned
        return None

    def _extract_prompt(self, user_input: str) -> str | None:
        """Extract a custom prompt from user input.

        Looks for text after 'about' or 'asking' keywords.

        Args:
            user_input: Raw user input.

        Returns:
            Custom prompt string or None.
        """
        lower = user_input.lower()
        for keyword in ("about ", "asking "):
            if keyword in lower:
                idx = lower.index(keyword) + len(keyword)
                extracted = user_input[idx:].strip()
                return extracted if extracted else None
        return None

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process vision-related user requests.

        Routes to screenshot, OCR, image description, or webcam
        handlers based on keyword analysis.

        Args:
            user_input: The user's text input.
            context: Conversation history context.
            metadata: Additional metadata.

        Returns:
            Processing result dictionary.
        """
        try:
            query = user_input.lower().strip()

            # Webcam operations
            if any(kw in query for kw in (
                "webcam", "camera", "consent", "grant camera",
            )):
                return self._handle_webcam(user_input)

            # OCR / text extraction
            if "ocr" in query or "extract text" in query or "read text" in query:
                return self._handle_ocr(user_input)

            # Describe / analyze image
            if (
                "describe" in query
                or "what is" in query
                or "what do you see" in query
                or "analyze" in query
            ):
                return self._handle_describe(user_input)

            # Screenshot (default for ambiguous vision requests)
            if (
                "screenshot" in query
                or "capture" in query
                or "screen" in query
                or "monitor" in query
            ):
                return self._handle_screenshot(user_input)

            # General help
            return {
                "content": (
                    "I can help with vision tasks:\n"
                    "- Take a screenshot\n"
                    "- Extract text (OCR) from screen or image\n"
                    "- Describe what's on screen or in an image\n"
                    "- Capture from webcam (requires consent)\n"
                    "- List available monitors"
                ),
                "success": True,
                "source_agent": "vision",
            }

        except Exception as e:
            logger.exception("vision_agent_process_failed")
            return {
                "content": "",
                "success": False,
                "error": str(e),
                "source_agent": "vision",
            }
