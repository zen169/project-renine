"""Spreadsheet agent for Renine.

Analyzes Excel and CSV files using pandas, offering basic statistics
and natural language query capability backed by Ollama.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.brain.ollama_client import chat, check_connection
from renine.core.logging_config import get_logger
from renine.security.input_validator import validate_path
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)


def _load_data_frame(path: Path) -> pd.DataFrame:
    """Load Excel or CSV file into a pandas DataFrame.

    Args:
        path: Path object to the file.

    Returns:
        Loaded DataFrame.

    Raises:
        ValueError: If the file type is unsupported.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported spreadsheet format: '{suffix}'. Only CSV/Excel supported.")


def _generate_fallback_summary(df: pd.DataFrame) -> str:
    """Generate a text summary of the DataFrame when LLM is offline.

    Args:
        df: The loaded DataFrame.

    Returns:
        Summary description string.
    """
    summary = [
        f"Spreadsheet contains {df.shape[0]} rows and {df.shape[1]} columns.",
        f"Columns: {', '.join(df.columns)}",
        "\nData description:",
        str(df.describe(include="all")),
    ]
    return "\n".join(summary)


def _query_llm_about_data(user_query: str, df: pd.DataFrame) -> str:
    """Ask Ollama about the spreadsheet content.

    Args:
        user_query: Original user query.
        df: Loaded DataFrame.

    Returns:
        LLM answer.
    """
    if not check_connection():
        logger.warning("ollama_offline_spreadsheet_fallback")
        return _generate_fallback_summary(df)

    data_summary = (
        f"Shape: {df.shape}\n"
        f"Columns: {list(df.columns)}\n"
        f"Sample Data:\n{df.head(5).to_string()}\n"
        f"Stats:\n{df.describe(include='all').to_string()}"
    )

    system_prompt = (
        "You are a spreadsheet analysis helper. Answer the user's question about the "
        "provided data. Be concise and reference key numbers in the data."
    )
    prompt = (
        f"Spreadsheet Data Summary:\n{data_summary}\n\n"
        f"User Question: {user_query}"
    )

    try:
        messages = [{"role": "user", "content": prompt}]
        return chat(messages=messages, system_prompt=system_prompt)
    except Exception as e:
        logger.exception("ollama_spreadsheet_query_failed")
        return f"Error communicating with local AI model: {e}"


class SpreadsheetAgent(BaseAgent):
    """Agent that handles CSV and Excel analysis."""

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the SpreadsheetAgent."""
        return AgentManifest(
            name="spreadsheet",
            description="Analyzes Excel and CSV files using pandas",
            required_tools=["file_reader"],
            memory_access_level=MemoryAccessLevel.LAYER1_AND_2,
            permission_level=PermissionLevel.READ_ONLY,
            active_phase=4,
        )

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process Excel/CSV files and answer user questions.

        Args:
            user_input: User question.
            context: Conversation history context.
            metadata: Metadata dictionary.

        Returns:
            Result dictionary.
        """
        query = user_input.lower().strip()
        file_path_str = ""

        # Extract file path
        for word in user_input.split():
            word_clean = word.strip(".,'\"?!=:;()[]{}")
            if "/" in word_clean or "\\" in word_clean or word_clean.endswith((".csv", ".xlsx", ".xls")):
                file_path_str = word_clean
                break

        if not file_path_str:
            return {
                "content": "Please specify a spreadsheet file path (.csv, .xlsx, .xls) to analyze.",
                "success": False,
                "source_agent": "spreadsheet",
            }

        try:
            path = validate_path(file_path_str)
            if not path.exists():
                return {
                    "content": f"File not found: {file_path_str}",
                    "success": False,
                    "source_agent": "spreadsheet",
                }

            df = _load_data_frame(path)

            if "columns" in query:
                content = f"Columns: {', '.join(df.columns)}"
            elif "summary" in query or "describe" in query:
                content = _generate_fallback_summary(df)
            else:
                content = _query_llm_about_data(user_input, df)

            return {
                "content": content,
                "success": True,
                "source_agent": "spreadsheet",
                "shape": df.shape,
            }

        except Exception as e:
            logger.exception("spreadsheet_agent_process_failed", path=file_path_str)
            return {
                "content": f"Failed to analyze spreadsheet: {e}",
                "success": False,
                "error": str(e),
                "source_agent": "spreadsheet",
            }
