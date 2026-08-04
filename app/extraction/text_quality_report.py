from __future__ import annotations

import shutil
import subprocess
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Chunk, Collection, Page, PageTextLayer
from app.extraction.text_quality import detect_caption_lines, detect_formula_like_lines, text_quality_signals


def build_text_quality_report(session: Session, settings: Settings, collection_name: str) -> dict[str, object]:
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")

    articles = list(session.scalars(select(Article).where(Article.collection_id == collection.id).order_by(Article.title)))
    article_ids = [article.id for article in articles]
    article_by_id = {article.id: article for article in articles}
    if not article_ids:
        return _empty_report(settings, collection_name)

    pages = list(session.scalars(select(Page).where(Page.article_id.in_(article_ids)).order_by(Page.article_id, Page.page_number)))
    layer_rows = list(
        session.scalars(
            select(PageTextLayer)
            .where(PageTextLayer.article_id.in_(article_ids))
            .order_by(PageTextLayer.article_id, PageTextLayer.page_number, PageTextLayer.layer_type)
        )
    )
    layers_by_page: dict[tuple[object, int], dict[str, PageTextLayer]] = defaultdict(dict)
    for layer in layer_rows:
        layers_by_page[(layer.article_id, layer.page_number)][layer.layer_type] = layer

    source_type_distribution = _count_chunks(session, Chunk.source_type, article_ids)
    text_layer_distribution = _count_chunks(session, Chunk.text_layer, article_ids)
    selected_text_layer_distribution = Counter(page.selected_text_layer for page in pages)
    page_text_layer_distribution = Counter(layer.layer_type for layer in layer_rows)

    empty_original_pages: list[dict[str, object]] = []
    short_original_pages: list[dict[str, object]] = []
    suspicious_pages: list[dict[str, object]] = []
    caption_candidates: list[dict[str, object]] = []
    formula_candidates: list[dict[str, object]] = []
    table_like_pages: list[dict[str, object]] = []
    ocr_used_pages = 0
    ocr_available_pages = 0
    ocr_still_unusable_pages: list[dict[str, object]] = []

    for page in pages:
        article = article_by_id[page.article_id]
        layer_map = layers_by_page.get((page.article_id, page.page_number), {})
        original = layer_map.get("original")
        ocr = layer_map.get("ocr")
        selected_text = page.text or ""
        original_text = original.text if original is not None else ""
        ocr_text = ocr.text if ocr is not None else ""
        original_signals = text_quality_signals(original_text)
        selected_signals = text_quality_signals(selected_text)
        reasons: list[str] = []

        if page.ocr_used:
            ocr_used_pages += 1
        if ocr is not None:
            ocr_available_pages += 1
            if not ocr.has_usable_text or not ocr_text.strip():
                ocr_still_unusable_pages.append(_page_ref(article, page, {"ocr_char_count": len(ocr_text)}))
        if not original_text.strip():
            ref = _page_ref(article, page, {"original_char_count": 0})
            empty_original_pages.append(ref)
            reasons.append("empty_original_text")
        elif original_signals.normalized_char_count < settings.text_quality_short_page_chars:
            ref = _page_ref(article, page, {"original_char_count": original_signals.normalized_char_count})
            short_original_pages.append(ref)
            reasons.append("short_original_text")
        if selected_signals.control_char_ratio > settings.text_quality_control_char_ratio:
            reasons.append("high_control_character_ratio")
        if selected_signals.repeated_artifact_count:
            reasons.append("repeated_extraction_artifacts")
        if selected_signals.table_like_line_count and selected_signals.caption_count == 0:
            reasons.append("table_like_text_without_caption")
        if ocr is not None and page.selected_text_layer == "original" and len(ocr_text) > max(len(original_text) * 2, 200):
            reasons.append("ocr_layer_much_longer_than_selected_original")

        captions = detect_caption_lines(selected_text)
        formulas = detect_formula_like_lines(selected_text)
        if captions:
            caption_candidates.append(_page_ref(article, page, {"caption_count": len(captions), "examples": captions[:3]}))
        if formulas:
            formula_candidates.append(_page_ref(article, page, {"formula_like_line_count": len(formulas), "examples": formulas[:3]}))
        if selected_signals.table_like_line_count:
            table_like_pages.append(_page_ref(article, page, {"table_like_line_count": selected_signals.table_like_line_count}))
        if reasons:
            suspicious_pages.append(
                _page_ref(
                    article,
                    page,
                    {
                        "reasons": reasons,
                        "selected_text_layer": page.selected_text_layer,
                        "selected_char_count": selected_signals.normalized_char_count,
                        "original_char_count": original_signals.normalized_char_count,
                        "ocr_char_count": len(ocr_text.strip()),
                        "control_char_ratio": selected_signals.control_char_ratio,
                    },
                )
            )

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "collection": collection_name,
        "thresholds": {
            "short_page_chars": settings.text_quality_short_page_chars,
            "control_char_ratio": settings.text_quality_control_char_ratio,
        },
        "article_count": len(articles),
        "page_count": len(pages),
        "empty_original_pages": empty_original_pages,
        "empty_original_page_count": len(empty_original_pages),
        "short_original_pages": short_original_pages,
        "short_original_page_count": len(short_original_pages),
        "ocr_used_pages": ocr_used_pages,
        "ocr_available_pages": ocr_available_pages,
        "ocr_still_unusable_pages": ocr_still_unusable_pages,
        "suspicious_pages": suspicious_pages,
        "suspicious_page_count": len(suspicious_pages),
        "caption_candidates": caption_candidates,
        "formula_candidates": formula_candidates,
        "table_like_pages": table_like_pages,
        "source_type_distribution": dict(source_type_distribution),
        "text_layer_distribution": dict(text_layer_distribution),
        "selected_text_layer_distribution": dict(selected_text_layer_distribution),
        "page_text_layer_distribution": dict(page_text_layer_distribution),
        "ocr_diagnostics": _ocr_diagnostics(settings),
    }


def build_reprocess_text_quality_dry_run(session: Session, settings: Settings, article: Article) -> dict[str, object]:
    pages = list(session.scalars(select(Page).where(Page.article_id == article.id).order_by(Page.page_number)))
    layer_rows = list(
        session.scalars(
            select(PageTextLayer)
            .where(PageTextLayer.article_id == article.id)
            .order_by(PageTextLayer.page_number, PageTextLayer.layer_type)
        )
    )
    chunk_count = int(session.scalar(select(func.count(Chunk.id)).where(Chunk.article_id == article.id)) or 0)
    layers_by_page: dict[int, dict[str, PageTextLayer]] = defaultdict(dict)
    for layer in layer_rows:
        layers_by_page[layer.page_number][layer.layer_type] = layer

    page_diagnostics = []
    candidate_actions = Counter[str]()
    for page in pages:
        layer_map = layers_by_page.get(page.page_number, {})
        original = layer_map.get("original")
        ocr = layer_map.get("ocr")
        selected_text = page.text or ""
        original_text = original.text if original is not None else ""
        ocr_text = ocr.text if ocr is not None else ""
        selected_signals = text_quality_signals(selected_text)
        original_signals = text_quality_signals(original_text)
        reasons: list[str] = []
        actions: list[str] = []

        if not original_text.strip():
            reasons.append("empty_original_text")
            actions.append("inspect_original_text_layer")
        elif original_signals.normalized_char_count < settings.text_quality_short_page_chars:
            reasons.append("short_original_text")
            actions.append("inspect_original_text_layer")
        if selected_signals.control_char_ratio > settings.text_quality_control_char_ratio:
            reasons.append("high_control_character_ratio")
            actions.append("inspect_text_extraction_artifacts")
        if selected_signals.table_like_line_count:
            reasons.append("table_like_text")
            actions.append("evaluate_table_or_caption_evidence")
        if selected_signals.caption_count:
            reasons.append("caption_candidate")
            actions.append("evaluate_caption_evidence")
        if selected_signals.formula_like_line_count:
            reasons.append("formula_like_text")
            actions.append("evaluate_formula_evidence")
        if ocr is not None and page.selected_text_layer == "original" and len(ocr_text) > max(len(original_text) * 2, 200):
            reasons.append("ocr_layer_much_longer_than_selected_original")
            actions.append("consider_reselecting_page_text_layer")
        if ocr is None and (not original_text.strip() or original_signals.normalized_char_count < settings.text_quality_short_page_chars):
            actions.append("consider_ocr_if_pdf_available")

        for action in actions:
            candidate_actions[action] += 1
        page_diagnostics.append(
            {
                "page_number": page.page_number,
                "selected_text_layer": page.selected_text_layer,
                "has_text_layer": page.has_text_layer,
                "ocr_used": page.ocr_used,
                "selected_char_count": selected_signals.normalized_char_count,
                "original_char_count": original_signals.normalized_char_count,
                "ocr_char_count": len(ocr_text.strip()),
                "caption_count": selected_signals.caption_count,
                "table_like_line_count": selected_signals.table_like_line_count,
                "formula_like_line_count": selected_signals.formula_like_line_count,
                "control_char_ratio": selected_signals.control_char_ratio,
                "reasons": reasons,
                "candidate_actions": sorted(set(actions)),
            }
        )

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "text-quality",
        "dry_run": True,
        "mutation_performed": False,
        "article": {
            "article_id": str(article.id),
            "title": article.title,
            "doi": article.doi,
            "status": article.status,
            "pdf_original_path": article.pdf_original_path,
            "pdf_ocr_path": article.pdf_ocr_path,
        },
        "current_counts": {
            "pages": len(pages),
            "page_text_layers": len(layer_rows),
            "chunks": chunk_count,
        },
        "candidate_actions": dict(candidate_actions),
        "page_diagnostics": page_diagnostics,
        "rollback_note": "Dry run only: no pages, chunks, text layers, PDFs, or vector index state were modified.",
    }


def _empty_report(settings: Settings, collection_name: str) -> dict[str, object]:
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "collection": collection_name,
        "thresholds": {
            "short_page_chars": settings.text_quality_short_page_chars,
            "control_char_ratio": settings.text_quality_control_char_ratio,
        },
        "article_count": 0,
        "page_count": 0,
        "empty_original_pages": [],
        "empty_original_page_count": 0,
        "short_original_pages": [],
        "short_original_page_count": 0,
        "ocr_used_pages": 0,
        "ocr_available_pages": 0,
        "ocr_still_unusable_pages": [],
        "suspicious_pages": [],
        "suspicious_page_count": 0,
        "caption_candidates": [],
        "formula_candidates": [],
        "table_like_pages": [],
        "source_type_distribution": {},
        "text_layer_distribution": {},
        "selected_text_layer_distribution": {},
        "page_text_layer_distribution": {},
        "ocr_diagnostics": _ocr_diagnostics(settings),
    }


def _page_ref(article: Article, page: Page, extra: dict[str, object]) -> dict[str, object]:
    return {
        "article_id": str(article.id),
        "title": article.title,
        "doi": article.doi,
        "page_number": page.page_number,
        **extra,
    }


def _count_chunks(session: Session, column: Any, article_ids: Sequence[object]) -> dict[str, int]:
    if not article_ids:
        return {}
    rows = session.execute(select(column, func.count()).where(Chunk.article_id.in_(article_ids)).group_by(column).order_by(column)).all()
    return {str(value): int(count) for value, count in rows}


def _ocr_diagnostics(settings: Settings) -> dict[str, object]:
    resolved = shutil.which(settings.ocr_command)
    payload: dict[str, object] = {
        "enabled": settings.ocr_enabled,
        "command": settings.ocr_command,
        "resolved_command": resolved,
        "languages": settings.ocr_languages,
        "reprocess_allow_existing": settings.ocr_reprocess_allow_existing,
    }
    if resolved is None:
        payload["version_status"] = "command_not_found"
        return payload
    try:
        completed = subprocess.run([resolved, "--version"], check=False, capture_output=True, text=True, timeout=30)
    except Exception as exc:
        payload["version_status"] = "failed"
        payload["version_error_type"] = type(exc).__name__
        payload["version_error"] = str(exc)
        return payload
    payload["version_status"] = "ok" if completed.returncode == 0 else "failed"
    version_text = (completed.stdout or completed.stderr).splitlines()
    payload["version"] = version_text[0].strip() if version_text else ""
    return payload
