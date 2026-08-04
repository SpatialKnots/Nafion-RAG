from __future__ import annotations

from pathlib import Path

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.evaluation.retrieval import (
    compare_retrieval_methods,
    compare_retrieval_reports,
    load_evaluation_report,
    run_retrieval_evaluation,
    write_comparison_report,
    write_evaluation_report,
)

cli = typer.Typer(help="Nafion RAG evaluation commands.")


@cli.callback()
def main() -> None:
    """Run evaluation commands."""


@cli.command()
def retrieval(questions_path: Path, collection: str = "literature", top_k: int = 10, method: str = "exact") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        report = run_retrieval_evaluation(session, settings, questions_path, collection=collection, top_k=top_k, method=method)
    output_path = write_evaluation_report(report, settings.data_root)
    typer.echo({"output_path": str(output_path), "summary": report["summary"]})


@cli.command()
def compare(exact_report: Path, candidate_report: Path) -> None:
    settings = get_settings()
    report = compare_retrieval_reports(load_evaluation_report(exact_report), load_evaluation_report(candidate_report))
    output_path = write_comparison_report(report, settings.data_root)
    typer.echo({"output_path": str(output_path), "summary": report["summary"]})


@cli.command("compare-methods")
def compare_methods(exact_report: Path, semantic_report: Path, hybrid_report: Path) -> None:
    settings = get_settings()
    report = compare_retrieval_methods(
        load_evaluation_report(exact_report),
        load_evaluation_report(semantic_report),
        load_evaluation_report(hybrid_report),
    )
    output_path = write_comparison_report(report, settings.data_root)
    typer.echo({"output_path": str(output_path), "deltas": report["deltas"]})


if __name__ == "__main__":
    cli()
