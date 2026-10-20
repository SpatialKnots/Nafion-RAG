"""Read-only automatic Terms Atlas, source diagnostics and archival history export."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.core.config import get_settings
from app.terms.review_bundle import automatic_graph_view, render_graph, render_table
from app.terms.review_projection import review_queue
from app.terms.review_store import (
    freshness,
    history,
    latest,
    load_snapshot,
    snapshot_diff,
    source_file,
    source_problems,
)

router = APIRouter()


def review_root() -> Path:
    return get_settings().data_root / "reviews" / "terms"


Root = Annotated[Path, Depends(review_root)]


def read_snapshot(root: Path, sid: str | None) -> tuple[str, dict[str, Any]]:
    try:
        return load_snapshot(root, sid)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Terms review snapshot not prepared or missing") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/ui/terms-review", response_class=HTMLResponse)
def workbench(root: Root, snapshot: str | None = None) -> HTMLResponse:
    sid, frozen = read_snapshot(root, snapshot)
    try:
        _, graph = automatic_graph_view(root, sid, online=True)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    graph["review"].update(online=True, problems=freshness(root, sid, frozen) + source_problems(frozen),
                           diff=snapshot_diff(root, sid, frozen))
    script = (Path(__file__).resolve().parents[1] / "static" / "terms_review.js").read_text(encoding="utf-8")
    response = HTMLResponse(render_graph(frozen, graph, f"/ui/terms-review/table?snapshot={sid}", script))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/ui/terms-review/state")
def state(root: Root, snapshot: str | None = None, term: str | None = None,
          axis: str = "type", queue: str = "conflicts") -> dict[str, Any]:
    sid, frozen = read_snapshot(root, snapshot)
    try:
        _, graph = automatic_graph_view(root, sid)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    try:
        pending = review_queue(graph, {}, axis, queue)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"snapshot_id": sid, "revision_cutoff": 0, "workflow_mode": "automatic",
            "manual_decisions_enabled": False, "decisions": {}, "events": [],
            "historical_annotations": [], "queue": pending,
            "diff": snapshot_diff(root, sid, frozen),
            "problems": freshness(root, sid, frozen) + (source_problems(frozen, term) if term else [])}


@router.post("/ui/terms-review/decision")
def decision() -> None:
    raise HTTPException(410, "Manual Terms decisions are disabled. Classification and subsets are produced automatically.")


@router.get("/ui/terms-review/asset")
def asset(root: Root, snapshot: str, asset: str) -> FileResponse:
    _, frozen = read_snapshot(root, snapshot)
    try:
        path = source_file(frozen, asset)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Frozen Terms source file unavailable") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return FileResponse(path, media_type="application/pdf" if path.suffix.lower() == ".pdf" else "image/png",
                        content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"})


@router.get("/ui/terms-review/table", response_class=HTMLResponse)
def table(root: Root, snapshot: str, cutoff: int | None = Query(None, ge=0)) -> HTMLResponse:
    sid, _ = read_snapshot(root, snapshot)
    if cutoff not in {None, 0}:
        raise HTTPException(422, "Automatic Terms table does not apply manual revision cutoffs; use the archive export.")
    try:
        frozen, _ = automatic_graph_view(root, sid)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return HTMLResponse(render_table(frozen, sid, {}, 0, online=True),
                        headers={"Cache-Control": "no-store"})


@router.get("/ui/terms-review/export")
def export(root: Root, snapshot: str, cutoff: int | None = Query(None, ge=0)) -> JSONResponse:
    sid, frozen = read_snapshot(root, snapshot)
    events = history(root, sid, cutoff)
    return JSONResponse({"schema": "tac_terms_review_export_v0.1", "snapshot_id": sid,
                         "input_sha256": frozen["input_sha256"], "policy_code_sha256": frozen["policy_code_sha256"],
                         "events": events, "decisions": latest(root, sid, cutoff), "independent_acceptance": False},
                        headers={"Content-Disposition": 'attachment; filename="ariadne_terms_review.json"'})
