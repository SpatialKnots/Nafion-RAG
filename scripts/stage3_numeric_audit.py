"""Read-only, source-verified numeric target audit; no structured_facts writes.

This is targeted detection coverage, not exhaustive extraction precision/recall.
Expected operators/materials/conditions are reviewed labels, never inferred gold.
"""

import argparse
import hashlib
import json
from dataclasses import asdict, fields
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.models import Article, Chunk, PageTextLayer
from app.db.session import SessionLocal
from app.facts.extraction import StructuredFactCandidate, extract_structured_fact_candidates_from_chunk


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("docs/numeric_fact_cases.json"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = args.cases.read_bytes()
    fixture = json.loads(raw)
    if fixture["review_status"] != "assistant_pdf_reviewed" or not fixture["cases"]:
        raise ValueError("Expected nonempty PDF-reviewed development cases")
    ids = [case["id"] for case in fixture["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs")
    candidate_fields = {field.name for field in fields(StructuredFactCandidate)}
    records = []
    verified_pdfs: dict[str, str] = {}
    with SessionLocal() as session:
        for case in fixture["cases"]:
            article = session.scalars(select(Article).where(Article.checksum_sha256 == case["article_checksum"])).one()
            pdf = Path(article.pdf_original_path).resolve()
            if str(pdf) not in verified_pdfs:
                verified_pdfs[str(pdf)] = sha(pdf.read_bytes())
            if verified_pdfs[str(pdf)] != case["article_checksum"]:
                raise ValueError(f"{case['id']}: original PDF checksum mismatch")
            layer = session.scalars(select(PageTextLayer).where(
                PageTextLayer.article_id == article.id, PageTextLayer.page_number == case["page"],
                PageTextLayer.layer_type == case["text_layer"])).one()
            text = case["text"]
            if sha(text.encode()) != case["text_sha256"] or layer.text[case["start"]:case["start"] + len(text)] != text:
                raise ValueError(f"{case['id']}: annotated fragment changed")
            chunks = list(session.scalars(select(Chunk).where(
                Chunk.article_id == article.id, Chunk.page_start <= case["page"], Chunk.page_end >= case["page"],
                Chunk.text_layer == case["text_layer"]).order_by(Chunk.chunk_index)))
            chunks = [chunk for chunk in chunks if text in chunk.text]
            if not chunks:
                raise ValueError(f"{case['id']}: no selected-layer chunk contains the exact fragment")
            candidates = [candidate for chunk in chunks for candidate in extract_structured_fact_candidates_from_chunk(chunk)]
            targets = []
            for value in case["values"]:
                expected = Decimal(value)
                matches = [candidate for candidate in candidates
                           if candidate.field_value_numeric == expected and candidate.unit == case["unit"]
                           and candidate.field_name == case["field"] and candidate.field_value_text in text]
                targets.append({"expected": value, "detected": bool(matches),
                                "matching_candidates": [asdict(candidate) for candidate in matches]})
            records.append({
                **case, "article_id": str(article.id), "pdf_path": str(pdf),
                "page_text_sha256": sha(layer.text.encode()),
                "chunks": [{"id": str(c.id), "text_sha256": sha(c.text.encode()),
                            "page_start": c.page_start, "page_end": c.page_end,
                            "source_type": c.source_type, "text_layer": c.text_layer} for c in chunks],
                "targets": targets, "all_values_detected": all(t["detected"] for t in targets),
                "all_chunk_candidates": [asdict(c) for c in candidates],
                "unrepresented_structured_fields": [name for name in ("operator", "material", "conditions")
                                                    if name not in candidate_fields],
            })
    # Detect accidental/external source changes during the run as well.
    for path, checksum in verified_pdfs.items():
        if sha(Path(path).read_bytes()) != checksum:
            raise ValueError(f"Original PDF changed during audit: {path}")
    total = sum(len(r["targets"]) for r in records)
    detected = sum(t["detected"] for r in records for t in r["targets"])
    summary = {"cases": len(records), "numeric_targets": total, "detected_targets": detected,
               "target_detection_coverage": detected / total,
               "all_values_detected_cases": sum(r["all_values_detected"] for r in records),
               "cases_with_unrepresented_context_fields": sum(bool(r["unrepresented_structured_fields"]) for r in records)}
    report = {"cases_sha256": sha(raw), "extractor_sha256": sha(Path("app/facts/extraction.py").read_bytes()),
              "scope": fixture["scope"], "independent_review": fixture["independent_review"],
              "applied": False, "verified_originals": verified_pdfs, "summary": summary, "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    if args.check and (detected != total or summary["cases_with_unrepresented_context_fields"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
