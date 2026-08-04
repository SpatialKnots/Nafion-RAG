from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection, VectorIndexState
from app.retrieval.index_lifecycle import VECTOR_INDEX_READY

EmbeddingProvider = Callable[[list[str], int], list[Any]]
VECTOR_EMBEDDINGS_FILENAME = "embeddings.npy"
VECTOR_CHUNK_IDS_FILENAME = "chunk_ids.json"
VECTOR_MANIFEST_FILENAME = "manifest.json"
VECTOR_CURRENT_POINTER_FILENAME = "current.json"
VECTOR_INDEX_SCHEMA_VERSION = 2
VECTOR_INDEX_GENERATION_SCHEMA_VERSION = 3
VectorIndexCacheKey = tuple[str, str, str, str]


@dataclass(frozen=True)
class LoadedVectorIndex:
    embeddings: Any
    chunk_ids: list[str]
    rows_by_chunk_id: dict[str, tuple[Chunk, Article]]
    manifest: dict[str, Any]
    manifest_sha256: str


_VECTOR_INDEX_CACHE: OrderedDict[VectorIndexCacheKey, LoadedVectorIndex] = OrderedDict()


@dataclass(frozen=True)
class BuiltVectorIndexGeneration:
    root: Path
    generation_id: str
    manifest_path: Path
    current_pointer_path: Path
    manifest_sha256: str
    target_revision: int
    corpus_fingerprint_sha256: str


class VectorIndexUnavailableError(ValueError):
    pass


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


def vector_index_generation_root(data_root: Path, collection: str, embedding_model: str) -> Path:
    return data_root / "processed" / "vector_indexes" / safe_index_name(collection) / safe_index_name(embedding_model)


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


def _chunk_manifest_items(rows: list[tuple[Chunk, Article]]) -> tuple[list[dict[str, Any]], list[str]]:
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
    return chunks, sorted(article_checksums)


def corpus_fingerprint_sha256(chunks: list[dict[str, Any]]) -> str:
    canonical = json.dumps(chunks, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    chunks, article_checksums = _chunk_manifest_items(rows)

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
        "article_checksums": article_checksums,
        "chunk_count": len(chunks),
        "chunks": chunks,
        "similarity": "cosine",
        "vectors_normalized": True,
        "index_files": [],
    }


def build_vector_index_generation_manifest(
    session: Session,
    *,
    collection: str,
    embedding_model: str,
    embedding_dimension: int,
    generation_id: str,
    build_id: str,
    target_revision: int,
    backend: str = "local_vector_index",
    build_command: str | None = None,
    batch_size: int = 64,
    snapshot_created_at: datetime | None = None,
    build_started_at: datetime | None = None,
    build_finished_at: datetime | None = None,
) -> dict[str, Any]:
    if embedding_dimension <= 0:
        raise ValueError("embedding_dimension must be positive")
    if target_revision < 0:
        raise ValueError("target_revision must be non-negative")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    db_collection = session.scalar(select(Collection).where(Collection.name == collection))
    if db_collection is None:
        raise ValueError(f"Unknown collection: {collection}")

    rows = _collection_chunk_rows(session, db_collection)
    chunks, article_checksums = _chunk_manifest_items(rows)
    now = datetime.now(UTC)
    return {
        "schema_version": VECTOR_INDEX_GENERATION_SCHEMA_VERSION,
        "status": "built",
        "backend": backend.strip(),
        "collection": collection,
        "collection_id": str(db_collection.id),
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "generation_id": generation_id,
        "build_id": build_id,
        "target_revision": target_revision,
        "corpus_fingerprint_sha256": corpus_fingerprint_sha256(chunks),
        "snapshot_created_at": (snapshot_created_at or now).isoformat(),
        "build_started_at": (build_started_at or now).isoformat(),
        "build_finished_at": (build_finished_at or now).isoformat(),
        "build_command": build_command,
        "batch_size": batch_size,
        "software_versions": _dependency_versions(),
        "similarity": "cosine",
        "vectors_normalized": True,
        "chunk_count": len(chunks),
        "article_checksums": article_checksums,
        "chunks": chunks,
        "index_files": [],
    }


def _normalized_embedding_matrix(
    vectors: list[Any],
    *,
    expected_dimension: int | None,
    empty_dimension: int | None,
) -> tuple[Any, int]:
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
        return matrix / norms[:, np.newaxis], actual_dimension

    if empty_dimension is None:
        raise ValueError("embedding_dimension is required when the collection has no chunks")
    return np.empty((0, empty_dimension), dtype=np.float32), empty_dimension


def _write_json(path: Path, payload: dict[str, Any] | list[str]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    _write_json(tmp_path, payload)
    with tmp_path.open("r+b") as handle:
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def build_local_vector_index_generation(
    session: Session,
    *,
    data_root: Path,
    collection: str,
    embedding_model: str,
    target_revision: int,
    backend: str = "local_vector_index",
    build_command: str | None = None,
    batch_size: int = 64,
    embedding_dimension: int | None = None,
    embedder: EmbeddingProvider | None = None,
    generation_id: str | None = None,
    build_id: str | None = None,
) -> BuiltVectorIndexGeneration:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if target_revision < 0:
        raise ValueError("target_revision must be non-negative")

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

    expected_dimension = embedding_dimension if embedder is not None else embedding_dimension or fastembed_model_dimension(embedding_model)
    matrix, actual_dimension = _normalized_embedding_matrix(
        vectors,
        expected_dimension=expected_dimension,
        empty_dimension=expected_dimension,
    )

    resolved_generation_id = generation_id or f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4()}"
    resolved_build_id = build_id or str(uuid.uuid4())
    root = vector_index_generation_root(data_root, collection, embedding_model)
    staging_dir = root / "staging" / resolved_build_id
    generation_dir = root / "generations" / resolved_generation_id
    if staging_dir.exists() or generation_dir.exists():
        raise ValueError("vector index generation id or build id already exists")
    staging_dir.mkdir(parents=True, exist_ok=False)

    try:
        embeddings_path = staging_dir / VECTOR_EMBEDDINGS_FILENAME
        chunk_ids_path = staging_dir / VECTOR_CHUNK_IDS_FILENAME
        np.save(embeddings_path, matrix.astype(np.float32, copy=False))
        _write_json(chunk_ids_path, chunk_ids)
        manifest = build_vector_index_generation_manifest(
            session,
            collection=collection,
            embedding_model=embedding_model,
            embedding_dimension=actual_dimension,
            generation_id=resolved_generation_id,
            build_id=resolved_build_id,
            target_revision=target_revision,
            backend=backend,
            build_command=build_command,
            batch_size=batch_size,
        )
        manifest_chunk_ids = [str(item["chunk_id"]) for item in manifest["chunks"]]
        if manifest_chunk_ids != chunk_ids:
            raise ValueError("vector manifest chunk order does not match embedding order")
        manifest["index_files"] = [
            {"name": VECTOR_EMBEDDINGS_FILENAME, "sha256": _file_sha256(embeddings_path)},
            {"name": VECTOR_CHUNK_IDS_FILENAME, "sha256": _file_sha256(chunk_ids_path)},
        ]
        manifest_path = staging_dir / VECTOR_MANIFEST_FILENAME
        _write_json(manifest_path, manifest)
        manifest_sha256 = _file_sha256(manifest_path)

        generation_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging_dir), str(generation_dir))
        current_pointer_path = root / VECTOR_CURRENT_POINTER_FILENAME
        _atomic_write_json(
            current_pointer_path,
            {
                "generation_id": resolved_generation_id,
                "manifest_sha256": manifest_sha256,
                "target_revision": target_revision,
            },
        )
        return BuiltVectorIndexGeneration(
            root=root,
            generation_id=resolved_generation_id,
            manifest_path=generation_dir / VECTOR_MANIFEST_FILENAME,
            current_pointer_path=current_pointer_path,
            manifest_sha256=manifest_sha256,
            target_revision=target_revision,
            corpus_fingerprint_sha256=str(manifest["corpus_fingerprint_sha256"]),
        )
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise


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

    expected_dimension = embedding_dimension if embedder is not None else embedding_dimension or fastembed_model_dimension(embedding_model)
    matrix, actual_dimension = _normalized_embedding_matrix(
        vectors,
        expected_dimension=expected_dimension,
        empty_dimension=expected_dimension,
    )

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


def _generation_error(message: str, embedding_model: str, collection: str) -> VectorIndexUnavailableError:
    return VectorIndexUnavailableError(
        f"Vector index is unavailable for collection {collection!r} and embedding model {embedding_model!r}: {message}"
    )


def _read_json(path: Path, description: str, embedding_model: str, collection: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _index_error(f"cannot read {description} at {path}: {exc}", embedding_model, collection) from exc


def _read_generation_json(path: Path, description: str, embedding_model: str, collection: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _generation_error(f"cannot read {description}", embedding_model, collection) from exc


def _load_and_validate_vector_index_files(
    session: Session,
    *,
    db_collection: Collection,
    index_dir: Path,
    manifest: dict[str, Any],
    manifest_path: Path,
    collection: str,
    embedding_model: str,
    schema_version: int,
    safe_errors: bool = False,
    use_mmap: bool = False,
) -> LoadedVectorIndex:
    def invalid(message: str) -> ValueError:
        if safe_errors:
            return _generation_error(message, embedding_model, collection)
        return _index_error(message, embedding_model, collection)

    if manifest.get("schema_version") != schema_version:
        raise invalid(f"unsupported manifest schema_version {manifest.get('schema_version')!r}; expected {schema_version}")
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
            raise invalid(f"manifest {field} must be {expected!r}")

    if schema_version == VECTOR_INDEX_GENERATION_SCHEMA_VERSION:
        if manifest.get("collection_id") != str(db_collection.id):
            raise invalid("manifest collection_id does not match database")
        if not isinstance(manifest.get("generation_id"), str) or not str(manifest.get("generation_id")).strip():
            raise invalid("manifest generation_id must be a non-empty string")
        target_revision = manifest.get("target_revision")
        if not isinstance(target_revision, int) or target_revision < 0:
            raise invalid("manifest target_revision must be non-negative")
        if not isinstance(manifest.get("corpus_fingerprint_sha256"), str):
            raise invalid("manifest corpus_fingerprint_sha256 must be a string")

    dimension = manifest.get("embedding_dimension")
    chunk_count = manifest.get("chunk_count")
    chunks = manifest.get("chunks")
    if not isinstance(dimension, int) or dimension <= 0:
        raise invalid("manifest embedding_dimension must be positive")
    if not isinstance(chunk_count, int) or chunk_count < 0:
        raise invalid("manifest chunk_count must be non-negative")
    if not isinstance(chunks, list) or len(chunks) != chunk_count or not all(isinstance(item, dict) for item in chunks):
        raise invalid("manifest chunks do not match chunk_count")

    file_entries = manifest.get("index_files")
    if not isinstance(file_entries, list):
        raise invalid("manifest index_files must be a list")
    checksums: dict[str, str] = {}
    for entry in file_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("sha256"), str):
            raise invalid("manifest index_files entries must contain name and sha256")
        checksums[str(entry["name"])] = str(entry["sha256"])
    for filename in (VECTOR_EMBEDDINGS_FILENAME, VECTOR_CHUNK_IDS_FILENAME):
        artifact_path = index_dir / filename
        if not artifact_path.is_file():
            raise invalid(f"missing {filename}")
        if checksums.get(filename) != _file_sha256(artifact_path):
            raise invalid(f"checksum mismatch for {filename}")

    chunk_ids_payload = (
        _read_generation_json(index_dir / VECTOR_CHUNK_IDS_FILENAME, "chunk id file", embedding_model, collection)
        if safe_errors
        else _read_json(index_dir / VECTOR_CHUNK_IDS_FILENAME, "chunk id file", embedding_model, collection)
    )
    if not isinstance(chunk_ids_payload, list) or not all(isinstance(item, str) for item in chunk_ids_payload):
        raise invalid("chunk_ids.json must contain a list of strings")
    chunk_ids = list(chunk_ids_payload)
    if len(chunk_ids) != chunk_count or len(set(chunk_ids)) != len(chunk_ids):
        raise invalid("chunk id count or uniqueness does not match manifest")
    manifest_chunk_ids = [str(item.get("chunk_id")) for item in chunks]
    if chunk_ids != manifest_chunk_ids:
        raise invalid("chunk id order does not match manifest")
    try:
        parsed_chunk_ids = [UUID(chunk_id) for chunk_id in chunk_ids]
    except ValueError as exc:
        raise invalid("chunk_ids.json contains an invalid UUID") from exc

    try:
        mmap_mode: Literal["r"] | None = "r" if use_mmap else None
        embeddings = np.load(index_dir / VECTOR_EMBEDDINGS_FILENAME, allow_pickle=False, mmap_mode=mmap_mode)
    except (OSError, ValueError) as exc:
        raise invalid("cannot load embeddings.npy") from exc
    if embeddings.ndim != 2 or embeddings.shape != (chunk_count, dimension):
        raise invalid(f"embedding matrix shape {embeddings.shape} does not match {(chunk_count, dimension)}")
    if not np.issubdtype(embeddings.dtype, np.floating) or not np.isfinite(embeddings).all():
        raise invalid("embedding matrix must contain only finite floating-point values")
    if chunk_count and not np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, rtol=1e-4, atol=1e-5):
        raise invalid("embedding matrix rows are not cosine-normalized")

    current_rows = _collection_chunk_rows(session, db_collection)
    current_chunk_ids = [str(chunk.id) for chunk, _article in current_rows]
    if current_chunk_ids != chunk_ids:
        raise invalid("database chunk set or order has changed")
    rows_by_chunk_id = {str(chunk.id): (chunk, article) for chunk, article in current_rows}
    if len(rows_by_chunk_id) != len(parsed_chunk_ids):
        raise invalid("database chunk count has changed")

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
                raise invalid(f"chunk {chunk_id} metadata mismatch for {field}")

    if schema_version == VECTOR_INDEX_GENERATION_SCHEMA_VERSION:
        fingerprint = corpus_fingerprint_sha256(chunks)
        if manifest.get("corpus_fingerprint_sha256") != fingerprint:
            raise invalid("corpus fingerprint mismatch")
    else:
        corpus_manifest_path = manifest.get("corpus_manifest_path")
        corpus_manifest_sha256 = manifest.get("corpus_manifest_sha256")
        if corpus_manifest_path and corpus_manifest_sha256:
            source_manifest = Path(str(corpus_manifest_path))
            if not source_manifest.is_file() or _file_sha256(source_manifest) != corpus_manifest_sha256:
                raise invalid("corpus manifest is missing or has changed")

    return LoadedVectorIndex(
        embeddings=embeddings,
        chunk_ids=chunk_ids,
        rows_by_chunk_id=rows_by_chunk_id,
        manifest=manifest,
        manifest_sha256=_file_sha256(manifest_path),
    )


def load_current_vector_index_generation(
    session: Session,
    *,
    data_root: Path,
    collection: str,
    embedding_model: str,
    cache_enabled: bool = False,
    cache_max_items: int = 2,
    use_mmap: bool = False,
) -> LoadedVectorIndex:
    db_collection = session.scalar(select(Collection).where(Collection.name == collection))
    if db_collection is None:
        raise ValueError(f"Unknown collection: {collection}")

    state = session.scalar(
        select(VectorIndexState)
        .where(VectorIndexState.collection_id == db_collection.id)
        .where(VectorIndexState.embedding_model == embedding_model)
    )
    if state is None:
        raise _generation_error("state is missing", embedding_model, collection)
    if state.status != VECTOR_INDEX_READY:
        raise _generation_error(f"state is {state.status}", embedding_model, collection)
    if state.active_generation_id is None or state.active_manifest_sha256 is None or state.active_revision is None:
        raise _generation_error("ready state is incomplete", embedding_model, collection)
    if state.active_revision != state.desired_revision:
        raise _generation_error("active revision is stale", embedding_model, collection)

    cache_key: VectorIndexCacheKey = (
        str(db_collection.id),
        embedding_model,
        state.active_generation_id,
        state.active_manifest_sha256,
    )
    if cache_enabled and cache_key in _VECTOR_INDEX_CACHE:
        cached = _VECTOR_INDEX_CACHE.pop(cache_key)
        _VECTOR_INDEX_CACHE[cache_key] = cached
        return cached

    root = vector_index_generation_root(data_root, collection, embedding_model)
    current_path = root / VECTOR_CURRENT_POINTER_FILENAME
    if not current_path.is_file():
        raise _generation_error("current pointer is missing", embedding_model, collection)
    current = _read_generation_json(current_path, "current pointer", embedding_model, collection)
    if not isinstance(current, dict):
        raise _generation_error("current pointer root must be an object", embedding_model, collection)
    if current.get("generation_id") != state.active_generation_id:
        raise _generation_error("current pointer does not match database state", embedding_model, collection)
    if current.get("manifest_sha256") != state.active_manifest_sha256:
        raise _generation_error("current pointer manifest checksum does not match database state", embedding_model, collection)

    generation_dir = root / "generations" / state.active_generation_id
    manifest_path = generation_dir / VECTOR_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise _generation_error("active generation manifest is missing", embedding_model, collection)
    if _file_sha256(manifest_path) != state.active_manifest_sha256:
        raise _generation_error("active manifest checksum mismatch", embedding_model, collection)
    manifest = _read_generation_json(manifest_path, "manifest", embedding_model, collection)
    if not isinstance(manifest, dict):
        raise _generation_error("manifest root must be an object", embedding_model, collection)
    if manifest.get("generation_id") != state.active_generation_id:
        raise _generation_error("manifest generation does not match database state", embedding_model, collection)
    if manifest.get("target_revision") != state.active_revision:
        raise _generation_error("manifest target revision does not match database state", embedding_model, collection)

    loaded = _load_and_validate_vector_index_files(
        session,
        db_collection=db_collection,
        index_dir=generation_dir,
        manifest=manifest,
        manifest_path=manifest_path,
        collection=collection,
        embedding_model=embedding_model,
        schema_version=VECTOR_INDEX_GENERATION_SCHEMA_VERSION,
        safe_errors=True,
        use_mmap=use_mmap,
    )
    if cache_enabled:
        bounded_cache_size = max(1, cache_max_items)
        _VECTOR_INDEX_CACHE[cache_key] = loaded
        while len(_VECTOR_INDEX_CACHE) > bounded_cache_size:
            _VECTOR_INDEX_CACHE.popitem(last=False)
    return loaded


def clear_vector_index_cache() -> None:
    _VECTOR_INDEX_CACHE.clear()


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
    return _load_and_validate_vector_index_files(
        session,
        db_collection=db_collection,
        index_dir=index_dir,
        manifest=manifest,
        manifest_path=manifest_path,
        collection=collection,
        embedding_model=embedding_model,
        schema_version=VECTOR_INDEX_SCHEMA_VERSION,
    )
