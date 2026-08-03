from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Chunk, Collection


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


def write_vector_index_manifest(manifest: dict[str, Any], data_root: Path) -> Path:
    index_name = safe_index_name(str(manifest["embedding_model"]))
    index_dir = data_root / "processed" / "vector_indexes" / index_name
    index_dir.mkdir(parents=True, exist_ok=True)
    output_path = index_dir / "manifest.json"
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
