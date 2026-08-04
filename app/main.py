from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.generation.providers import GenerationOutputError, GenerationUnavailableError
from app.generation.service import answer_question, answer_response_to_dict
from app.retrieval.search import search_chunks, search_response_to_dict
from app.ui import router as ui_router

app = FastAPI(title="Nafion RAG", version="0.1.0")
app.include_router(ui_router)
SessionDep = Annotated[Session, Depends(get_session)]


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    collection: str = "literature"
    top_k: int = Field(default=5, ge=1)
    method: str = "hybrid"


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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
