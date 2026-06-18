"""PDF reader tool for Renine.

Provides a tool to extract text from PDF documents using PyMuPDF (fitz).
Enforces path validation and size limits.
"""
from __future__ import annotations

from typing import Any

import fitz  # PyMuPDF

from renine.core.config import get_security_config
from renine.core.logging_config import get_logger
from renine.security.input_validator import validate_path
from renine.tools.permissions import PermissionLevel
from renine.tools.registry import BaseTool, ToolResult, register_tool

logger = get_logger(__name__)


def _extract_pdf_text(path_str: str) -> dict[str, Any]:
    """Helper to validate path, check file size, and extract text from PDF.

    Args:
        path_str: Path to the PDF file.

    Returns:
        Dictionary containing extracted text and metadata.

    Raises:
        ValueError: If size limits are exceeded.
    """
    path = validate_path(path_str)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found at: {path}")

    # Check file size against policy
    sec_config = get_security_config().get("security", {})
    fs_config = sec_config.get("filesystem", {})
    max_size = fs_config.get("max_read_size_bytes", 52428800)

    if path.stat().st_size > max_size:
        raise ValueError(
            f"File size exceeds policy limit of {max_size} bytes."
        )

    text_pages: list[str] = []
    logger.info("reading_pdf_file", path=str(path))

    with fitz.open(str(path)) as doc:
        total_pages = len(doc)
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            text_pages.append(page.get_text())

    return {
        "text": "\n".join(text_pages),
        "total_pages": total_pages,
        "file_name": path.name,
    }


@register_tool(
    name="pdf_reader",
    description="Read and extract text from a PDF file",
    permission_level=PermissionLevel.READ_ONLY,
    requires_confirmation=False,
)
class PDFReaderTool(BaseTool):
    """Tool to read text content from PDF files."""

    def execute(self, file_path: str, **kwargs: Any) -> ToolResult:
        """Extract text from a PDF file.

        Args:
            file_path: Absolute or relative path to the PDF file.
            **kwargs: Extra arguments.

        Returns:
            ToolResult containing the extracted text and page count.
        """
        if not file_path:
            return ToolResult(success=False, error="File path cannot be empty.")

        try:
            res = _extract_pdf_text(file_path)
            return ToolResult(success=True, data=res)
        except Exception as e:
            logger.exception("pdf_reading_failed", path=file_path)
            return ToolResult(success=False, error=str(e))
