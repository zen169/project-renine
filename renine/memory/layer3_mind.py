"""Layer 3 memory: structured local mind database.

Dual-storage engine utilizing SQLite for relational storage of namespace facts
and ChromaDB for semantic search of those facts.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from renine.core.config import get_memory_config
from renine.databases.models.mind import MindRecord
from renine.databases.session import get_session
from renine.memory.retrieval import (
    add_to_vector_store,
    delete_from_vector_store,
    search_vector_store,
)

logger = logging.getLogger("renine.memory.layer3_mind")


def _get_collection_name(namespace: str) -> str:
    """Get the ChromaDB collection name for the namespace."""
    config = get_memory_config()
    prefix = (
        config.get("memory", {})
        .get("layer3", {})
        .get("chroma_collection_prefix", "mind_")
    )
    return f"{prefix}{namespace}"


def _validate_namespace(namespace: str) -> None:
    """Validate that the namespace is defined in memory configuration."""
    config = get_memory_config()
    valid_namespaces = (
        config.get("memory", {}).get("layer3", {}).get("namespaces", [])
    )
    if namespace not in valid_namespaces:
        msg = (
            f"Invalid mind namespace: {namespace}. "
            f"Valid options: {valid_namespaces}"
        )
        raise ValueError(msg)


def store_fact(
    namespace: str,
    key: str,
    value: dict[str, Any],
    summary: str,
) -> MindRecord:
    """Store or update a structured fact in SQLite and ChromaDB.

    Args:
        namespace: The logical namespace (e.g. 'inventory').
        key: The key identifier for the fact.
        value: The dictionary payload.
        summary: Human-readable summary for semantic search.

    Returns:
        The stored MindRecord ORM model.
    """
    _validate_namespace(namespace)

    db = get_session("mind_db")
    try:
        stmt = select(MindRecord).where(
            MindRecord.namespace == namespace, MindRecord.key == key
        )
        record = db.scalars(stmt).first()

        if record:
            record.value = value
            record.summary = summary
        else:
            record = MindRecord(
                namespace=namespace,
                key=key,
                value=value,
                summary=summary,
            )
            db.add(record)

        db.commit()
        db.refresh(record)

        collection = _get_collection_name(namespace)
        chroma_id = f"{namespace}:{key}"
        add_to_vector_store(
            collection_name=collection,
            id_=chroma_id,
            text=summary,
            metadata={"namespace": namespace, "key": key},
        )
        logger.info("Stored fact '%s' in namespace '%s'", key, namespace)
        return record
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_fact(namespace: str, key: str) -> MindRecord | None:
    """Retrieve a fact by namespace and key.

    Args:
        namespace: The namespace.
        key: The key.

    Returns:
        MindRecord or None.
    """
    _validate_namespace(namespace)
    db = get_session("mind_db")
    try:
        stmt = select(MindRecord).where(
            MindRecord.namespace == namespace, MindRecord.key == key
        )
        return db.scalars(stmt).first()
    finally:
        db.close()


def delete_fact(namespace: str, key: str) -> bool:
    """Delete a fact by namespace and key from both SQLite and ChromaDB.

    Args:
        namespace: The namespace.
        key: The key.

    Returns:
        True if deleted, False if not found.
    """
    _validate_namespace(namespace)
    db = get_session("mind_db")
    try:
        stmt = select(MindRecord).where(
            MindRecord.namespace == namespace, MindRecord.key == key
        )
        record = db.scalars(stmt).first()
        if not record:
            return False

        db.delete(record)
        db.commit()

        collection = _get_collection_name(namespace)
        chroma_id = f"{namespace}:{key}"
        delete_from_vector_store(collection, chroma_id)

        logger.info("Deleted fact '%s' from namespace '%s'", key, namespace)
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_facts(namespace: str) -> list[MindRecord]:
    """List all facts in a namespace.

    Args:
        namespace: The namespace.

    Returns:
        List of MindRecord models.
    """
    _validate_namespace(namespace)
    db = get_session("mind_db")
    try:
        stmt = select(MindRecord).where(MindRecord.namespace == namespace)
        return list(db.scalars(stmt).all())
    finally:
        db.close()


def search_facts(
    namespace: str,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Semantically search facts in a namespace using ChromaDB.

    Args:
        namespace: The namespace.
        query: Semantic search query.
        limit: Max results.

    Returns:
        List of dicts containing the fact details.
    """
    _validate_namespace(namespace)
    collection = _get_collection_name(namespace)
    chroma_results = search_vector_store(collection, query, limit)

    out = []
    db = get_session("mind_db")
    try:
        for res in chroma_results:
            key = res["metadata"].get("key")
            stmt = select(MindRecord).where(
                MindRecord.namespace == namespace, MindRecord.key == key
            )
            record = db.scalars(stmt).first()
            if record:
                out.append({
                    "key": record.key,
                    "value": record.value,
                    "summary": record.summary,
                    "distance": res["distance"],
                })
        return out
    finally:
        db.close()
