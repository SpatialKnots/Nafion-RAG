"""Read-only lexical corpus profile for a Li-Nafion pilot, not scientific gold."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text

from app.db.models import Article, Chunk
from app.db.session import SessionLocal

LITHIUM_NAFION = re.compile(
    r"\bli[\s‐‑–−-]*(?:na(?:fi|ﬁ)on|нафион\w*)\b|"
    r"\b(?:lithi(?:ated|um)|литиев\w*|литирован\w*)[\s\w,()-]{0,60}(?:na(?:fi|ﬁ)on|нафион\w*)\b|"
    r"\b(?:na(?:fi|ﬁ)on|нафион\w*)[\s\w,()-]{0,60}(?:lithi(?:ated|um)|литиев\w*|литирован\w*)\b",
    re.IGNORECASE,
)
CONDUCTIVITY = re.compile(r"conductivit\w*|проводим\w*", re.IGNORECASE)


def file_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    articles = []
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        for article in session.scalars(select(Article).order_by(Article.id)):
            pdf = Path(article.pdf_original_path)
            observed = file_hash(pdf)
            if observed != article.checksum_sha256:
                raise ValueError(f"Original PDF checksum mismatch: {article.id}")
            regions = []
            for chunk in session.scalars(select(Chunk).where(Chunk.article_id == article.id).order_by(Chunk.chunk_index)):
                anchors = list(LITHIUM_NAFION.finditer(chunk.text))
                if not anchors:
                    continue
                for match in anchors:
                    start = max(0, match.start() - 160)
                    end = min(len(chunk.text), match.end() + 300)
                    regions.append(
                        {
                            "chunk_id": str(chunk.id),
                            "page_start": chunk.page_start,
                            "page_end": chunk.page_end,
                            "text_layer": chunk.text_layer,
                            "source_type": chunk.source_type,
                            "chunk_sha256": hashlib.sha256(chunk.text.encode()).hexdigest(),
                            "anchor_start": match.start(),
                            "anchor_end": match.end(),
                            "anchor": match.group(),
                            "fragment_start": start,
                            "fragment_end": end,
                            "fragment": chunk.text[start:end],
                            "conductivity_in_same_chunk": bool(CONDUCTIVITY.search(chunk.text)),
                        }
                    )
            articles.append(
                {
                    "article_id": str(article.id),
                    "title": article.title,
                    "doi": article.doi,
                    "pdf_path": str(pdf),
                    "pdf_sha256": observed,
                    "original_integrity": True,
                    "candidate_regions": regions,
                    "candidate_priority": "li_nafion_and_conductivity_in_chunk"
                    if any(r["conductivity_in_same_chunk"] for r in regions)
                    else "li_nafion_mention"
                    if regions
                    else "no_anchor",
                }
            )
    result = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "Li-Nafion ionic conductivity",
        "rule": LITHIUM_NAFION.pattern,
        "conductivity_rule": CONDUCTIVITY.pattern,
        "limitations": [
            "Lexical shortlist, not verified material/property linkage or gold.",
            "No anchor does not establish absence; spelling, OCR and cross-chunk context can be missed.",
            "Page ranges are chunk provenance, not inferred occurrence pages.",
            "Repeated mentions across overlapping chunks are not independent experiments.",
        ],
        "summary": {
            "articles": len(articles),
            "originals_verified": len(articles),
            "articles_with_anchors": sum(bool(a["candidate_regions"]) for a in articles),
            "articles_with_conductivity_cooccurrence": sum(
                a["candidate_priority"] == "li_nafion_and_conductivity_in_chunk" for a in articles
            ),
        },
        "articles": articles,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}))


if __name__ == "__main__":
    main()
