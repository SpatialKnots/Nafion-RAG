from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article, ArticleTag, Chunk, Note, Page, PageTextLayer, Section, StructuredFact
from app.db.session import SessionLocal
from app.diagnostics.doctor import run_doctor
from app.ingestion.service import IngestionResult, ingest_pdf, reselect_article_text
from app.ingestion.text_layers import article_text_layer_summary

cli = typer.Typer(help="Nafion RAG ingestion commands.")


def _echo_payload(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=True))


def _json_ready(value: object) -> object:
    if isinstance(value, UUID | datetime | Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def _model_dict(model: object) -> dict[str, object]:
    return {key: value for key, value in vars(model).items() if key != "_sa_instance_state"}


def _result_payload(path: Path, result: IngestionResult) -> dict[str, object]:
    return {
        "path": str(path),
        "article_id": result.article_id,
        "status": result.status,
        "checksum_sha256": result.checksum_sha256,
        "page_count": result.page_count,
        "chunk_count": result.chunk_count,
        "ocr_required": result.ocr_required,
    }


def _ingest_one(path: Path, collection: str, *, force_ocr: bool = False) -> dict[str, object]:
    settings = get_settings()
    with SessionLocal() as session:
        result = ingest_pdf(session, settings, path, collection, force_ocr=force_ocr)
    return _result_payload(path, result)


@cli.command()
def file(path: Path, collection: str = "literature", force_ocr: bool = False) -> None:
    _echo_payload(_ingest_one(path, collection, force_ocr=force_ocr))


@cli.command()
def folder(path: Path, collection: str = "literature", force_ocr: bool = False) -> None:
    pdfs = sorted(item for item in path.glob("*.pdf") if item.is_file())
    if not pdfs:
        typer.echo(f"No PDF files found in {path}")
        raise typer.Exit(code=1)
    summary = {"total": len(pdfs), "indexed": 0, "duplicate": 0, "failed": 0}
    for pdf in pdfs:
        try:
            payload = _ingest_one(pdf, collection, force_ocr=force_ocr)
        except Exception as exc:
            summary["failed"] += 1
            _echo_payload({"path": str(pdf), "status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
            continue

        status = payload["status"]
        if status in {"indexed", "duplicate"}:
            summary[status] += 1
        _echo_payload(payload)

    _echo_payload({"summary": summary})
    if summary["failed"]:
        raise typer.Exit(code=1)


def _articles_for_target(session: Session, target: str) -> list[Article]:
    if target == "all":
        return list(session.scalars(select(Article).order_by(Article.title)))
    try:
        article_id = UUID(target)
    except ValueError as exc:
        raise typer.BadParameter("target must be 'all' or an article UUID") from exc
    article = session.scalar(select(Article).where(Article.id == article_id))
    if article is None:
        raise typer.BadParameter(f"Unknown article: {target}")
    return [article]


def _missing_corpus_articles(session: Session) -> list[Article]:
    articles = list(session.scalars(select(Article).order_by(Article.title)))
    missing: list[Article] = []
    for article in articles:
        original_missing = not Path(article.pdf_original_path).exists()
        ocr_missing = bool(article.pdf_ocr_path) and not Path(article.pdf_ocr_path or "").exists()
        if original_missing or ocr_missing:
            missing.append(article)
    return missing


def _backup_missing_articles(session: Session, articles: list[Article], backup_dir: Path) -> Path:
    article_ids = [article.id for article in articles]
    payload: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "reason": "prune_missing_corpus",
        "article_count": len(articles),
        "articles": [
            {
                "id": article.id,
                "title": article.title,
                "doi": article.doi,
                "checksum_sha256": article.checksum_sha256,
                "pdf_original_path": article.pdf_original_path,
                "pdf_ocr_path": article.pdf_ocr_path,
                "status": article.status,
            }
            for article in articles
        ],
        "pages": [
            _model_dict(page)
            for page in session.scalars(
                select(Page).where(Page.article_id.in_(article_ids)).order_by(Page.article_id, Page.page_number)
            )
        ],
        "chunks": [
            _model_dict(chunk)
            for chunk in session.scalars(
                select(Chunk).where(Chunk.article_id.in_(article_ids)).order_by(Chunk.article_id, Chunk.chunk_index)
            )
        ],
        "text_layers": [
            _model_dict(layer)
            for layer in session.scalars(
                select(PageTextLayer)
                .where(PageTextLayer.article_id.in_(article_ids))
                .order_by(PageTextLayer.article_id, PageTextLayer.page_number)
            )
        ],
        "sections": [
            _model_dict(section)
            for section in session.scalars(
                select(Section).where(Section.article_id.in_(article_ids)).order_by(Section.article_id, Section.page_start)
            )
        ],
        "article_tags": [
            _model_dict(tag)
            for tag in session.scalars(
                select(ArticleTag).where(ArticleTag.article_id.in_(article_ids)).order_by(ArticleTag.article_id, ArticleTag.tag_type)
            )
        ],
    }

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"missing_corpus_prune_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    backup_path.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_path


def _delete_articles(session: Session, articles: list[Article]) -> dict[str, int]:
    article_ids = [article.id for article in articles]
    chunk_ids = list(session.scalars(select(Chunk.id).where(Chunk.article_id.in_(article_ids))))
    counts = {"articles": len(article_ids), "chunks": len(chunk_ids)}
    session.execute(delete(Note).where(Note.article_id.in_(article_ids)))
    if chunk_ids:
        session.execute(delete(Note).where(Note.chunk_id.in_(chunk_ids)))
        session.execute(delete(StructuredFact).where(StructuredFact.source_chunk_id.in_(chunk_ids)))
    session.execute(delete(StructuredFact).where(StructuredFact.article_id.in_(article_ids)))
    session.execute(delete(ArticleTag).where(ArticleTag.article_id.in_(article_ids)))
    session.execute(delete(PageTextLayer).where(PageTextLayer.article_id.in_(article_ids)))
    session.execute(delete(Chunk).where(Chunk.article_id.in_(article_ids)))
    session.execute(delete(Page).where(Page.article_id.in_(article_ids)))
    session.execute(delete(Section).where(Section.article_id.in_(article_ids)))
    session.execute(delete(Article).where(Article.id.in_(article_ids)))
    return counts


@cli.command("prune-missing-corpus")
def prune_missing_corpus(apply: bool = False) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        articles = _missing_corpus_articles(session)
        summary: dict[str, object] = {
            "status": "dry_run" if not apply else "pruned",
            "candidate_count": len(articles),
            "candidates": [
                {
                    "article_id": str(article.id),
                    "title": article.title,
                    "pdf_original_path": article.pdf_original_path,
                    "pdf_ocr_path": article.pdf_ocr_path,
                    "original_exists": Path(article.pdf_original_path).exists(),
                    "ocr_exists": bool(article.pdf_ocr_path) and Path(article.pdf_ocr_path or "").exists(),
                }
                for article in articles
            ],
        }
        if not apply or not articles:
            _echo_payload(summary)
            return

        backup_path = _backup_missing_articles(session, articles, settings.data_root / "backups")
        counts = _delete_articles(session, articles)
        session.commit()
        summary["backup_path"] = str(backup_path)
        summary["deleted"] = counts
        _echo_payload(summary)


@cli.command("reselect-text")
def reselect_text(target: Annotated[str, typer.Argument()] = "all") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        articles = _articles_for_target(session, target)
        for article in articles:
            chunk_count = reselect_article_text(session, settings, article)
            _echo_payload({"article_id": str(article.id), "title": article.title, "status": "reselected", "chunk_count": chunk_count})
        session.commit()
        _echo_payload({"summary": {"target": target, "articles": len(articles)}})


@cli.command("text-layers")
def text_layers(article_id: Annotated[UUID, typer.Argument()]) -> None:
    with SessionLocal() as session:
        article = session.scalar(select(Article).where(Article.id == article_id))
        if article is None:
            raise typer.BadParameter(f"Unknown article: {article_id}")
        _echo_payload({"article_id": str(article.id), "title": article.title, "layers": article_text_layer_summary(session, article)})


@cli.command()
def doctor() -> None:
    settings = get_settings()
    _echo_payload(run_doctor(settings, SessionLocal))


if __name__ == "__main__":
    cli()
