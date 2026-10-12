"""Read-only cap sensitivity audit; trial caps are diagnostics, not production settings."""

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select

import app.facts.extraction as extraction
from app.db.models import Chunk
from app.db.session import SessionLocal


def identity(candidate: dict) -> tuple:
    return (candidate["field_name"], candidate["field_value_text"],
            str(candidate["field_value_numeric"]), candidate["unit"])


def extract_keys(chunk: Chunk, cap: int) -> set[tuple]:
    with patch.object(extraction, "MAX_FACTS_PER_CHUNK", cap):
        return {(c.field_name, c.field_value_text, str(c.field_value_numeric), c.unit)
                for c in extraction.extract_structured_fact_candidates_from_chunk(chunk)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.diff.read_bytes()
    diff = json.loads(raw)
    code_hash = hashlib.sha256(Path("app/facts/extraction.py").read_bytes()).hexdigest()
    if diff["current_code_sha256"] != code_hash:
        raise ValueError("Extractor changed since diff")
    production_cap = extraction.MAX_FACTS_PER_CHUNK
    caps = sorted({production_cap, 16, 24})
    targets = [(r, c) for r in diff["records"] for c in r["displaced_by_cap"]]
    if not targets:
        raise ValueError("No cap-displaced targets in diff")
    with SessionLocal() as session:
        chunks = list(session.scalars(select(Chunk).order_by(Chunk.id)))
    by_id = {str(chunk.id): chunk for chunk in chunks}
    if len(chunks) != diff["chunks"]:
        raise ValueError("Corpus size changed since diff")
    for row in diff["records"]:
        if row["chunk_id"] not in by_id or by_id[row["chunk_id"]].text != row["text"]:
            raise ValueError("Diff source chunk changed or disappeared")
    results = {cap: {str(c.id): extract_keys(c, cap) for c in chunks} for cap in caps}
    records = []
    for row, candidate in targets:
        chunk = by_id[row["chunk_id"]]
        key = identity(candidate)
        article_chunks = [c for c in chunks if c.article_id == chunk.article_id]
        if key not in extract_keys(chunk, len(chunk.text) + 1):
            raise ValueError("Target no longer present without cap")
        records.append(dict(
            chunk_id=str(chunk.id), article_id=str(chunk.article_id), candidate=candidate,
            chunk_sha256=hashlib.sha256(chunk.text.encode()).hexdigest(),
            selected_by_cap={str(cap): key in results[cap][str(chunk.id)] for cap in caps},
            same_candidate_other_chunks_at_production_cap=[
                str(c.id) for c in article_chunks if c.id != chunk.id and key in results[production_cap][str(c.id)]
            ],
        ))
    report = dict(
        diff_sha256=hashlib.sha256(raw).hexdigest(), extractor_sha256=code_hash,
        applied=False, production_cap=production_cap, chunks=len(chunks),
        scope="Candidate identity and cap sensitivity only; presence is not scientific support",
        trial_candidate_counts={str(cap): sum(len(values) for values in results[cap].values()) for cap in caps},
        trial_added_over_production={str(cap): sum(
            len(results[cap][str(c.id)] - results[production_cap][str(c.id)]) for c in chunks
        ) for cap in caps},
        records=records,
    )
    if extraction.MAX_FACTS_PER_CHUNK != production_cap:
        raise RuntimeError("Diagnostic cap was not restored")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
