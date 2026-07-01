from __future__ import annotations

import typer
from sqlalchemy import select

from app.classification.report import build_classification_report, write_classification_report
from app.classification.rules import classify_article
from app.core.config import get_settings
from app.db.models import Article, Collection
from app.db.session import SessionLocal

cli = typer.Typer(help="Rule-based scientific classification commands.")


@cli.command("all")
def classify_all(collection: str = "literature") -> None:
    with SessionLocal() as session:
        db_collection = session.scalar(select(Collection).where(Collection.name == collection))
        if db_collection is None:
            raise typer.BadParameter(f"Unknown collection: {collection}")
        articles = list(session.scalars(select(Article).where(Article.collection_id == db_collection.id).order_by(Article.title)))
        for article in articles:
            classify_article(session, article)
            typer.echo({"article_id": str(article.id), "title": article.title, "status": "classified"})
        session.commit()
        typer.echo({"summary": {"collection": collection, "classified": len(articles)}})


@cli.command()
def report(collection: str = "literature") -> None:
    settings = get_settings()
    with SessionLocal() as session:
        payload = build_classification_report(session, collection)
    output_path = write_classification_report(payload, settings.data_root)
    typer.echo({"output_path": str(output_path), "summary": payload["summary"]})


if __name__ == "__main__":
    cli()
