from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from json import JSONDecodeError
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import typer
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article, ArticleTag, Chunk, Collection, Note, Page, PageTextLayer, Section, StructuredFact
from app.db.session import SessionLocal
from app.diagnostics.doctor import run_doctor
from app.extraction.text_quality_report import build_reprocess_text_quality_dry_run, build_text_quality_report
from app.ingestion.service import IngestionResult, ingest_pdf, reselect_article_text
from app.ingestion.text_layers import article_text_layer_summary
from app.retrieval.index_lifecycle import mark_vector_index_stale

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


def _latest_retrieval_eval(data_root: Path) -> dict[str, object] | None:
    export_dir = data_root / "exports"
    if not export_dir.exists():
        return None
    reports = sorted(export_dir.glob("retrieval_eval_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not reports:
        return None
    latest = reports[0]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        return {"path": str(latest), "status": "unreadable", "error_type": type(exc).__name__, "error": str(exc)}
    summary = payload.get("summary")
    settings = payload.get("settings")
    return {
        "path": str(latest),
        "status": "loaded",
        "created_at": payload.get("created_at"),
        "summary": summary if isinstance(summary, dict) else None,
        "settings": settings if isinstance(settings, dict) else None,
    }


def _count_by_value(session: Session, column: Any, collection: Collection | None = None) -> dict[str, int]:
    statement = select(column, func.count()).group_by(column).order_by(column)
    if collection is not None:
        statement = statement.join(Article, Chunk.article_id == Article.id).where(Article.collection_id == collection.id)
    return {str(value): count for value, count in session.execute(statement).all()}


def _build_corpus_report(session: Session, data_root: Path, collection_name: str) -> dict[str, object]:
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise typer.BadParameter(f"Unknown collection: {collection_name}")

    articles = list(session.scalars(select(Article).where(Article.collection_id == collection.id).order_by(Article.title)))
    article_ids = [article.id for article in articles]
    pages = session.scalar(select(func.count(Page.id)).where(Page.article_id.in_(article_ids))) if article_ids else 0
    chunks = session.scalar(select(func.count(Chunk.id)).where(Chunk.article_id.in_(article_ids))) if article_ids else 0
    text_layers = (
        session.scalar(select(func.count(PageTextLayer.id)).where(PageTextLayer.article_id.in_(article_ids))) if article_ids else 0
    )
    source_types = _count_by_value(session, Chunk.source_type, collection)
    text_layer_types = _count_by_value(session, Chunk.text_layer, collection)

    article_payloads: list[dict[str, object]] = []
    missing_doi_titles: list[str | None] = []
    missing_original_count = 0
    missing_ocr_count = 0
    for article in articles:
        original_exists = Path(article.pdf_original_path).exists()
        ocr_exists = bool(article.pdf_ocr_path) and Path(article.pdf_ocr_path or "").exists()
        if not article.doi:
            missing_doi_titles.append(article.title)
        if not original_exists:
            missing_original_count += 1
        if article.pdf_ocr_path and not ocr_exists:
            missing_ocr_count += 1
        article_payloads.append(
            {
                "article_id": str(article.id),
                "title": article.title,
                "doi": article.doi,
                "pdf_original_path": article.pdf_original_path,
                "pdf_ocr_path": article.pdf_ocr_path,
                "original_exists": original_exists,
                "ocr_exists": ocr_exists,
                "status": article.status,
            }
        )

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "collection": collection_name,
        "data_root": str(data_root),
        "summary": {
            "articles": len(articles),
            "articles_with_doi": sum(1 for article in articles if article.doi),
            "articles_without_doi": len(missing_doi_titles),
            "pages": int(pages or 0),
            "chunks": int(chunks or 0),
            "text_layers": int(text_layers or 0),
            "missing_original_files": missing_original_count,
            "missing_ocr_files": missing_ocr_count,
        },
        "distributions": {"chunk_source_type": source_types, "chunk_text_layer": text_layer_types},
        "missing_doi_titles": missing_doi_titles,
        "latest_retrieval_eval": _latest_retrieval_eval(data_root),
        "articles": article_payloads,
    }


def _write_corpus_report(report: dict[str, object], data_root: Path) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_dir / f"corpus_report_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path.write_text(json.dumps(_json_ready(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _write_text_quality_report(report: dict[str, object], data_root: Path) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_dir / f"text_quality_report_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path.write_text(json.dumps(_json_ready(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _write_reprocess_report(report: dict[str, object], data_root: Path, article_id: UUID) -> Path:
    export_dir = data_root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_path = export_dir / f"reprocess_text_quality_{article_id}_{timestamp}.json"
    output_path.write_text(json.dumps(_json_ready(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _backup_article_content(session: Session, article: Article, backup_dir: Path, reason: str) -> Path:
    payload: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "reason": reason,
        "article": {
            "id": article.id,
            "title": article.title,
            "doi": article.doi,
            "checksum_sha256": article.checksum_sha256,
            "pdf_original_path": article.pdf_original_path,
            "pdf_ocr_path": article.pdf_ocr_path,
            "status": article.status,
        },
        "pages": [
            _model_dict(page)
            for page in session.scalars(select(Page).where(Page.article_id == article.id).order_by(Page.page_number))
        ],
        "chunks": [
            _model_dict(chunk)
            for chunk in session.scalars(select(Chunk).where(Chunk.article_id == article.id).order_by(Chunk.chunk_index))
        ],
        "text_layers": [
            _model_dict(layer)
            for layer in session.scalars(
                select(PageTextLayer)
                .where(PageTextLayer.article_id == article.id)
                .order_by(PageTextLayer.page_number, PageTextLayer.layer_type)
            )
        ],
        "sections": [
            _model_dict(section)
            for section in session.scalars(select(Section).where(Section.article_id == article.id).order_by(Section.page_start))
        ],
        "article_tags": [
            _model_dict(tag)
            for tag in session.scalars(select(ArticleTag).where(ArticleTag.article_id == article.id).order_by(ArticleTag.tag_type))
        ],
    }
    backup_dir.mkdir(parents=True, exist_ok=True)
    output_path = backup_dir / f"article_reprocess_{article.id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _article_counts(session: Session, article_ids: list[UUID], model: Any) -> dict[UUID, int]:
    if not article_ids:
        return {}
    rows = session.execute(
        select(model.article_id, func.count(model.id)).where(model.article_id.in_(article_ids)).group_by(model.article_id)
    )
    return {article_id: int(count) for article_id, count in rows.all()}


def _build_corpus_manifest(session: Session, collection_name: str) -> dict[str, object]:
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise typer.BadParameter(f"Unknown collection: {collection_name}")

    articles = list(
        session.scalars(select(Article).where(Article.collection_id == collection.id).order_by(Article.title, Article.checksum_sha256))
    )
    article_ids = [article.id for article in articles]
    page_counts = _article_counts(session, article_ids, Page)
    chunk_counts = _article_counts(session, article_ids, Chunk)
    text_layer_counts = _article_counts(session, article_ids, PageTextLayer)

    article_payloads: list[dict[str, object]] = [
        {
            "checksum_sha256": article.checksum_sha256,
            "title": article.title,
            "doi": article.doi,
            "pdf_original_basename": Path(article.pdf_original_path).name,
            "pdf_ocr_basename": Path(article.pdf_ocr_path).name if article.pdf_ocr_path else None,
            "status": article.status,
            "page_count": page_counts.get(article.id, 0),
            "chunk_count": chunk_counts.get(article.id, 0),
            "text_layer_count": text_layer_counts.get(article.id, 0),
        }
        for article in articles
    ]
    page_total = sum(page_counts.get(article.id, 0) for article in articles)
    chunk_total = sum(chunk_counts.get(article.id, 0) for article in articles)
    text_layer_total = sum(text_layer_counts.get(article.id, 0) for article in articles)

    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "collection": collection_name,
        "summary": {
            "articles": len(article_payloads),
            "articles_with_doi": sum(1 for article in article_payloads if article["doi"]),
            "articles_without_doi": sum(1 for article in article_payloads if not article["doi"]),
            "pages": page_total,
            "chunks": chunk_total,
            "text_layers": text_layer_total,
        },
        "articles": article_payloads,
    }


def _write_corpus_manifest(manifest: dict[str, object], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(_json_ready(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def _manifest_comparable(manifest: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in manifest.items() if key != "created_at"}


def _manifest_articles_by_checksum(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    articles = manifest.get("articles")
    if not isinstance(articles, list):
        return {}
    result: dict[str, dict[str, object]] = {}
    for article in articles:
        if isinstance(article, dict) and isinstance(article.get("checksum_sha256"), str):
            result[article["checksum_sha256"]] = article
    return result


def _compare_corpus_manifest(current: dict[str, object], expected: dict[str, object]) -> dict[str, object]:
    current_articles = _manifest_articles_by_checksum(current)
    expected_articles = _manifest_articles_by_checksum(expected)
    current_checksums = set(current_articles)
    expected_checksums = set(expected_articles)
    shared_checksums = sorted(current_checksums & expected_checksums)

    changed_articles = [
        {
            "checksum_sha256": checksum,
            "expected": expected_articles[checksum],
            "current": current_articles[checksum],
        }
        for checksum in shared_checksums
        if current_articles[checksum] != expected_articles[checksum]
    ]
    diagnostics = {
        "status": "match",
        "summary_changed": current.get("summary") != expected.get("summary"),
        "missing_articles": [expected_articles[checksum] for checksum in sorted(expected_checksums - current_checksums)],
        "extra_articles": [current_articles[checksum] for checksum in sorted(current_checksums - expected_checksums)],
        "changed_articles": changed_articles,
    }
    if (
        diagnostics["summary_changed"]
        or diagnostics["missing_articles"]
        or diagnostics["extra_articles"]
        or diagnostics["changed_articles"]
        or _manifest_comparable(current) != _manifest_comparable(expected)
    ):
        diagnostics["status"] = "mismatch"
    return diagnostics


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
        collection_ids = sorted(
            {collection_id for article in articles if (collection_id := getattr(article, "collection_id", None)) is not None}
        )
        counts = _delete_articles(session, articles)
        embedding_model = getattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
        for collection_id in collection_ids:
            mark_vector_index_stale(session, collection_id=collection_id, embedding_model=embedding_model)
        session.commit()
        summary["backup_path"] = str(backup_path)
        summary["deleted"] = counts
        _echo_payload(summary)


@cli.command("corpus-report")
def corpus_report(collection: str = "literature") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        report = _build_corpus_report(session, settings.data_root, collection)
    output_path = _write_corpus_report(report, settings.data_root)
    _echo_payload({"output_path": str(output_path), "summary": report["summary"], "latest_retrieval_eval": report["latest_retrieval_eval"]})


@cli.command("text-quality-report")
def text_quality_report(collection: str = "literature") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        report = build_text_quality_report(session, settings, collection)
    output_path = _write_text_quality_report(report, settings.data_root)
    _echo_payload(
        {
            "output_path": str(output_path),
            "summary": {
                "collection": report["collection"],
                "article_count": report["article_count"],
                "page_count": report["page_count"],
                "empty_original_page_count": report["empty_original_page_count"],
                "short_original_page_count": report["short_original_page_count"],
                "ocr_used_pages": report["ocr_used_pages"],
                "suspicious_page_count": report["suspicious_page_count"],
            },
        }
    )


@cli.command("reprocess-article")
def reprocess_article(
    article_id: Annotated[UUID, typer.Argument()],
    mode: str = "text-quality",
    apply: bool = False,
) -> None:
    if mode != "text-quality":
        raise typer.BadParameter("mode must be text-quality")

    settings = get_settings()
    with SessionLocal() as session:
        article = session.scalar(select(Article).where(Article.id == article_id))
        if article is None:
            raise typer.BadParameter(f"Unknown article: {article_id}")
        report = build_reprocess_text_quality_dry_run(session, settings, article)
        if apply:
            backup_path = _backup_article_content(session, article, settings.data_root / "backups", "reprocess_article_text_quality")
            try:
                chunk_count = reselect_article_text(session, settings, article)
                session.commit()
            except Exception:
                session.rollback()
                raise
            _echo_payload(
                {
                    "status": "reprocessed",
                    "article_id": str(article_id),
                    "mode": mode,
                    "backup_path": str(backup_path),
                    "chunk_count": chunk_count,
                    "dry_run_report": {
                        "current_counts": report["current_counts"],
                        "candidate_actions": report["candidate_actions"],
                    },
                    "vector_index": "marked_stale",
                }
            )
            return
    output_path = _write_reprocess_report(report, settings.data_root, article_id)
    _echo_payload(
        {
            "status": "dry_run",
            "output_path": str(output_path),
            "article_id": str(article_id),
            "mode": mode,
            "current_counts": report["current_counts"],
            "candidate_actions": report["candidate_actions"],
        }
    )


@cli.command("corpus-manifest")
def corpus_manifest(
    output: Path = Path("docs/corpus_manifest.json"),
    check: Annotated[Path | None, typer.Option(help="Compare current corpus against an existing manifest.")] = None,
    collection: str = "literature",
) -> None:
    with SessionLocal() as session:
        manifest = _build_corpus_manifest(session, collection)

    if check is None:
        output_path = _write_corpus_manifest(manifest, output)
        _echo_payload({"status": "written", "output_path": str(output_path), "summary": manifest["summary"]})
        return

    if not check.exists():
        _echo_payload({"status": "missing_manifest", "path": str(check)})
        raise typer.Exit(code=1)
    try:
        expected = json.loads(check.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        _echo_payload({"status": "invalid_manifest", "path": str(check), "error_type": type(exc).__name__, "error": str(exc)})
        raise typer.Exit(code=1) from exc
    if not isinstance(expected, dict):
        _echo_payload({"status": "invalid_manifest", "path": str(check), "error": "manifest root must be a JSON object"})
        raise typer.Exit(code=1)
    diagnostics = _compare_corpus_manifest(manifest, expected)
    _echo_payload(diagnostics)
    if diagnostics["status"] != "match":
        raise typer.Exit(code=1)


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
