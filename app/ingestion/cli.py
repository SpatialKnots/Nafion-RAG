from __future__ import annotations

from pathlib import Path

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.diagnostics.doctor import run_doctor
from app.ingestion.service import IngestionResult, ingest_pdf

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


def _ingest_one(path: Path, collection: str) -> dict[str, object]:
    settings = get_settings()
    with SessionLocal() as session:
        result = ingest_pdf(session, settings, path, collection)
    return _result_payload(path, result)


@cli.command()
def file(path: Path, collection: str = "literature") -> None:
    typer.echo(_ingest_one(path, collection))


@cli.command()
def folder(path: Path, collection: str = "literature") -> None:
    pdfs = sorted(item for item in path.glob("*.pdf") if item.is_file())
    if not pdfs:
        typer.echo(f"No PDF files found in {path}")
        raise typer.Exit(code=1)
    summary = {"total": len(pdfs), "indexed": 0, "duplicate": 0, "failed": 0}
    for pdf in pdfs:
        try:
            payload = _ingest_one(pdf, collection)
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


@cli.command()
def doctor() -> None:
    settings = get_settings()
    typer.echo(run_doctor(settings, SessionLocal))


if __name__ == "__main__":
    cli()
