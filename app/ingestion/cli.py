from __future__ import annotations

from typing import Annotated
from pathlib import Path
from uuid import UUID

import typer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article
from app.db.session import SessionLocal
from app.diagnostics.doctor import run_doctor
from app.ingestion.service import IngestionResult, ingest_pdf, reselect_article_text
from app.ingestion.text_layers import article_text_layer_summary

cli = typer.Typer(help="Nafion RAG ingestion commands.")


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
    typer.echo(_ingest_one(path, collection, force_ocr=force_ocr))


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
            typer.echo({"path": str(pdf), "status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
            continue

        status = payload["status"]
        if status in {"indexed", "duplicate"}:
            summary[status] += 1
        typer.echo(payload)

    typer.echo({"summary": summary})
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


@cli.command("reselect-text")
def reselect_text(target: Annotated[str, typer.Argument()] = "all") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        articles = _articles_for_target(session, target)
        for article in articles:
            chunk_count = reselect_article_text(session, settings, article)
            typer.echo({"article_id": str(article.id), "title": article.title, "status": "reselected", "chunk_count": chunk_count})
        session.commit()
        typer.echo({"summary": {"target": target, "articles": len(articles)}})


@cli.command("text-layers")
def text_layers(article_id: Annotated[UUID, typer.Argument()]) -> None:
    with SessionLocal() as session:
        article = session.scalar(select(Article).where(Article.id == article_id))
        if article is None:
            raise typer.BadParameter(f"Unknown article: {article_id}")
        typer.echo({"article_id": str(article.id), "title": article.title, "layers": article_text_layer_summary(session, article)})


@cli.command()
def doctor() -> None:
    settings = get_settings()
    typer.echo(run_doctor(settings, SessionLocal))


if __name__ == "__main__":
    cli()
