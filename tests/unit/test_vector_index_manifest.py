from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.retrieval.vector_index import (
    build_vector_index_manifest,
    chunk_text_checksum,
    safe_index_name,
    write_vector_index_manifest,
)


class FakeSession:
    def __init__(self, collection: object | None, rows: list[tuple[object, object]]) -> None:
        self.collection = collection
        self.rows = rows

    def scalar(self, statement: object) -> object | None:
        return self.collection

    def execute(self, statement: object) -> object:
        return SimpleNamespace(all=lambda: self.rows)


def test_chunk_text_checksum_is_stable() -> None:
    assert chunk_text_checksum("Nafion chunk text") == chunk_text_checksum("Nafion chunk text")
    assert chunk_text_checksum("Nafion chunk text") != chunk_text_checksum("different text")


def test_safe_index_name_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="embedding model"):
        safe_index_name(" / ")


def test_build_vector_index_manifest_records_chunk_evidence(tmp_path) -> None:
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    article = SimpleNamespace(
        id=uuid.uuid4(),
        collection_id=collection.id,
        checksum_sha256="article-checksum",
    )
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=article.id,
        chunk_index=3,
        page_start=4,
        page_end=5,
        source_type="method",
        text_layer="ocr",
        char_count=17,
        text="Li-Nafion evidence",
    )
    corpus_manifest = tmp_path / "corpus_manifest.json"
    corpus_manifest.write_text('{"articles": []}', encoding="utf-8")

    payload = build_vector_index_manifest(
        FakeSession(collection, [(chunk, article)]),  # type: ignore[arg-type]
        collection="literature",
        embedding_model="test/model",
        embedding_dimension=384,
        backend="local_vector_index",
        corpus_manifest_path=corpus_manifest,
        build_command="build command",
        created_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert payload["schema_version"] == 1
    assert payload["status"] == "manifest_only"
    assert payload["backend"] == "local_vector_index"
    assert payload["collection"] == "literature"
    assert payload["embedding_model"] == "test/model"
    assert payload["embedding_dimension"] == 384
    assert payload["chunk_count"] == 1
    assert payload["article_checksums"] == ["article-checksum"]
    assert payload["corpus_manifest_path"] == str(corpus_manifest)
    assert payload["corpus_manifest_sha256"]
    assert payload["chunks"][0]["chunk_id"] == str(chunk.id)
    assert payload["chunks"][0]["source_text_checksum_sha256"] == chunk_text_checksum(chunk.text)


def test_build_vector_index_manifest_rejects_unknown_collection() -> None:
    with pytest.raises(ValueError, match="Unknown collection"):
        build_vector_index_manifest(
            FakeSession(None, []),  # type: ignore[arg-type]
            collection="missing",
            embedding_model="test-model",
            embedding_dimension=384,
            backend="local_vector_index",
        )


def test_write_vector_index_manifest_uses_model_directory(tmp_path) -> None:
    payload = {
        "embedding_model": "BAAI/bge-m3",
        "chunk_count": 0,
    }

    output_path = write_vector_index_manifest(payload, tmp_path)

    assert output_path == tmp_path / "processed" / "vector_indexes" / "BAAI_bge-m3" / "manifest.json"
    assert json.loads(output_path.read_text(encoding="utf-8"))["embedding_model"] == "BAAI/bge-m3"
