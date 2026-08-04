# Phase 3 Storage Decision

Date: 2026-08-03

This decision records the Phase 3 retrieval storage backend after checking the
current local environment.

## Evidence

PostgreSQL check:

```text
pg_available_extensions where name = 'vector': []
pg_extension where extname = 'vector': []
server: PostgreSQL 18.4 on x86_64-windows
```

Python package availability check in the project virtual environment:

```text
numpy: false
faiss: false
sentence_transformers: false
transformers: false
fastembed: false
sklearn: false
onnxruntime: false
```

The checks above mean `pgvector` is not available in the current PostgreSQL
installation, and no local embedding/vector runtime is currently installed in
the project environment.

## Decision

Phase 3 should use a rebuildable local vector index under:

```text
data/processed/vector_indexes/
```

The source of truth remains the database `chunks` table. Generated vector index
files are local artifacts and must remain rebuildable from indexed chunks,
model metadata, and a manifest.

This decision avoids making `pgvector` a hidden local infrastructure
requirement. If `pgvector` is installed later, the project can revisit a
database-backed embedding table with a new decision record.

## Required Manifest

Each local vector index must have a manifest next to the generated index files.
The manifest must record:

- retrieval backend;
- embedding model identifier;
- embedding dimension;
- software dependency versions;
- corpus manifest checksum or article checksums;
- chunk ids;
- chunk text checksums;
- index build command;
- creation timestamp.
- SHA-256 checksums for the embedding and chunk-id artifacts;
- cosine normalization state and similarity method.

The manifest is required for stale-index detection. If a chunk text checksum,
model identifier, embedding dimension, or corpus checksum changes, the index
must be rebuilt before semantic or hybrid retrieval can use it.

A manifest-only artifact can be generated with:

```powershell
python -m app.retrieval.cli manifest --embedding-model MODEL_ID --embedding-dimension DIMENSION
```

This command does not create embeddings and does not enable semantic or hybrid
retrieval.

## Dependency Gate

FastEmbed is selected as the first local embedding runtime for the local vector
index path.

Implemented dependency constraints:

- `fastembed>=0.8,<0.9`;
- `numpy>=1.26,<2.3`.

`numpy<2.3` is pinned because the project type-checks as Python 3.11, and newer
NumPy stubs may use syntax that requires Python 3.12.

The first verified model build used:

```text
BAAI/bge-small-en-v1.5
dimension: 384
chunk_count: 379
```

FastEmbed may download model files from HuggingFace on first use. On Windows,
the HuggingFace cache may warn that symlinks are unavailable unless Developer
Mode or administrator privileges are enabled. This is a local cache efficiency
warning, not an indexing failure.

## Rollback

Rollback for this storage path is file-based:

- leave exact retrieval as the default;
- delete generated files under `data/processed/vector_indexes/`;
- rebuild local indexes from database chunks when needed;
- do not re-ingest or mutate original PDFs.

## Verdict

Gate 2 storage backend is local rebuildable vector indexes, not `pgvector`, for
the current environment. FastEmbed is the first embedding runtime, and the
project can build and strictly validate manifest v2 local vector artifacts.
Semantic cosine retrieval is implemented behind an explicit method selection.
Hybrid RRF retrieval is also implemented behind an explicit method selection.
Exact retrieval remains the default pending a separate default-method decision.
