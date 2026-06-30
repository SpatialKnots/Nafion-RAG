from __future__ import annotations

from pathlib import Path

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.evaluation.retrieval import run_retrieval_evaluation, write_evaluation_report

cli = typer.Typer(help="Nafion RAG evaluation commands.")


@cli.callback()
def main() -> None:
    """Run evaluation commands."""


@cli.command()
def retrieval(questions_path: Path, collection: str = "literature", top_k: int = 10) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        report = run_retrieval_evaluation(session, settings, questions_path, collection=collection, top_k=top_k)
    output_path = write_evaluation_report(report, settings.data_root)
    typer.echo({"output_path": str(output_path), "summary": report["summary"]})


if __name__ == "__main__":
    cli()
