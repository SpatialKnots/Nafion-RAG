from __future__ import annotations

from pathlib import Path

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.service import ingest_pdf

cli = typer.Typer(help="Nafion RAG ingestion commands.")


@cli.command()
def file(path: Path, collection: str = "literature") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        result = ingest_pdf(session, settings, path, collection)
    typer.echo(
        {
            "article_id": result.article_id,
            "status": result.status,
            "checksum_sha256": result.checksum_sha256,
            "page_count": result.page_count,
            "chunk_count": result.chunk_count,
            "ocr_required": result.ocr_required,
        }
    )


@cli.command()
def folder(path: Path, collection: str = "literature") -> None:
    pdfs = sorted(item for item in path.glob("*.pdf") if item.is_file())
    if not pdfs:
        typer.echo(f"No PDF files found in {path}")
        raise typer.Exit(code=1)
    for pdf in pdfs:
        file(pdf, collection=collection)


if __name__ == "__main__":
    cli()
