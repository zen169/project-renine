"""Retrieval module for semantic search using BGE-M3 and ChromaDB.

Handles embedding generation and persistent vector storage/retrieval.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb
import torch
from sentence_transformers import SentenceTransformer

from renine.core.config import get_memory_config, get_project_root, get_settings

logger = logging.getLogger("renine.memory.retrieval")

# Global caches
_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None


def get_embedding_model() -> SentenceTransformer:
    """Load and return the BGE-M3 embedding model from cache or disk.

    Returns:
        The SentenceTransformer model.
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    config = get_memory_config()
    emb_config = config.get("memory", {}).get("embedding", {})
    model_name = emb_config.get("model_name", "BAAI/bge-m3")
    device = emb_config.get("device", "cpu")

    # Fallback if CUDA requested but not available
    if device == "cuda" and not torch.cuda.is_available():
        logger.warning(
            "CUDA is not available, falling back to CPU for embedding model",
        )
        device = "cpu"

    logger.info("Initializing embedding model %s on %s", model_name, device)
    _embedding_model = SentenceTransformer(model_name, device=device)
    return _embedding_model


def get_chroma_client() -> chromadb.PersistentClient:
    """Return the cached persistent ChromaDB client.

    Returns:
        The chromadb PersistentClient.
    """
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    # Read chroma directory from settings databases section
    settings = get_settings()
    chroma_dir_rel = settings.get("databases", {}).get("chroma_dir", "data/chroma")
    project_root = get_project_root()
    chroma_path = (project_root / chroma_dir_rel).resolve()
    chroma_path.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing ChromaDB persistent client at %s", chroma_path)
    _chroma_client = chromadb.PersistentClient(path=chroma_path.as_posix())
    return _chroma_client


def add_to_vector_store(
    collection_name: str,
    id_: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Embed text and store it in the specified ChromaDB collection.

    Args:
        collection_name: Name of the collection.
        id_: Unique identifier for the document.
        text: The text content to embed and store.
        metadata: Optional dictionary of metadata.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name=collection_name)
    model = get_embedding_model()

    config = get_memory_config()
    emb_config = config.get("memory", {}).get("embedding", {})
    batch_size = emb_config.get("batch_size", 32)

    embedding = model.encode(
        [text], batch_size=batch_size, convert_to_numpy=True,
    )[0].tolist()

    collection.add(
        ids=[id_],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata or {}],
    )


def delete_from_vector_store(collection_name: str, id_: str) -> None:
    """Delete a document from the specified ChromaDB collection by its ID.

    Args:
        collection_name: Name of the collection.
        id_: Unique identifier of the document to delete.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name=collection_name)
    collection.delete(ids=[id_])


def search_vector_store(
    collection_name: str,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Perform semantic search on the specified ChromaDB collection.

    Args:
        collection_name: Name of the collection.
        query: Query text.
        limit: Max number of results to return.

    Returns:
        List of result dicts, each with keys: id, document, metadata, distance.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name=collection_name)
    model = get_embedding_model()

    config = get_memory_config()
    emb_config = config.get("memory", {}).get("embedding", {})
    batch_size = emb_config.get("batch_size", 32)

    query_embedding = model.encode(
        [query], batch_size=batch_size, convert_to_numpy=True,
    )[0].tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
    )

    out = []
    if not results or not results["ids"] or not results["ids"][0]:
        return out

    for i in range(len(results["ids"][0])):
        out.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i] if results["distances"] else 0.0,
        })
    return out
