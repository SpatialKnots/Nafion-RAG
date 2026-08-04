from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection

EmbeddingProvider = Callable[[list[str], int], list[Any]]
VECTOR_EMBEDDINGS_FILENAME = "embeddings.npy"
VECTOR_CHUNK_IDS_FILENAME = "chunk_ids.json"
VECTOR_MANIFEST_FILENAME = "manifest.json"
VECTOR_INDEX_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class LoadedVectorIndex:
    embeddings: Any
    chunk_ids: list[str]
    rows_by_chunk_id: dict[str, tuple[Chunk, Article]]
    manifest: dict[str, Any]
    manifest_sha256: str


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


def vector_index_dir(data_root: Path, embedding_model: str) -> Path:
    return data_root / "processed" / "vector_indexes" / safe_index_name(embedding_model)


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


@lru_cache(maxsize=4)
def _fastembed_model(embedding_model: str) -> Any:
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=embedding_model)


def _embed_with_fastembed(texts: list[str], batch_size: int, embedding_model: str) -> list[Any]:
    return list(_fastembed_model(embedding_model).passage_embed(texts, batch_size=batch_size))


def embed_query_with_fastembed(query: str, embedding_model: str) -> Any:
    vectors = list(_fastembed_model(embedding_model).query_embed([query]))
    if len(vectors) != 1:
        raise ValueError(f"query embedding provider returned {len(vectors)} vectors")
    return vectors[0]


def _collection_chunk_rows(session: Session, collection: Collection) -> list[tuple[Chunk, Article]]:
    return list(
        session.execute(
            select(Chunk, Article)
            .join(Article, Chunk.article_id == Article.id)
            .where(Article.collection_id == collection.id)
            .order_by(Article.checksum_sha256, Chunk.chunk_index, Chunk.id)
        )
        .tuples()
        .all()
    )


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

    rows = _collection_chunk_rows(session, db_collection)
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
        "schema_version": VECTOR_INDEX_SCHEMA_VERSION,
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
        "similarity": "cosine",
        "vectors_normalized": True,
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
    rows = _collection_chunk_rows(session, db_collection)
    texts = [chunk.text for chunk, _article in rows]
    chunk_ids = [str(chunk.id) for chunk, _article in rows]
    provider = embedder or (lambda documents, size: _embed_with_fastembed(documents, size, embedding_model))
    vectors = provider(texts, batch_size)
    if len(vectors) != len(texts):
        raise ValueError(f"embedding provider returned {len(vectors)} vectors for {len(texts)} chunks")

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
        if not np.isfinite(matrix).all():
            raise ValueError("embedding provider returned NaN or infinite values")
        norms = np.linalg.norm(matrix, axis=1)
        if np.any(norms == 0):
            raise ValueError("embedding provider returned a zero-length vector")
        matrix = matrix / norms[:, np.newaxis]
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

    manifest_chunk_ids = [str(item["chunk_id"]) for item in manifest["chunks"]]
    if manifest_chunk_ids != chunk_ids:
        raise ValueError("vector manifest chunk order does not match embedding order")

    index_dir = vector_index_dir(data_root, embedding_model)
    index_dir.mkdir(parents=True, exist_ok=True)
    embeddings_path = index_dir / VECTOR_EMBEDDINGS_FILENAME
    chunk_ids_path = index_dir / VECTOR_CHUNK_IDS_FILENAME
    np.save(embeddings_path, matrix.astype(np.float32, copy=False))
    chunk_ids_path.write_text(json.dumps(chunk_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["index_files"] = [
        {"name": VECTOR_EMBEDDINGS_FILENAME, "sha256": _file_sha256(embeddings_path)},
        {"name": VECTOR_CHUNK_IDS_FILENAME, "sha256": _file_sha256(chunk_ids_path)},
    ]
    return write_vector_index_manifest(manifest, data_root)


def write_vector_index_manifest(manifest: dict[str, Any], data_root: Path) -> Path:
    index_dir = vector_index_dir(data_root, str(manifest["embedding_model"]))
    index_dir.mkdir(parents=True, exist_ok=True)
    output_path = index_dir / VECTOR_MANIFEST_FILENAME
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _index_error(message: str, embedding_model: str, collection: str) -> ValueError:
    command = f"python -m app.retrieval.cli build --embedding-model {embedding_model} --collection {collection}"
    return ValueError(f"Invalid local vector index: {message}. Rebuild it with: {command}")


def _read_json(path: Path, description: str, embedding_model: str, collection: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _index_error(f"cannot read {description} at {path}: {exc}", embedding_model, collection) from exc


def load_local_vector_index(
    session: Session,
    *,
    data_root: Path,
    collection: str,
    embedding_model: str,
) -> LoadedVectorIndex:
    db_collection = session.scalar(select(Collection).where(Collection.name == collection))
    if db_collection is None:
        raise ValueError(f"Unknown collection: {collection}")

    index_dir = vector_index_dir(data_root, embedding_model)
    manifest_path = index_dir / VECTOR_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise _index_error(f"missing {manifest_path}", embedding_model, collection)
    manifest = _read_json(manifest_path, "manifest", embedding_model, collection)
    if not isinstance(manifest, dict):
        raise _index_error("manifest root must be an object", embedding_model, collection)
    if manifest.get("schema_version") != VECTOR_INDEX_SCHEMA_VERSION:
        raise _index_error(
            f"unsupported manifest schema_version {manifest.get('schema_version')!r}; expected {VECTOR_INDEX_SCHEMA_VERSION}",
            embedding_model,
            collection,
        )
    expected_values = {
        "status": "built",
        "backend": "local_vector_index",
        "collection": collection,
        "embedding_model": embedding_model,
        "similarity": "cosine",
        "vectors_normalized": True,
    }
    for field, expected in expected_values.items():
        if manifest.get(field) != expected:
            raise _index_error(f"manifest {field} must be {expected!r}", embedding_model, collection)

    dimension = manifest.get("embedding_dimension")
    chunk_count = manifest.get("chunk_count")
    chunks = manifest.get("chunks")
    if not isinstance(dimension, int) or dimension <= 0:
        raise _index_error("manifest embedding_dimension must be positive", embedding_model, collection)
    if not isinstance(chunk_count, int) or chunk_count < 0:
        raise _index_error("manifest chunk_count must be non-negative", embedding_model, collection)
    if not isinstance(chunks, list) or len(chunks) != chunk_count or not all(isinstance(item, dict) for item in chunks):
        raise _index_error("manifest chunks do not match chunk_count", embedding_model, collection)

    file_entries = manifest.get("index_files")
    if not isinstance(file_entries, list):
        raise _index_error("manifest index_files must be a list", embedding_model, collection)
    checksums: dict[str, str] = {}
    for entry in file_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("sha256"), str):
            raise _index_error("manifest index_files entries must contain name and sha256", embedding_model, collection)
        checksums[str(entry["name"])] = str(entry["sha256"])
    for filename in (VECTOR_EMBEDDINGS_FILENAME, VECTOR_CHUNK_IDS_FILENAME):
        artifact_path = index_dir / filename
        if not artifact_path.is_file():
            raise _index_error(f"missing {artifact_path}", embedding_model, collection)
        if checksums.get(filename) != _file_sha256(artifact_path):
            raise _index_error(f"checksum mismatch for {filename}", embedding_model, collection)

    chunk_ids_payload = _read_json(index_dir / VECTOR_CHUNK_IDS_FILENAME, "chunk id file", embedding_model, collection)
    if not isinstance(chunk_ids_payload, list) or not all(isinstance(item, str) for item in chunk_ids_payload):
        raise _index_error("chunk_ids.json must contain a list of strings", embedding_model, collection)
    chunk_ids = list(chunk_ids_payload)
    if len(chunk_ids) != chunk_count or len(set(chunk_ids)) != len(chunk_ids):
        raise _index_error("chunk id count or uniqueness does not match manifest", embedding_model, collection)
    manifest_chunk_ids = [str(item.get("chunk_id")) for item in chunks]
    if chunk_ids != manifest_chunk_ids:
        raise _index_error("chunk id order does not match manifest", embedding_model, collection)
    try:
        parsed_chunk_ids = [UUID(chunk_id) for chunk_id in chunk_ids]
    except ValueError as exc:
        raise _index_error("chunk_ids.json contains an invalid UUID", embedding_model, collection) from exc

    try:
        embeddings = np.load(index_dir / VECTOR_EMBEDDINGS_FILENAME, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise _index_error(f"cannot load embeddings.npy: {exc}", embedding_model, collection) from exc
    if embeddings.ndim != 2 or embeddings.shape != (chunk_count, dimension):
        raise _index_error(
            f"embedding matrix shape {embeddings.shape} does not match {(chunk_count, dimension)}",
            embedding_model,
            collection,
        )
    if not np.issubdtype(embeddings.dtype, np.floating) or not np.isfinite(embeddings).all():
        raise _index_error("embedding matrix must contain only finite floating-point values", embedding_model, collection)
    if chunk_count and not np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, rtol=1e-4, atol=1e-5):
        raise _index_error("embedding matrix rows are not cosine-normalized", embedding_model, collection)

    current_rows = _collection_chunk_rows(session, db_collection)
    current_chunk_ids = [str(chunk.id) for chunk, _article in current_rows]
    if current_chunk_ids != chunk_ids:
        raise _index_error("database chunk set or order has changed", embedding_model, collection)
    rows_by_chunk_id = {str(chunk.id): (chunk, article) for chunk, article in current_rows}
    if len(rows_by_chunk_id) != len(parsed_chunk_ids):
        raise _index_error("database chunk count has changed", embedding_model, collection)

    for metadata in chunks:
        chunk_id = str(metadata["chunk_id"])
        chunk, article = rows_by_chunk_id[chunk_id]
        expected_metadata = {
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
        for field, expected in expected_metadata.items():
            if metadata.get(field) != expected:
                raise _index_error(f"chunk {chunk_id} metadata mismatch for {field}", embedding_model, collection)

    corpus_manifest_path = manifest.get("corpus_manifest_path")
    corpus_manifest_sha256 = manifest.get("corpus_manifest_sha256")
    if corpus_manifest_path and corpus_manifest_sha256:
        source_manifest = Path(str(corpus_manifest_path))
        if not source_manifest.is_file() or _file_sha256(source_manifest) != corpus_manifest_sha256:
            raise _index_error("corpus manifest is missing or has changed", embedding_model, collection)

    return LoadedVectorIndex(
        embeddings=embeddings,
        chunk_ids=chunk_ids,
        rows_by_chunk_id=rows_by_chunk_id,
        manifest=manifest,
        manifest_sha256=_file_sha256(manifest_path),
    )
