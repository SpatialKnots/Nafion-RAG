"""Read-only occurrence diagnostics. Recognition/selection is not scientific approval."""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select

from app.db.models import Article, Chunk
from app.db.session import SessionLocal
from app.facts.extraction import MAX_FACTS_PER_CHUNK, diagnose_numeric_occurrences


def chunk_record(chunk: Chunk) -> dict:
    candidates, occurrences = diagnose_numeric_occurrences(chunk)
    records = []
    selected = iter(candidates)
    for occurrence in occurrences:
        row = asdict(occurrence)
        if chunk.text[occurrence.start:occurrence.end] != occurrence.text:
            raise ValueError("Occurrence span does not match source")
        row["source_line"] = chunk.text[occurrence.line_start:occurrence.line_end]
        row["candidate"] = asdict(next(selected)) if occurrence.decision == "accepted" else None
        row["duplicate_scientific_equivalence"] = "not_assessed" if occurrence.decision == "duplicate" else None
        records.append(row)
    return {
        "chunk_id": str(chunk.id), "article_id": str(chunk.article_id),
        "chunk_sha256": hashlib.sha256(chunk.text.encode()).hexdigest(),
        "page_start": chunk.page_start, "page_end": chunk.page_end,
        "occurrence_page": chunk.page_start if chunk.page_start == chunk.page_end else None,
        "page_attribution": "single_page_chunk" if chunk.page_start == chunk.page_end else "unresolved_multi_page_chunk",
        "source_type": chunk.source_type, "text_layer": chunk.text_layer,
        "occurrences": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = []
    with SessionLocal() as session:
        for chunk, article in session.execute(select(Chunk, Article).join(Article).order_by(Chunk.id)):
            record = chunk_record(chunk)
            record["pdf_path"] = article.pdf_original_path
            record["stored_pdf_sha256"] = article.checksum_sha256
            records.append(record)
    counts = Counter(o["decision"] for r in records for o in r["occurrences"])
    reasons = Counter(o["reason"] for r in records for o in r["occurrences"])
    cues = Counter(cue["kind"] for r in records for o in r["occurrences"] for cue in o["context_cues"])
    report = {
        "schema_version": 2, "applied": False, "production_cap": MAX_FACTS_PER_CHUNK,
        "extractor_sha256": hashlib.sha256(Path("app/facts/extraction.py").read_bytes()).hexdigest(),
        "context_cues_sha256": hashlib.sha256(Path("app/facts/context_cues.py").read_bytes()).hexdigest(),
        "scope": "NUMERIC_UNIT_PATTERN matches only; accepted means selected, not scientifically verified. "
                 "Offsets are half-open Python character offsets in chunk text. PDF hashes are stored metadata, not reverified. "
                 "Context cues are same-line lexical evidence, not assigned scientific roles/operators; absence is not exactness. "
                 "Lexical duplicates are not scientifically validated duplicates.",
        "chunks": len(records), "decisions": dict(sorted(counts.items())),
        "reasons": dict(sorted(reasons.items())), "context_cue_counts": dict(sorted(cues.items())), "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}))


if __name__ == "__main__":
    main()
