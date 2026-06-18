"""Coding agent for Renine.

Provides coding assistance including code explanation, generation, and debugging
using local Ollama client, with optional file-reading capability.
"""
from __future__ import annotations

from typing import Any

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.brain.ollama_client import chat, check_connection
from renine.core.logging_config import get_logger
from renine.tools.executor import execute_tool
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)

_CODING_SYSTEM_PROMPT = (
    "You are a senior software engineering assistant. Help the user write, debug, "
    "or explain code. Provide clear explanations and clean, well-formatted code blocks."
)


def _call_ollama(prompt: str, system_prompt: str) -> str:
    """Helper to query Ollama safely.

    Args:
        prompt: User prompt.
        system_prompt: System instructions.

    Returns:
        Ollama response or fallback message.
    """
    if not check_connection():
        logger.warning("ollama_offline_using_fallback")
        return "I'm sorry, but my local AI model (Ollama) is currently offline."

    try:
        messages = [{"role": "user", "content": prompt}]
        return chat(messages=messages, system_prompt=system_prompt)
    except Exception as e:
        logger.exception("ollama_query_failed")
        return f"Error communicating with local AI model: {e}"


def _read_target_file(file_path: str) -> str | None:
    """Helper to read code file content using the file_reader tool.

    Args:
        file_path: File path to read.

    Returns:
        File content string or None if reading failed.
    """
    res = execute_tool("file_reader", PermissionLevel.READ_ONLY, file_path=file_path)
    if res.success and isinstance(res.data, dict):
        return res.data.get("text")
    return None


class CodingAgent(BaseAgent):
    """Agent that assists with code generation, explanation, and debugging."""

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the CodingAgent."""
        return AgentManifest(
            name="coding",
            description="Assists with code generation, explanation, and debugging",
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
        """Process coding questions or requests.

        Args:
            user_input: The user instruction.
            context: Conversation history context.
            metadata: Additional metadata.

        Returns:
            Processing result dictionary.
        """
        query = user_input.lower().strip()
        file_path = None

        # Look for simple file paths to read and explain/debug
        if "file" in query or "code in" in query:
            words = user_input.split()
            for w in words:
                if "/" in w or "\\" in w or w.endswith((".py", ".js", ".ts", ".txt", ".cpp", ".h")):
                    file_path = w.strip(".,'\"")
                    break

        prompt = user_input
        if file_path:
            content = _read_target_file(file_path)
            if content:
                prompt = (
                    f"Here is the content of the file '{file_path}':\n\n"
                    f"```\n{content}\n```\n\n"
                    f"User request: {user_input}"
                )

        response_text = _call_ollama(prompt, _CODING_SYSTEM_PROMPT)

        return {
            "content": response_text,
            "success": "offline" not in response_text.lower(),
            "source_agent": "coding",
            "file_read": file_path if file_path and content else None,
        }
