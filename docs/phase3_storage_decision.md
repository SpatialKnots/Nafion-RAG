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

No embedding dependency is selected by this decision. Before implementation,
choose and install one local embedding runtime explicitly.

Candidate next choices:

- `fastembed` for a lighter local embedding workflow;
- `sentence-transformers` if model quality and multilingual coverage justify
  the larger dependency set;
- ONNX-based runtime if reproducibility and packaged model control outweigh
  implementation complexity.

Any dependency addition must update `pyproject.toml`, record model identifiers
in operations documentation, and pass tests before semantic retrieval is
reported as implemented.

## Rollback

Rollback for this storage path is file-based:

- leave exact retrieval as the default;
- delete generated files under `data/processed/vector_indexes/`;
- rebuild local indexes from database chunks when needed;
- do not re-ingest or mutate original PDFs.

## Verdict

Gate 2 storage backend is local rebuildable vector indexes, not `pgvector`, for
the current environment. The next implementation step is dependency selection
and a manifest-first index builder that can detect stale chunk/model state
before any semantic search endpoint is exposed.
