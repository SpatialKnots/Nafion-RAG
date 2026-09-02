from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article, IngestionJob
from app.db.session import get_session
from app.documents.context import (
    ContextNotFoundError,
    chunk_context_to_dict,
    get_chunk_context,
    get_page_range_context,
    page_range_context_to_dict,
)
from app.documents.service import (
    PageEvidenceNotFoundError,
    PageLayer,
    PdfLayer,
    PdfLayerUnavailableError,
    PdfNotFoundError,
    PdfStorageIntegrityError,
    get_article_page,
    page_evidence_to_dict,
    resolve_article_pdf,
)
from app.generation.providers import GenerationOutputError, GenerationUnavailableError
from app.generation.service import answer_question, answer_response_to_dict
from app.ingestion.queue import enqueue_upload, job_to_response
from app.ingestion.schemas import IngestionJobResponse, JobsResponse, UploadItemResponse, UploadItemStatus, UploadResponse
from app.ingestion.upload import UploadValidationError, remove_staged_file, stage_upload_file
from app.library.schemas import (
    LibraryScanResponse,
    LibrarySourceCreateRequest,
    LibrarySourceFileResponse,
    LibrarySourceFilesResponse,
    LibrarySourceResponse,
    LibrarySourcesResponse,
)
from app.library.service import (
    create_library_source,
    get_library_source,
    library_scan_result_to_response,
    library_source_file_to_response,
    library_source_to_response,
    list_library_source_files,
    list_library_sources,
    scan_and_queue_library_source,
)
from app.retrieval.index_lifecycle import (
    get_vector_index_state_by_collection_name,
    list_vector_index_states,
    request_vector_rebuild,
    vector_index_state_to_response,
)
from app.retrieval.search import SearchFilters, search_chunks, search_response_to_dict
from app.retrieval.vector_index import VectorIndexUnavailableError
from app.ui import router as ui_router

app = FastAPI(title="ARIADNE", version="0.1.0")
app.include_router(ui_router)
SessionDep = Annotated[Session, Depends(get_session)]


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    collection: str = "literature"
    library_source_id: UUID | None = None
    top_k: int = Field(default=5, ge=1)
    method: str = "hybrid_cross_lingual"
    answer_style: str = "claims"
    answer_language: str = "auto"


def _get_article_or_404(session: Session, article_id: UUID) -> Article:
    article = session.scalar(select(Article).where(Article.id == article_id))
    if article is None:
        raise HTTPException(status_code=404, detail=f"Unknown article: {article_id}")
    return article


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
def search(
    session: SessionDep,
    q: str = Query(..., min_length=1),
    collection: str = "literature",
    top_k: int = Query(default=10, ge=1),
    article_id: UUID | None = None,
    library_source_id: UUID | None = None,
    doi: str | None = None,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    journal: str | None = None,
    source_type: str | None = None,
    text_layer: str | None = None,
    tag_type: str | None = None,
    tag_value: str | None = None,
    method: str = "exact",
    group_by: str = "none",
    chunks_per_article: int | None = None,
    include_group_diagnostics: bool = False,
) -> dict[str, object]:
    try:
        if chunks_per_article is not None and chunks_per_article <= 0:
            raise ValueError("chunks_per_article must be positive")
        filters = SearchFilters.normalize(
            article_id=article_id,
            library_source_id=library_source_id,
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
        return search_response_to_dict(
            search_chunks(
                session,
                q,
                collection,
                top_k,
                method=method,
                filters=filters,
                group_by=group_by,
                chunks_per_article=chunks_per_article,
                settings=get_settings(),
            )
        )
    except VectorIndexUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/vector-indexes")
def vector_indexes(session: SessionDep) -> dict[str, object]:
    return {"items": [vector_index_state_to_response(state) for state in list_vector_index_states(session)]}


@app.get("/vector-indexes/{collection}")
def vector_index_detail(session: SessionDep, collection: str, embedding_model: str | None = None) -> dict[str, object]:
    model = embedding_model or get_settings().embedding_model
    try:
        state = get_vector_index_state_by_collection_name(session, collection_name=collection, embedding_model=model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if state is None:
        return {"collection": collection, "embedding_model": model, "status": "missing"}
    return vector_index_state_to_response(state)


@app.post("/vector-indexes/{collection}/rebuild")
def vector_index_rebuild(session: SessionDep, collection: str, embedding_model: str | None = None) -> dict[str, object]:
    model = embedding_model or get_settings().embedding_model
    try:
        state = request_vector_rebuild(session, collection_name=collection, embedding_model=model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return vector_index_state_to_response(state)


@app.get("/libraries")
def libraries(session: SessionDep) -> dict[str, object]:
    return LibrarySourcesResponse(
        items=[LibrarySourceResponse.model_validate(library_source_to_response(source)) for source in list_library_sources(session)]
    ).model_dump()


@app.post("/libraries")
def create_library(session: SessionDep, request: LibrarySourceCreateRequest) -> dict[str, object]:
    try:
        source = create_library_source(
            session,
            get_settings(),
            name=request.name,
            path=request.path,
            collection_name=request.collection,
            recursive=request.recursive,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"Library folder is unavailable: {exc}") from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=f"Library path is not a directory: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return LibrarySourceResponse.model_validate(library_source_to_response(source)).model_dump()


@app.get("/libraries/{library_id}")
def library_detail(session: SessionDep, library_id: UUID) -> dict[str, object]:
    source = get_library_source(session, library_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown library source: {library_id}")
    return LibrarySourceResponse.model_validate(library_source_to_response(source)).model_dump()


@app.get("/libraries/{library_id}/files")
def library_files(session: SessionDep, library_id: UUID) -> dict[str, object]:
    source = get_library_source(session, library_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown library source: {library_id}")
    items = [
        LibrarySourceFileResponse.model_validate(library_source_file_to_response(row))
        for row in list_library_source_files(session, library_id)
    ]
    return LibrarySourceFilesResponse(items=items).model_dump()


@app.post("/libraries/{library_id}/scan")
def library_scan(session: SessionDep, library_id: UUID) -> dict[str, object]:
    try:
        result = scan_and_queue_library_source(session, get_settings(), library_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return LibraryScanResponse.model_validate(library_scan_result_to_response(result)).model_dump()


@app.get("/articles/{article_id}/pdf")
def article_pdf(
    session: SessionDep,
    article_id: UUID,
    layer: Annotated[PdfLayer, Query()] = "original",
) -> FileResponse:
    article = _get_article_or_404(session, article_id)
    try:
        resolved = resolve_article_pdf(article, get_settings(), layer)
    except (PdfLayerUnavailableError, PdfNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PdfStorageIntegrityError as exc:
        raise HTTPException(status_code=500, detail="Stored PDF path is invalid") from exc

    return FileResponse(
        resolved.path,
        media_type=resolved.media_type,
        filename=resolved.download_name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@app.get("/articles/{article_id}/pages/{page_number}")
def article_page_text(
    session: SessionDep,
    article_id: UUID,
    page_number: Annotated[int, Path(ge=1)],
    layer: Annotated[PageLayer, Query()] = "selected",
) -> dict[str, object]:
    article = _get_article_or_404(session, article_id)
    try:
        return page_evidence_to_dict(get_article_page(session, get_settings(), article, page_number, layer))
    except PageEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/articles/{article_id}/chunks/{chunk_id}/context")
def article_chunk_context(
    session: SessionDep,
    article_id: UUID,
    chunk_id: UUID,
    before: int = Query(default=1, ge=0),
    after: int = Query(default=1, ge=0),
    highlight_query: str | None = None,
    max_chars: int | None = Query(default=None, ge=1),
) -> dict[str, object]:
    article = _get_article_or_404(session, article_id)
    try:
        return chunk_context_to_dict(
            get_chunk_context(
                session,
                get_settings(),
                article,
                chunk_id,
                before=before,
                after=after,
                highlight_query=highlight_query,
                max_chars=max_chars,
            )
        )
    except ContextNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/articles/{article_id}/pages/context")
def article_page_range_context(
    session: SessionDep,
    article_id: UUID,
    page_start: int = Query(..., ge=1),
    page_end: int = Query(..., ge=1),
    layer: Annotated[PageLayer, Query()] = "selected",
    highlight_query: str | None = None,
    max_chars: int | None = Query(default=None, ge=1),
) -> dict[str, object]:
    article = _get_article_or_404(session, article_id)
    try:
        return page_range_context_to_dict(
            get_page_range_context(
                session,
                get_settings(),
                article,
                page_start=page_start,
                page_end=page_end,
                layer=layer,
                highlight_query=highlight_query,
                max_chars=max_chars,
            )
        )
    except PageEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ingestion/uploads")
async def upload_pdfs(
    request: Request,
    session: SessionDep,
    files: Annotated[list[UploadFile], File()],
    collection: str = "literature",
) -> dict[str, object]:
    settings = get_settings()
    if len(files) > settings.upload_max_files_per_request:
        raise HTTPException(status_code=413, detail="Too many files in one upload request")
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.upload_max_files_per_request * settings.upload_max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Upload request is too large")

    items: list[UploadItemResponse] = []
    for upload in files:
        staged = None
        filename = upload.filename
        try:
            staged = await stage_upload_file(upload, settings)
            job = enqueue_upload(session, settings, staged, collection)
            session.commit()
            status = cast(UploadItemStatus, "active" if job.status in {"queued", "processing"} else job.status)
            items.append(
                UploadItemResponse(
                    filename=filename,
                    status=status,
                    job=IngestionJobResponse.model_validate(job_to_response(job)),
                )
            )
        except UploadValidationError as exc:
            session.rollback()
            items.append(UploadItemResponse(filename=filename, status="failed", error_code=exc.code, error_message=exc.message))
        except ValueError as exc:
            session.rollback()
            if staged is not None:
                remove_staged_file(staged.path)
            items.append(UploadItemResponse(filename=filename, status="failed", error_code="invalid_request", error_message=str(exc)))
    return UploadResponse(items=items).model_dump()


@app.get("/ingestion/jobs/{job_id}")
def ingestion_job(session: SessionDep, job_id: UUID) -> dict[str, object]:
    job = session.scalar(select(IngestionJob).where(IngestionJob.id == job_id))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown ingestion job: {job_id}")
    return IngestionJobResponse.model_validate(job_to_response(job)).model_dump()


@app.get("/ingestion/jobs")
def ingestion_jobs(
    session: SessionDep,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    statement = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
    if status is not None:
        if status not in {"queued", "processing", "indexed", "duplicate", "failed"}:
            raise HTTPException(status_code=422, detail="Unsupported ingestion job status")
        statement = statement.where(IngestionJob.status == status)
    jobs = list(session.scalars(statement))
    return JobsResponse(items=[IngestionJobResponse.model_validate(job_to_response(job)) for job in jobs]).model_dump()


@app.post("/answer")
def answer(session: SessionDep, request: AnswerRequest) -> dict[str, object]:
    try:
        response = answer_question(
            session,
            get_settings(),
            request.question,
            collection=request.collection,
            top_k=request.top_k,
            method=request.method,
            answer_style=request.answer_style,
            answer_language=request.answer_language,
            library_source_id=request.library_source_id,
        )
        return answer_response_to_dict(response)
    except GenerationUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GenerationOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except VectorIndexUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
