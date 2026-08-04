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
from app.retrieval.index_lifecycle import (
    get_vector_index_state_by_collection_name,
    list_vector_index_states,
    request_vector_rebuild,
    vector_index_state_to_response,
)
from app.retrieval.search import search_chunks, search_response_to_dict
from app.retrieval.vector_index import VectorIndexUnavailableError
from app.ui import router as ui_router

app = FastAPI(title="Nafion RAG", version="0.1.0")
app.include_router(ui_router)
SessionDep = Annotated[Session, Depends(get_session)]


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    collection: str = "literature"
    top_k: int = Field(default=5, ge=1)
    method: str = "hybrid"


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
    source_type: str | None = None,
    method: str = "exact",
) -> dict[str, object]:
    try:
        return search_response_to_dict(
            search_chunks(
                session,
                q,
                collection,
                top_k,
                method=method,
                source_type=source_type,
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
