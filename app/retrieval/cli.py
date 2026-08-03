from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.retrieval.vector_index import build_vector_index_manifest, write_vector_index_manifest

cli = typer.Typer(help="Retrieval index planning commands.")


@cli.callback()
def main() -> None:
    """Run retrieval planning commands."""


@cli.command()
def manifest(
    embedding_model: Annotated[str, typer.Option(help="Embedding model identifier recorded in the manifest.")],
    embedding_dimension: Annotated[int, typer.Option(help="Embedding dimension recorded in the manifest.")],
    collection: str = "literature",
    backend: str = "local_vector_index",
    corpus_manifest_path: Path = Path("docs/corpus_manifest.json"),
) -> None:
    settings = get_settings()
    build_command = (
        "python -m app.retrieval.cli manifest "
        f"--embedding-model {embedding_model} --embedding-dimension {embedding_dimension} "
        f"--collection {collection} --backend {backend}"
    )
    with SessionLocal() as session:
        payload = build_vector_index_manifest(
            session,
            collection=collection,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            backend=backend,
            corpus_manifest_path=corpus_manifest_path,
            build_command=build_command,
        )
    output_path = write_vector_index_manifest(payload, settings.data_root)
    typer.echo({"output_path": str(output_path), "summary": {"collection": collection, "chunk_count": payload["chunk_count"]}})


if __name__ == "__main__":
    cli()
