"""Tests for file_reader and pdf_reader tools."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import docx
import fitz
import pytest

from renine.tools.files.file_reader import FileReaderTool
from renine.tools.files.pdf_reader import PDFReaderTool


@pytest.fixture
def mock_filesystem_sec_config(tmp_path: Path):
    """Mock security settings for filesystem read."""
    config = {
        "security": {
            "filesystem": {
                "allowed_paths": [str(tmp_path)],
                "blocked_paths": [],
                "max_read_size_bytes": 1000000,
            }
        }
    }
    # Patch get_security_config in both file_reader and pdf_reader
    with patch("renine.tools.files.file_reader.get_security_config", return_value=config), \
         patch("renine.tools.files.pdf_reader.get_security_config", return_value=config), \
         patch("renine.security.input_validator.get_security_config", return_value=config):
        yield tmp_path


def test_read_text_file(mock_filesystem_sec_config) -> None:
    """Read a standard plain text file successfully."""
    tmp_path = mock_filesystem_sec_config
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello Text File", encoding="utf-8")

    tool = FileReaderTool()
    result = tool.execute(file_path=str(txt_file))

    assert result.success is True
    assert result.data["text"] == "Hello Text File"
    assert result.data["type"] == "text"


def test_read_docx_file(mock_filesystem_sec_config) -> None:
    """Read a DOCX document successfully."""
    tmp_path = mock_filesystem_sec_config
    docx_file = tmp_path / "test.docx"

    doc = docx.Document()
    doc.add_paragraph("Hello DOCX World")
    doc.save(docx_file)

    tool = FileReaderTool()
    result = tool.execute(file_path=str(docx_file))

    assert result.success is True
    assert "Hello DOCX World" in result.data["text"]
    assert result.data["type"] == "docx"


def test_read_pdf_file(mock_filesystem_sec_config) -> None:
    """Read a PDF document successfully."""
    tmp_path = mock_filesystem_sec_config
    pdf_file = tmp_path / "test.pdf"

    # Create a simple PDF using PyMuPDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello PDF World")
    doc.save(str(pdf_file))
    doc.close()

    tool = PDFReaderTool()
    result = tool.execute(file_path=str(pdf_file))

    assert result.success is True
    assert "Hello PDF World" in result.data["text"]
    assert result.data["total_pages"] == 1
