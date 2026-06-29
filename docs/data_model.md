# Data Model

The initial schema follows the implementation plan while keeping vector search out of Phase 1.

## Core Tables

- `collections`: `literature` and `own_data`.
- `articles`: one row per unique PDF checksum.
- `pages`: page-level text and OCR/text-layer flags.
- `sections`: reserved for GROBID-derived sections.
- `chunks`: source fragments with `page_start` and `page_end`.
- `article_tags`: deterministic and manual tags.
- `notes`: user notes linked to articles or chunks.
- `ingestion_jobs`: visible ingestion status and failures.
- `structured_facts`: source-linked scientific facts for later extraction work.

## Traceability

Every chunk stores:

- `article_id`;
- `page_start`;
- `page_end`;
- `source_type`;
- exact `text`.

This is the minimum required evidence layer for later exact search, semantic search, and RAG citations.
