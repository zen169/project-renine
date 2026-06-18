import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from renine.memory.retrieval import (
    add_to_vector_store,
    delete_from_vector_store,
    get_chroma_client,
    get_embedding_model,
    search_vector_store,
)


@pytest.fixture
def mock_sentence_transformer():
    with patch("renine.memory.retrieval.SentenceTransformer") as mock_class:
        mock_instance = MagicMock()
        mock_instance.encode.side_effect = lambda texts, **kwargs: np.zeros(
            (len(texts), 1024), dtype=np.float32
        )
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_chroma_client():
    with patch(
        "renine.memory.retrieval.chromadb.PersistentClient",
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_class.return_value = mock_client
        yield mock_client, mock_collection


@pytest.fixture(autouse=True)
def clean_globals():
    import renine.memory.retrieval as r
    r._embedding_model = None
    r._chroma_client = None
    yield
    r._embedding_model = None
    r._chroma_client = None



def test_get_embedding_model(mock_sentence_transformer):
    import renine.memory.retrieval as r

    r._embedding_model = None

    model = get_embedding_model()
    assert model == mock_sentence_transformer


def test_get_chroma_client(mock_chroma_client):
    import renine.memory.retrieval as r

    r._chroma_client = None

    client = get_chroma_client()
    assert client == mock_chroma_client[0]


def test_add_and_search_vector_store(
    mock_sentence_transformer,
    mock_chroma_client,
):
    _, mock_collection = mock_chroma_client

    add_to_vector_store(
        "test_coll", "doc1", "hello world", {"tag": "test"},
    )
    mock_collection.add.assert_called_once()

    delete_from_vector_store("test_coll", "doc1")
    mock_collection.delete.assert_called_once_with(ids=["doc1"])

    mock_collection.query.return_value = {
        "ids": [["doc1"]],
        "documents": [["hello world"]],
        "metadatas": [[{"tag": "test"}]],
        "distances": [[0.1]],
    }

    results = search_vector_store("test_coll", "hello")
    assert len(results) == 1
    assert results[0]["id"] == "doc1"
    assert results[0]["document"] == "hello world"
    assert results[0]["distance"] == 0.1
