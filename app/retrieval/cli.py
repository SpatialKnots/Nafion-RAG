from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.retrieval.index_cleanup import cleanup_vector_index_generations
from app.retrieval.index_lifecycle import (
    complete_vector_rebuild,
    get_vector_index_state_by_collection_name,
    request_vector_rebuild,
    vector_index_state_to_response,
)
from app.retrieval.vector_index import (
    build_local_vector_index,
    build_local_vector_index_generation,
    build_vector_index_manifest,
    write_vector_index_manifest,
)

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


@cli.command()
def build(
    embedding_model: Annotated[str, typer.Option(help="FastEmbed model identifier used to build local vectors.")] = (
        "BAAI/bge-small-en-v1.5"
    ),
    collection: str = "literature",
    batch_size: int = 64,
    backend: str = "local_vector_index",
    corpus_manifest_path: Path = Path("docs/corpus_manifest.json"),
) -> None:
    settings = get_settings()
    build_command = (
        "python -m app.retrieval.cli build "
        f"--embedding-model {embedding_model} --collection {collection} "
        f"--batch-size {batch_size} --backend {backend}"
    )
    with SessionLocal() as session:
        output_path = build_local_vector_index(
            session,
            data_root=settings.data_root,
            collection=collection,
            embedding_model=embedding_model,
            backend=backend,
            corpus_manifest_path=corpus_manifest_path,
            build_command=build_command,
            batch_size=batch_size,
        )
    typer.echo({"output_path": str(output_path), "summary": {"collection": collection, "embedding_model": embedding_model}})


@cli.command("status")
def status(collection: str = "literature", embedding_model: str | None = None) -> None:
    settings = get_settings()
    model = embedding_model or settings.embedding_model
    with SessionLocal() as session:
        state = get_vector_index_state_by_collection_name(session, collection_name=collection, embedding_model=model)
        if state is None:
            typer.echo({"collection": collection, "embedding_model": model, "status": "missing"})
            raise typer.Exit(code=1)
        typer.echo(vector_index_state_to_response(state))


@cli.command("rebuild-request")
def rebuild_request(collection: str = "literature", embedding_model: str | None = None) -> None:
    settings = get_settings()
    model = embedding_model or settings.embedding_model
    with SessionLocal() as session:
        state = request_vector_rebuild(session, collection_name=collection, embedding_model=model)
        session.commit()
        typer.echo(vector_index_state_to_response(state))


@cli.command("build-generation")
def build_generation(
    collection: str = "literature",
    embedding_model: str | None = None,
    batch_size: int | None = None,
) -> None:
    settings = get_settings()
    model = embedding_model or settings.embedding_model
    size = batch_size or settings.vector_rebuild_batch_size
    with SessionLocal() as session:
        state = request_vector_rebuild(session, collection_name=collection, embedding_model=model)
        state.status = "rebuilding"
        state.building_revision = state.desired_revision
        generation = build_local_vector_index_generation(
            session,
            data_root=settings.data_root,
            collection=collection,
            embedding_model=model,
            target_revision=state.building_revision,
            batch_size=size,
            build_command="python -m app.retrieval.cli build-generation",
        )
        complete_vector_rebuild(state, generation_id=generation.generation_id, manifest_sha256=generation.manifest_sha256)
        session.commit()
        typer.echo(vector_index_state_to_response(state))


@cli.command("cleanup")
def cleanup(apply: bool = False) -> None:
    settings = get_settings()
    with SessionLocal() as session:
        typer.echo(cleanup_vector_index_generations(session, settings, apply=apply))


if __name__ == "__main__":
    cli()
