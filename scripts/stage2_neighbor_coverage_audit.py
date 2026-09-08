"""Read-only +/-2 chunk experiment; does not enable automatic context expansion."""

import json
from pathlib import Path

from sqlalchemy import select

from app.db.models import Chunk
from app.db.session import SessionLocal
from app.generation.required_concepts import assess_required_concepts

baseline = json.loads(Path("tmp/stage2_retention_after.json").read_text(encoding="utf-8"))
changes = []
with SessionLocal() as session:
    chunks = {str(chunk.id): chunk for chunk in session.scalars(select(Chunk))}
    by_article = {}
    for chunk in chunks.values():
        by_article.setdefault(chunk.article_id, []).append(chunk)
    for row in baseline["records"]:
        missing = set(row["selected_full"]["required_concepts"]["missing"])
        if not missing:
            continue
        selected = [chunks[chunk_id] for chunk_id in row["selected_chunk_ids"]]
        added = []
        for parent in selected:
            candidates = sorted(
                by_article[parent.article_id],
                key=lambda chunk: (abs(chunk.chunk_index - parent.chunk_index), chunk.chunk_index, str(chunk.id)),
            )
            for chunk in candidates:
                if chunk.text_layer != parent.text_layer or not 0 < abs(chunk.chunk_index - parent.chunk_index) <= 2:
                    continue
                covered = set(assess_required_concepts(row["query"], [chunk.text]).matched) & missing
                if not covered:
                    continue
                added.append(
                    {
                        "chunk_id": str(chunk.id),
                        "article_id": str(chunk.article_id),
                        "parent": str(parent.id),
                        "pages": [chunk.page_start, chunk.page_end],
                        "source_type": chunk.source_type,
                        "text_layer": chunk.text_layer,
                        "covered": sorted(covered),
                    }
                )
                missing -= covered
        if added:
            item = {key: row[key] for key in ("id", "method", "answerable")}
            item.update({"added": added, "missing_after": sorted(missing)})
            changes.append(item)
            print(json.dumps(item, ensure_ascii=True))
Path("tmp/stage2_neighbor_coverage_audit.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8")
