from __future__ import annotations

from pathlib import Path

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.evaluation.answers import run_answer_evaluation, write_answer_evaluation_report
from app.evaluation.benchmark import run_search_benchmark, write_benchmark_report
from app.evaluation.retrieval import (
    check_extended_evaluation_thresholds,
    compare_retrieval_methods,
    compare_retrieval_reports,
    load_evaluation_report,
    load_evaluation_thresholds,
    run_extended_retrieval_evaluation,
    run_retrieval_evaluation,
    write_comparison_report,
    write_evaluation_report,
    write_extended_evaluation_report,
)
from app.retrieval.search import SearchFilters

cli = typer.Typer(help="ARIADNE evaluation commands.")


@cli.callback()
def main() -> None:
    """Run evaluation commands."""


@cli.command()
def retrieval(
    questions_path: Path,
    collection: str = "literature",
    top_k: int = 10,
    method: str = "exact",
    doi: str | None = None,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    source_type: str | None = None,
    text_layer: str | None = None,
    tag_type: str | None = None,
    tag_value: str | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
) -> None:
    settings = get_settings()
    filters = SearchFilters.normalize(
        doi=doi,
        year=year,
        year_from=year_from,
        year_to=year_to,
        journal=journal,
        source_type=source_type,
        text_layer=text_layer,
        tag_type=tag_type,
        tag_value=tag_value,
    )
    with SessionLocal() as session:
        report = run_retrieval_evaluation(
            session,
            settings,
            questions_path,
            collection=collection,
            top_k=top_k,
            method=method,
            filters=filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
        )
    output_path = write_evaluation_report(report, settings.data_root)
    typer.echo({"output_path": str(output_path), "summary": report["summary"]})


@cli.command("retrieval-extended")
def retrieval_extended(
    questions_path: Path,
    collection: str = "literature",
    top_k: int = 10,
    method: str = "exact",
    thresholds_path: Path = Path("docs/evaluation_thresholds.yaml"),
    check_thresholds: bool = False,
    doi: str | None = None,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    source_type: str | None = None,
    text_layer: str | None = None,
    tag_type: str | None = None,
    tag_value: str | None = None,
    group_by: str = "none",
    chunks_per_article: int | None = None,
) -> None:
    settings = get_settings()
    filters = SearchFilters.normalize(
        doi=doi,
        year=year,
        year_from=year_from,
        year_to=year_to,
        journal=journal,
        source_type=source_type,
        text_layer=text_layer,
        tag_type=tag_type,
        tag_value=tag_value,
    )
    with SessionLocal() as session:
        report = run_extended_retrieval_evaluation(
            session,
            settings,
            questions_path,
            collection=collection,
            top_k=top_k,
            method=method,
            filters=filters,
            group_by=group_by,
            chunks_per_article=chunks_per_article,
        )
    threshold_failures = []
    if check_thresholds:
        thresholds = load_evaluation_thresholds(thresholds_path, report["settings"]["method"])
        threshold_failures = check_extended_evaluation_thresholds(report, thresholds)
        report["thresholds"] = {"path": str(thresholds_path), "values": thresholds, "failures": threshold_failures}
    output_path = write_extended_evaluation_report(report, settings.data_root)
    typer.echo({"output_path": str(output_path), "summary": report["summary"], "threshold_failures": threshold_failures})
    if threshold_failures:
        raise typer.Exit(code=1)


@cli.command("answers")
def answers(questions_path: Path, collection: str = "literature", top_k: int = 5, method: str = "hybrid") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        report = run_answer_evaluation(
            session,
            settings,
            questions_path,
            collection=collection,
            top_k=top_k,
            method=method,
        )
    output_path = write_answer_evaluation_report(report, settings.data_root)
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


@cli.command()
def benchmark(
    questions_path: Path = Path("docs/evaluation_questions.yaml"),
    collection: str = "literature",
    methods: str = "exact,semantic,hybrid",
    warmup: int = 3,
    runs: int = 10,
    top_k: int = 10,
    output: Path | None = None,
    include_rebuild: bool = False,
    include_ingestion_smoke: bool = False,
) -> None:
    settings = get_settings()
    method_list = [item.strip() for item in methods.split(",") if item.strip()]
    with SessionLocal() as session:
        report = run_search_benchmark(
            session,
            settings,
            questions_path,
            collection=collection,
            methods=method_list,
            warmup=warmup,
            runs=runs,
            top_k=top_k,
        )
    report["optional_scenarios"] = {
        "include_rebuild": include_rebuild,
        "include_ingestion_smoke": include_ingestion_smoke,
        "rebuild": "not_run",
        "ingestion_smoke": "not_run",
    }
    output_path = write_benchmark_report(report, settings.data_root, output)
    typer.echo({"output_path": str(output_path), "methods": list(report["methods"].keys())})


if __name__ == "__main__":
    cli()
