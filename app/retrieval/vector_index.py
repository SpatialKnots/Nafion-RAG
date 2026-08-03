from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection

EmbeddingProvider = Callable[[list[str], int], list[Any]]
VECTOR_EMBEDDINGS_FILENAME = "embeddings.npy"
VECTOR_CHUNK_IDS_FILENAME = "chunk_ids.json"


def chunk_text_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_index_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = normalized.strip("._-")
    if not normalized:
        raise ValueError("embedding model must produce a non-empty index name")
    return normalized


def _dependency_versions() -> dict[str, str | None]:
    packages = ["fastembed", "numpy", "onnxruntime"]
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def fastembed_model_dimension(embedding_model: str) -> int | None:
    from fastembed import TextEmbedding

    for model in TextEmbedding.list_supported_models():
        if model.get("model") == embedding_model:
            dimension = model.get("dim")
            return dimension if isinstance(dimension, int) else None
    return None


def _embed_with_fastembed(texts: list[str], batch_size: int, embedding_model: str) -> list[Any]:
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=embedding_model)
    return list(model.embed(texts, batch_size=batch_size))


def build_vector_index_manifest(
    session: Session,
    *,
    collection: str,
    embedding_model: str,
    embedding_dimension: int,
    backend: str,
    corpus_manifest_path: Path | None = None,
    build_command: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    if embedding_dimension <= 0:
        raise ValueError("embedding_dimension must be positive")
    if not backend.strip():
        raise ValueError("backend must not be empty")

    db_collection = session.scalar(select(Collection).where(Collection.name == collection))
    if db_collection is None:
        raise ValueError(f"Unknown collection: {collection}")

    rows = session.execute(
        select(Chunk, Article)
        .join(Article, Chunk.article_id == Article.id)
        .where(Article.collection_id == db_collection.id)
        .order_by(Article.title, Chunk.chunk_index)
    ).all()
    chunks = []
    article_checksums = set()
    for chunk, article in rows:
        article_checksums.add(article.checksum_sha256)
        chunks.append(
            {
                "chunk_id": str(chunk.id),
                "article_id": str(article.id),
                "article_checksum_sha256": article.checksum_sha256,
                "chunk_index": chunk.chunk_index,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "source_type": chunk.source_type,
                "text_layer": chunk.text_layer,
                "char_count": chunk.char_count,
                "source_text_checksum_sha256": chunk_text_checksum(chunk.text),
            }
        )

    manifest_path = corpus_manifest_path if corpus_manifest_path and corpus_manifest_path.exists() else None
    return {
        "schema_version": 1,
        "status": "manifest_only",
        "backend": backend.strip(),
        "collection": collection,
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
        "build_command": build_command,
        "corpus_manifest_path": str(manifest_path) if manifest_path else None,
        "corpus_manifest_sha256": _file_sha256(manifest_path) if manifest_path else None,
        "article_checksums": sorted(article_checksums),
        "chunk_count": len(chunks),
        "chunks": chunks,
        "index_files": [],
    }


def build_local_vector_index(
    session: Session,
    *,
    data_root: Path,
    collection: str,
    embedding_model: str,
    backend: str = "local_vector_index",
    corpus_manifest_path: Path | None = None,
    build_command: str | None = None,
    batch_size: int = 64,
    embedding_dimension: int | None = None,
    embedder: EmbeddingProvider | None = None,
) -> Path:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    db_collection = session.scalar(select(Collection).where(Collection.name == collection))
    if db_collection is None:
        raise ValueError(f"Unknown collection: {collection}")
    rows = session.execute(
        select(Chunk, Article)
        .join(Article, Chunk.article_id == Article.id)
        .where(Article.collection_id == db_collection.id)
        .order_by(Article.title, Chunk.chunk_index)
    ).all()
    texts = [chunk.text for chunk, _article in rows]
    chunk_ids = [str(chunk.id) for chunk, _article in rows]
    provider = embedder or (lambda documents, size: _embed_with_fastembed(documents, size, embedding_model))
    vectors = provider(texts, batch_size)
    if len(vectors) != len(texts):
        raise ValueError(f"embedding provider returned {len(vectors)} vectors for {len(texts)} chunks")

    import numpy as np

    expected_dimension = embedding_dimension or fastembed_model_dimension(embedding_model)
    if vectors:
        vector_arrays = []
        for vector in vectors:
            array = np.asarray(vector, dtype=np.float32)
            if array.ndim != 1:
                raise ValueError("embedding provider returned a non-1D vector")
            vector_arrays.append(array)
        dimensions = {int(array.shape[0]) for array in vector_arrays}
        if len(dimensions) != 1:
            raise ValueError("embedding provider returned vectors with inconsistent dimensions")
        actual_dimension = dimensions.pop()
        if expected_dimension is not None and actual_dimension != expected_dimension:
            raise ValueError(f"embedding dimension mismatch: expected {expected_dimension}, got {actual_dimension}")
        matrix = np.vstack(vector_arrays)
    else:
        if expected_dimension is None:
            raise ValueError("embedding_dimension is required when the collection has no chunks")
        actual_dimension = expected_dimension
        matrix = np.empty((0, actual_dimension), dtype=np.float32)

    manifest = build_vector_index_manifest(
        session,
        collection=collection,
        embedding_model=embedding_model,
        embedding_dimension=actual_dimension,
        backend=backend,
        corpus_manifest_path=corpus_manifest_path,
        build_command=build_command,
    )
    manifest["status"] = "built"
    manifest["batch_size"] = batch_size
    manifest["software_versions"] = _dependency_versions()
    manifest["index_files"] = [VECTOR_EMBEDDINGS_FILENAME, VECTOR_CHUNK_IDS_FILENAME]

    index_name = safe_index_name(embedding_model)
    index_dir = data_root / "processed" / "vector_indexes" / index_name
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / VECTOR_EMBEDDINGS_FILENAME, matrix)
    (index_dir / VECTOR_CHUNK_IDS_FILENAME).write_text(json.dumps(chunk_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    return write_vector_index_manifest(manifest, data_root)


def write_vector_index_manifest(manifest: dict[str, Any], data_root: Path) -> Path:
    index_name = safe_index_name(str(manifest["embedding_model"]))
    index_dir = data_root / "processed" / "vector_indexes" / index_name
    index_dir.mkdir(parents=True, exist_ok=True)
    output_path = index_dir / "manifest.json"
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
