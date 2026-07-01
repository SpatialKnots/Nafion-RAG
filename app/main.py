from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.retrieval.search import exact_search, search_response_to_dict
from app.ui import router as ui_router

app = FastAPI(title="Nafion RAG", version="0.1.0")
app.include_router(ui_router)
SessionDep = Annotated[Session, Depends(get_session)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
def search(
    session: SessionDep,
    q: str = Query(..., min_length=1),
    collection: str = "literature",
    top_k: int = Query(default=10, ge=1),
) -> dict[str, object]:
    try:
        return search_response_to_dict(exact_search(session, q, collection, top_k))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
