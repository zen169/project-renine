"""File agent for Renine.

Orchestrates file operations, searches files by name/type/content,
and maintains a local database file index for fast repeat lookups.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.core.config import get_security_config
from renine.core.logging_config import get_logger
from renine.databases.models.file_index import FileIndex
from renine.databases.session import get_session
from renine.tools.executor import execute_tool
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)


def _get_file_preview(path: Path) -> str:
    """Read a small text preview of a file for indexing.

    Args:
        path: Path object to the file.

    Returns:
        Preview string or empty string.
    """
    try:
        suffix = path.suffix.lower()
        if suffix in [".txt", ".md", ".json", ".csv", ".log"]:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(500).strip()
    except Exception:
        pass
    return ""


def _update_or_create_index_record(db: Any, file_path: Path, stat: Any) -> None:
    """Create or update a file index record in the database.

    Args:
        db: SQLAlchemy session.
        file_path: Absolute file Path.
        stat: stat result for file.
    """
    last_mod = datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc)
    stmt = select(FileIndex).where(FileIndex.file_path == str(file_path))
    idx_item = db.scalars(stmt).first()

    if idx_item:
        db_dt = idx_item.last_modified
        if db_dt.tzinfo is None:
            db_dt = db_dt.replace(tzinfo=datetime.timezone.utc)
        db_ts = db_dt.timestamp()
        file_ts = last_mod.timestamp()
        if idx_item.file_size == stat.st_size and abs(db_ts - file_ts) < 1.0:
            return  # Unchanged
        idx_item.file_size = stat.st_size
        idx_item.last_modified = last_mod
        idx_item.last_indexed = datetime.datetime.now(datetime.timezone.utc)
    else:
        preview = _get_file_preview(file_path)
        idx_item = FileIndex(
            file_path=str(file_path),
            file_name=file_path.name,
            file_type=file_path.suffix.lower(),
            file_size=stat.st_size,
            last_modified=last_mod,
            summary=preview,
        )
        db.add(idx_item)


class FileAgent(BaseAgent):
    """Agent that manages files and searches using the file_index table."""

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the FileAgent."""
        return AgentManifest(
            name="file",
            description="Manages local files and searches file index",
            required_tools=["file_reader", "file_search"],
            memory_access_level=MemoryAccessLevel.FULL_ACCESS,
            permission_level=PermissionLevel.READ_ONLY,
            active_phase=4,
        )

    def index_allowed_directories(self) -> int:
        """Index all files in configured allowed paths.

        Returns:
            Number of indexed files.
        """
        sec_config = get_security_config().get("security", {})
        allowed = sec_config.get("filesystem", {}).get("allowed_paths", [])
        db = get_session("mind_db")
        count = 0
        try:
            for path_str in allowed:
                base_path = Path(path_str).resolve()
                if not base_path.is_dir():
                    continue
                for root, _, files in os.walk(base_path):
                    for name in files:
                        file_path = Path(root) / name
                        try:
                            stat = file_path.stat()
                            _update_or_create_index_record(db, file_path, stat)
                            count += 1
                        except OSError:
                            continue
            db.commit()
            logger.info("file_agent_index_completed", files_indexed=count)
            return count
        except Exception as e:
            db.rollback()
            logger.exception("file_agent_indexing_failed")
            raise e
        finally:
            db.close()

    def _search_index_db(self, query: str) -> list[dict[str, Any]]:
        """Query the file_index database table for files matching query.

        Args:
            query: Name substring to match.

        Returns:
            List of matching records as dictionaries.
        """
        db = get_session("mind_db")
        try:
            stmt = select(FileIndex).where(FileIndex.file_name.contains(query))
            items = db.scalars(stmt).all()
            return [
                {
                    "name": item.file_name,
                    "path": item.file_path,
                    "size": item.file_size,
                    "suffix": item.file_type,
                }
                for item in items
            ]
        finally:
            db.close()

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process requests to search, read, or index files.

        Args:
            user_input: The user instruction.
            context: Conversation history context.
            metadata: Additional metadata.

        Returns:
            Processing result dictionary.
        """
        try:
            query = user_input.lower().strip()

            if "index files" in query or "update index" in query:
                count = self.index_allowed_directories()
                return {
                    "content": f"Successfully indexed {count} files in allowed paths.",
                    "success": True,
                    "source_agent": "file",
                }

            if "search" in query or "find file" in query:
                term = user_input.replace("search", "").replace("find file", "").strip()
                # Use database index for fast repeat lookup first
                db_results = self._search_index_db(term)
                if db_results:
                    files_str = "\n".join(f"- {f['name']} ({f['path']})" for f in db_results)
                    return {
                        "content": f"Found matching files in index:\n{files_str}",
                        "success": True,
                        "results": db_results,
                        "source_agent": "file",
                    }
                # Fallback to file search tool
                res = execute_tool("file_search", PermissionLevel.READ_ONLY, query=term)
                return {
                    "content": f"Search tool found: {res.data}",
                    "success": res.success,
                    "error": res.error,
                    "source_agent": "file",
                }

            if "read" in query:
                path_str = user_input.replace("read", "").strip()
                res = execute_tool("file_reader", PermissionLevel.READ_ONLY, file_path=path_str)
                return {
                    "content": res.data.get("text", "") if res.success else f"Error: {res.error}",
                    "success": res.success,
                    "error": res.error,
                    "source_agent": "file",
                }

            return {
                "content": "I can index files, search files by name/content, and read file contents.",
                "success": True,
                "source_agent": "file",
            }
        except Exception as e:
            logger.exception("file_agent_process_failed")
            return {"content": "", "success": False, "error": str(e), "source_agent": "file"}
