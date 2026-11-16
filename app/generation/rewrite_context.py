"""Source-bound title context for a single explicitly referenced work; no writes."""

from __future__ import annotations

import re
from dataclasses import asdict
from importlib import import_module
from typing import Any
from uuid import UUID

import fitz  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article
from app.documents.service import PdfStorageIntegrityError, resolve_article_pdf
from app.records.sources import file_hash
from app.retrieval.search import SearchFilters, _source_reference_inventory
from app.retrieval.source_reference import reference, resolve


def resolve_context(session: Session, settings: Settings, question: str, collection: str,
                    library_source_id: UUID | None) -> tuple[dict[str, str] | None, dict[str, Any]]:
    citation = reference(question)
    if citation is None:
        return None, {"status": "unavailable", "reason": "no_single_explicit_article_reference"}
    candidates = resolve(citation, _source_reference_inventory(
        session, collection, SearchFilters.normalize(library_source_id=library_source_id)))
    if len(candidates) != 1:
        raise ValueError("Explicit article reference unresolved or ambiguous; specify a unique registered author/year")
    article = session.get(Article, UUID(candidates[0]))
    if article is None:
        raise ValueError("Resolved article is unavailable")
    path = resolve_article_pdf(article, settings).path
    checksum = file_hash(path)
    if checksum != article.checksum_sha256:
        raise PdfStorageIntegrityError("Rewrite title context original PDF checksum mismatch")
    # Reuse the existing general layout algorithm, never a per-paper title regex.
    tac = import_module("scripts.tac_experiment")
    cover = import_module("scripts.tac_front_matter").COVER
    diagnostics: dict[str, Any] = {"article_id": str(article.id), "status": "unavailable", "pages": [],
                                   "reason": "no_unique_source_title", "scientific_confirmation": False}
    with fitz.open(path) as document:
        for index in range(min(3, len(document))):
            raw = document[index].get_text("text")
            page = tac.add_layout_blocks({"page": index + 1, "text": raw, "text_sha256": tac.digest(raw.encode()),
                "layer": "original", "layer_id": checksum, "layer_pdf_path": str(path)})
            title, candidates_title = tac.title_from_layout(page)
            diagnostics["pages"].append({"page": index + 1, "layout_warnings": page["layout_warnings"],
                                          "title_candidates": candidates_title})
            if cover.search(raw):
                continue
            if title is not None:
                if raw[title.start:title.end] != title.quote:
                    raise PdfStorageIntegrityError("Rewrite title differs from the original PDF span")
                text = re.sub(r"\s+", " ", title.quote).strip()
                context = {"article_id": str(article.id), "title": text, "title_sha256": tac.digest(text.encode()),
                           "original_pdf_sha256": checksum}
                diagnostics.update(status="source_bound_algorithm_proposal", reason="unique_layout_title",
                                   source=asdict(title))
                return context, diagnostics
            # The original algorithm examines later pages only after a cover.
            break
    return None, diagnostics
