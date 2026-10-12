"""Replay previously PDF-reviewed numeric blockers against verified stored sources.

This read-only regression check does not approve any new corpus diff or refresh facts.
"""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.db.models import Article, Chunk, PageTextLayer
from app.db.session import SessionLocal
from app.facts.extraction import extract_structured_fact_candidates_from_chunk


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-cap-review", action="store_true", help="Also replay the three glyph/unit blockers")
    parser.add_argument("--additional-labels", type=Path, help="Additional nonempty source-reviewed false-addition cases")
    args = parser.parse_args()
    raw = Path("docs/numeric_change_review.json").read_bytes()
    labels = json.loads(raw)["labels"]
    blockers = [label for label in labels if label["verdict"] == "blocker"]
    if {label["id"] for label in blockers} != {"bare_power", "uncertainty_operand", "inverse_unit", "dash_sign"}:
        raise ValueError("Expected the four previously reviewed numeric blockers")
    cap_raw = b""
    if args.include_cap_review:
        cap_raw = Path("docs/numeric_guard_change_review.json").read_bytes()
        expected = {"symbol_uncertainty", "escaped_inverse_unit", "compound_capacity_unit"}
        extra = [label for label in json.loads(cap_raw)["labels"] if label["id"] in expected]
        if len(extra) != 3 or {label["id"] for label in extra} != expected or any(
            label["verdict"] != "blocker" or label["direction"] != "added"
            or label["review_status"] != "assistant_pdf_reviewed" for label in extra
        ):
            raise ValueError("Expected the three reviewed glyph/unit blockers")
        blockers.extend(extra)
    additional_raw = b""
    if args.additional_labels:
        additional_raw = args.additional_labels.read_bytes()
        additional = json.loads(additional_raw)["labels"]
        if not additional or any(
            label["verdict"] != "blocker" or label["direction"] != "added"
            or label["review_status"] != "assistant_pdf_reviewed" for label in additional
        ):
            raise ValueError("Additional cases must be reviewed false additions")
        identifiers = [label["id"] for label in blockers + additional]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate regression case IDs")
        blockers.extend(additional)
    records = []
    with SessionLocal() as session:
        for label in blockers:
            chunk = session.get(Chunk, UUID(label["chunk_id"]))
            if chunk is None:
                raise ValueError("Missing reviewed chunk")
            article = session.get(Article, chunk.article_id)
            if article is None:
                raise ValueError("Missing reviewed article")
            layer = session.scalars(select(PageTextLayer).where(
                PageTextLayer.article_id == article.id,
                PageTextLayer.page_number == label["page"],
                PageTextLayer.layer_type == label["text_layer"],
            )).one()
            pdf = Path(article.pdf_original_path)
            checksum = hashlib.sha256(pdf.read_bytes()).hexdigest()
            fragment = label["text"]
            if (checksum != article.checksum_sha256 or checksum != label["article_checksum"]
                    or str(article.id) != label["candidate"]["article_id"]
                    or chunk.text_layer != label["text_layer"]
                    or not chunk.page_start <= label["page"] <= chunk.page_end
                    or hashlib.sha256(fragment.encode()).hexdigest() != label["text_sha256"]
                    or layer.text[label["start"]:label["start"] + len(fragment)] != fragment
                    # Chunk assembly strips terminal line breaks; page hash/text
                    # above still verifies the full, unmodified reviewed fragment.
                    or fragment.rstrip("\r\n") not in chunk.text):
                raise ValueError(f"Reviewed source changed: {label['id']}")
            candidates = extract_structured_fact_candidates_from_chunk(chunk)
            rejected = label["candidate"]["field_value_text"] not in [c.field_value_text for c in candidates]
            records.append(dict(
                id=label["id"], rejected=rejected, chunk_id=str(chunk.id),
                chunk_sha256=hashlib.sha256(chunk.text.encode()).hexdigest(),
                article_id=str(article.id), pdf_path=str(pdf), pdf_sha256=checksum,
                page=label["page"], text_layer=label["text_layer"], fragment=fragment,
                fragment_sha256=label["text_sha256"], rejected_candidate=label["candidate"],
            ))
    report = dict(
        labels_sha256=hashlib.sha256(raw).hexdigest(),
        cap_labels_sha256=hashlib.sha256(cap_raw).hexdigest() if cap_raw else None,
        additional_labels_sha256=hashlib.sha256(additional_raw).hexdigest() if additional_raw else None,
        extractor_sha256=hashlib.sha256(Path("app/facts/extraction.py").read_bytes()).hexdigest(),
        applied=False, scope="Historical source-bound regression only; no new scientific approval",
        checked=len(records), rejected=sum(r["rejected"] for r in records), records=records,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}))
    if not all(r["rejected"] for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
