"""Freeze all profiled stored pages for a source-only Li-Nafion development pilot."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pymupdf
from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.models import Article, Page
from app.db.session import SessionLocal
from app.documents.service import resolve_article_pdf
from app.records.pilot import PILOT_VERSION, PilotDocument, write_pilot_packet
from app.records.schema import CandidateBundle
from app.records.sources import file_hash, source_region_from_page


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path("docs/records/pilot_initialization_protocol_v0.1.md"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    profile = json.loads(args.profile.read_bytes())
    expected = {UUID(row["article_id"]): row["pdf_sha256"] for row in profile["articles"]}
    if len(expected) != len(profile["articles"]):
        raise ValueError("Duplicate profile document")
    settings = get_settings()
    documents = []
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        articles = list(session.scalars(select(Article).order_by(Article.id)))
        if {article.id for article in articles} != set(expected):
            raise ValueError("Live corpus membership differs from frozen profile")
        for article in articles:
            original = resolve_article_pdf(article, settings, "original").path
            original_hash = file_hash(original)
            if original_hash != article.checksum_sha256 or original_hash != expected[article.id]:
                raise ValueError(f"Original PDF differs from database/profile: {article.id}")
            with pymupdf.open(original) as pdf:
                pdf_pages = len(pdf)
            pages = list(session.scalars(select(Page).where(Page.article_id == article.id).order_by(Page.page_number)))
            stored_numbers = tuple(page.page_number for page in pages)
            diagnostics = [f"missing_stored_page:{page}" for page in range(1, pdf_pages + 1) if page not in stored_numbers]
            regions = []
            for page in pages:
                if not page.text or not page.text.strip():
                    diagnostics.append(f"empty_selected_page:{page.page_number}")
                    continue
                regions.append(source_region_from_page(
                    session, settings, article.id, page.page_number, selection_basis="fixed_page",
                    selection_note="All stored selected pages; source-only development corpus; no record gold or retrieval filtering.",
                ))
            if file_hash(original) != original_hash:
                raise ValueError(f"Original PDF changed during export: {article.id}")
            bundle = CandidateBundle(
                run_id=uuid4(), created_at=datetime.now(UTC), producer=PILOT_VERSION, regions=tuple(regions),
            ) if regions else None
            documents.append(PilotDocument(
                article_id=article.id, title=article.title, doi=article.doi, original_pdf_path=str(original),
                original_pdf_sha256=original_hash, pdf_page_count=pdf_pages, stored_page_numbers=stored_numbers,
                bundle=bundle, diagnostics=tuple(diagnostics),
            ))
    manifest = write_pilot_packet(
        tuple(documents), args.profile, args.output, protocol_path=args.protocol,
        baseline_manifest_path=args.baseline_manifest, source_root=Path(__file__).resolve().parents[1],
    )
    print(json.dumps({key: manifest[key] for key in (
        "source_fingerprint", "documents", "stored_pages", "exported_regions", "lexical_candidate_count",
        "candidate_records", "annotations", "document_diagnostics",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
