"""Local Terms workbench with snapshot-bound writes and exact source delivery."""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.core.config import get_settings
from app.terms.review_bundle import graph_view, render_graph, render_table
from app.terms.review_projection import review_queue
from app.terms.review_store import (
    Decision,
    ReviewConflict,
    freshness,
    history,
    latest,
    load_snapshot,
    save_decision,
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
def workbench(request: Request, root: Root, snapshot: str | None = None, view: str = "effective") -> HTMLResponse:
    sid, frozen = read_snapshot(root, snapshot)
    try:
        _, graph = graph_view(root, sid, view, online=True)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    token = request.cookies.get("terms_review_csrf") or secrets.token_urlsafe(32)
    graph["review"].update(online=True, csrf=token, problems=freshness(root, sid, frozen) + source_problems(frozen),
                           diff=snapshot_diff(root, sid, frozen))
    script = (Path(__file__).resolve().parents[1] / "static" / "terms_review.js").read_text(encoding="utf-8")
    response = HTMLResponse(render_graph(frozen, graph, f"/ui/terms-review/table?snapshot={sid}", script))
    response.set_cookie("terms_review_csrf", token, httponly=True, samesite="strict", path="/ui/terms-review")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/ui/terms-review/state")
def state(root: Root, snapshot: str | None = None, term: str | None = None,
          axis: str = "type", queue: str = "conflicts") -> dict[str, Any]:
    sid, frozen = read_snapshot(root, snapshot)
    events = history(root, sid)
    decisions = latest(root, sid)
    prior = [e for e in history(root) if e["snapshot_id"] != sid and (term is None or e["term_id"] == term)] if term else []
    try:
        pending = review_queue(frozen["graph"], decisions, axis, queue)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"snapshot_id": sid, "revision_cutoff": max((e["event_id"] for e in events), default=0),
            "decisions": decisions, "events": [e for e in events if term is None or e["term_id"] == term],
            "historical_annotations": prior, "queue": pending,
            "diff": snapshot_diff(root, sid, frozen),
            "problems": freshness(root, sid, frozen) + (source_problems(frozen, term) if term else [])}


@router.post("/ui/terms-review/decision")
def decision(request: Request, body: Decision, root: Root) -> dict[str, Any]:
    cookie, header = request.cookies.get("terms_review_csrf"), request.headers.get("x-terms-csrf")
    origin = str(request.url).split("/ui/", 1)[0]
    if (request.url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or request.client is None or request.client.host not in {"127.0.0.1", "::1"}
            or request.headers.get("origin") != origin or not cookie or not header or not secrets.compare_digest(cookie, header)):
        raise HTTPException(403, "Terms review requires local same-origin CSRF token")
    try:
        return save_decision(root, body)
    except ReviewConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(409, "Terms source/snapshot missing; review required") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


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
    frozen, graph = graph_view(root, sid, cutoff=cutoff)
    revision = graph["review"]["revision_cutoff"]
    return HTMLResponse(render_table(frozen, sid, latest(root, sid, revision), revision, online=True),
                        headers={"Cache-Control": "no-store"})


@router.get("/ui/terms-review/export")
def export(root: Root, snapshot: str, cutoff: int | None = Query(None, ge=0)) -> JSONResponse:
    sid, frozen = read_snapshot(root, snapshot)
    events = history(root, sid, cutoff)
    return JSONResponse({"schema": "tac_terms_review_export_v0.1", "snapshot_id": sid,
                         "input_sha256": frozen["input_sha256"], "policy_code_sha256": frozen["policy_code_sha256"],
                         "events": events, "decisions": latest(root, sid, cutoff), "independent_acceptance": False},
                        headers={"Content-Disposition": 'attachment; filename="ariadne_terms_review.json"'})
