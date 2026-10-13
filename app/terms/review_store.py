"""Immutable Terms snapshots and a separate append-only SQLite review ledger."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from app.terms.schema import NonEmpty, Sha256, TermModel

SCHEMA = "tac_terms_review_snapshot_v0.1"
DB_NAME = "terms_decisions.sqlite3"
APPLICATION_ID = int.from_bytes(b"TREV", "big")
Kind = Literal["classification", "relevance"]
Action = Literal["confirm", "correct", "reject", "uncertain", "restore"]


class ReviewConflict(ValueError):
    """Explicit stale source/snapshot or optimistic-concurrency failure."""


class Decision(TermModel):
    snapshot_id: Sha256
    target_kind: Kind
    target_id: Sha256
    expected_revision: int = Field(ge=0)
    action: Action
    categories: list[NonEmpty] = []
    reason: NonEmpty
    reviewer: NonEmpty
    reviewer_kind: Literal["human", "assistant"]
    restore_revision: int | None = Field(default=None, ge=1)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def code_hashes() -> dict[str, str]:
    base = Path(__file__).resolve().parent
    return {name: sha((base / name).read_bytes()) for name in
            ("schema.py", "contexts.py", "classification.py", "taxonomy_v01.json", "review_store.py", "review_projection.py")}


@contextmanager
def connection(root: Path) -> Iterator[sqlite3.Connection]:
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / DB_NAME, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        appid = conn.execute("PRAGMA application_id").fetchone()[0]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if appid not in {0, APPLICATION_ID} or version not in {0, 1} or (appid == 0 and tables):
            raise ReviewConflict("Not a supported Terms review database")
        conn.execute("""CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot TEXT NOT NULL, kind TEXT NOT NULL, target TEXT NOT NULL, revision INTEGER NOT NULL,
            payload TEXT NOT NULL, event_hash TEXT NOT NULL,
            UNIQUE(snapshot, kind, target, revision))""")
        conn.execute("CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON events "
                     "BEGIN SELECT RAISE(ABORT,'Immutable Terms event'); END")
        conn.execute("CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON events "
                     "BEGIN SELECT RAISE(ABORT,'Immutable Terms event'); END")
        conn.execute(f"PRAGMA application_id={APPLICATION_ID}")
        conn.execute("PRAGMA user_version=1")
        conn.commit()
        yield conn
    finally:
        conn.close()


def current_snapshot(root: Path) -> str:
    with connection(root) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='current_snapshot'").fetchone()
        if row is None:
            raise FileNotFoundError("Terms review snapshot not prepared")
        return str(row[0])


def load_snapshot(root: Path, sid: str | None = None) -> tuple[str, dict[str, Any]]:
    sid = sid or current_snapshot(root)
    if not re.fullmatch(r"[0-9a-f]{64}", sid):
        raise ValueError("Invalid Terms snapshot identifier")
    raw = (root / "snapshots" / f"{sid}.json").read_bytes()
    if sha(raw) != sid:
        raise ReviewConflict("Terms snapshot checksum mismatch")
    data: dict[str, Any] = json.loads(raw)
    if data.get("schema") != SCHEMA:
        raise ValueError("Unsupported Terms snapshot schema")
    return sid, data


def register_snapshot(root: Path, data: dict[str, Any]) -> str:
    if data.get("schema") != SCHEMA or data["policy_code_sha256"] != code_hashes():
        raise ValueError("Terms snapshot schema/code binding invalid")
    raw = canonical(data)
    sid = sha(raw)
    path = root / "snapshots" / f"{sid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ReviewConflict("Existing immutable Terms snapshot differs")
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    with connection(root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('current_snapshot',?)", (sid,))
        conn.commit()
    return sid


def target_info(snapshot: dict[str, Any], kind: str, identifier: str) -> dict[str, Any]:
    for article in snapshot["graph"]["articles"]:
        if kind == "classification":
            assignment = next((a for a in article["assignments"] if a["assignment_id"] == identifier), None)
            if assignment is None:
                continue
            use = next(u for u in article["uses"] if u["use_id"] == assignment["use_id"])
            mention = next(m["source"] for m in article["mentions"] if m["mention_id"] == use["mention_id"])
            context = next(c["source"] for c in article["contexts"] if c["context_id"] == use["context_id"])
            sources = [mention, context]
            term_id, axis = assignment["term_id"], assignment["axis"]
        elif kind == "relevance":
            term = next((t for t in article["terms"] if t["term_id"] == identifier), None)
            if term is None:
                continue
            use_ids = set(term["use_ids"])
            mention_ids = {u["mention_id"] for u in article["uses"] if u["use_id"] in use_ids}
            sources = [m["source"] for m in article["mentions"] if m["mention_id"] in mention_ids]
            term_id, axis, assignment = identifier, "relevance", None
        else:
            raise ValueError("Unknown Terms target kind")
        return {"term_id": term_id, "article_id": article["article_id"], "axis": axis, "assignment": assignment,
                "sources": sources, "evidence_sha256": sha(canonical(sources))}
    raise ValueError("Unknown Terms review target")


def source_file(snapshot: dict[str, Any], asset_id: str) -> Path:
    asset = snapshot["assets"].get(asset_id)
    if asset is None:
        raise ValueError("Unknown frozen source asset")
    root = Path(snapshot["source_root"]).resolve()
    path: Path = (root / asset["path"]).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() not in {".pdf", ".png"}:
        raise ReviewConflict("Terms source path outside frozen root")
    if sha(path.read_bytes()) != asset["sha256"]:
        raise ReviewConflict("Terms source file changed; review required")
    return path


def freshness(root: Path, sid: str, snapshot: dict[str, Any]) -> list[str]:
    problems = []
    if current_snapshot(root) != sid:
        problems.append("Snapshot is historical; current input changed. Decisions are not transferred automatically.")
    if snapshot["policy_code_sha256"] != code_hashes():
        problems.append("Terms source/policy/review engine changed; prepare a new snapshot.")
    return problems


def source_problems(snapshot: dict[str, Any], term: str | None = None) -> list[str]:
    assets = set(snapshot["assets"]) if term is None else {
        sha(source[key].encode()) for source in target_info(snapshot, "relevance", term)["sources"]
        for key in ("original_pdf_path", "layer_pdf_path")}
    problems = []
    for asset in sorted(assets):
        if Path(snapshot["assets"][asset]["path"]).suffix.lower() != ".pdf":
            continue
        try:
            source_file(snapshot, asset)
        except (FileNotFoundError, ReviewConflict) as exc:
            problems.append(f"Source requires recheck: {snapshot['assets'][asset]['path']}: {exc}")
    return problems


def snapshot_diff(root: Path, sid: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    current = current_snapshot(root)
    active = snapshot if current == sid else load_snapshot(root, current)[1]
    inputs = {name: {"before": snapshot["input_sha256"].get(name), "current": active["input_sha256"].get(name)}
              for name in set(snapshot["input_sha256"]) | set(active["input_sha256"])
              if snapshot["input_sha256"].get(name) != active["input_sha256"].get(name)}
    installed = code_hashes()
    policy = [name for name, checksum in snapshot["policy_code_sha256"].items() if installed.get(name) != checksum]
    before = {a["assignment_id"] for row in snapshot["graph"]["articles"] for a in row["assignments"]}
    after = {a["assignment_id"] for row in active["graph"]["articles"] for a in row["assignments"]}
    return {"current_snapshot": current, "changed_inputs": inputs, "changed_dependencies": sorted(policy),
            "targets_added": len(after - before), "targets_removed": len(before - after),
            "targets_retained": len(before & after), "automatic_decision_reuse": False}


def history(root: Path, sid: str | None = None, cutoff: int | None = None) -> list[dict[str, Any]]:
    if cutoff is not None and cutoff < 0:
        raise ValueError("Invalid Terms event cutoff")
    with connection(root) as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY event_id").fetchall()
    chains: dict[tuple[str, str, str], tuple[int, str]] = {}
    events = []
    for row in rows:
        payload = json.loads(row["payload"])
        key = (row["snapshot"], row["kind"], row["target"])
        revision, previous = chains.get(key, (0, ""))
        if (row["revision"] != revision + 1 or payload["previous_event_hash"] != previous
                or sha(canonical(payload)) != row["event_hash"]
                or any(payload[k] != row[column] for k, column in
                       (("snapshot_id", "snapshot"), ("target_kind", "kind"), ("target_id", "target"), ("revision", "revision")))):
            raise ReviewConflict("Terms event chain integrity failure")
        chains[key] = (row["revision"], row["event_hash"])
        if (sid is None or row["snapshot"] == sid) and (cutoff is None or row["event_id"] <= cutoff):
            events.append({**payload, "event_id": row["event_id"], "event_hash": row["event_hash"]})
    return events


def latest(root: Path, sid: str, cutoff: int | None = None) -> dict[str, dict[str, Any]]:
    return {f"{e['target_kind']}:{e['target_id']}": e for e in history(root, sid, cutoff)}


def save_decision(root: Path, request: Decision) -> dict[str, Any]:
    sid, snapshot = load_snapshot(root, request.snapshot_id)
    problems = freshness(root, sid, snapshot)
    if problems:
        raise ReviewConflict(" ".join(problems))
    target = target_info(snapshot, request.target_kind, request.target_id)
    if not request.reason.strip() or not request.reviewer.strip() or len(set(request.categories)) != len(request.categories):
        raise ValueError("Terms decision requires reason/reviewer and distinct categories")
    categories = sorted(request.categories)
    effective_action = request.action
    records = history(root, sid)
    prior = [e for e in records if e["target_kind"] == request.target_kind and e["target_id"] == request.target_id]
    if request.action == "restore":
        old = next((e for e in prior if e["revision"] == request.restore_revision), None)
        if old is None or categories:
            raise ValueError("Unknown Terms restore revision or unexpected categories")
        categories, effective_action = old["categories"], old["effective_action"]
    elif request.restore_revision is not None:
        raise ValueError("Restore revision only valid for restore action")
    elif request.target_kind == "relevance":
        if categories or request.action == "correct":
            raise ValueError("Term relevance accepts confirm/reject/uncertain without categories")
    else:
        allowed = set(snapshot["graph"]["taxonomy"]["categories"][target["axis"]]) - {"unclassified", "unresolved"}
        if request.action in {"confirm", "correct"}:
            if not categories or not set(categories) <= allowed:
                raise ValueError("Unknown or missing Terms classification categories")
            proposed = {p["category"] for p in target["assignment"]["proposals"]}
            if request.action == "confirm" and not set(categories) <= proposed:
                raise ValueError("Confirm must choose proposed categories; use correct for a new category")
        elif categories:
            raise ValueError("Reject/uncertain cannot assign categories")
    # Hash both original and selected layer PDFs for this target, even for restore.
    for source in target["sources"]:
        for key in ("original_pdf_path", "layer_pdf_path"):
            asset_id = sha(source[key].encode())
            source_file(snapshot, asset_id)
    with connection(root) as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT value FROM meta WHERE key='current_snapshot'").fetchone()
        if current is None or current[0] != sid:
            raise ReviewConflict("Terms current snapshot changed before commit")
        # A second checksum check inside the write transaction prevents committing
        # against a snapshot replaced between the initial read and the lock.
        load_snapshot(root, sid)
        if snapshot["policy_code_sha256"] != code_hashes():
            raise ReviewConflict("Terms policy/review engine changed before commit")
        for source in target["sources"]:
            for key in ("original_pdf_path", "layer_pdf_path"):
                source_file(snapshot, sha(source[key].encode()))
        row = conn.execute("SELECT revision,event_hash FROM events WHERE snapshot=? AND kind=? AND target=? ORDER BY revision DESC LIMIT 1",
                           (sid, request.target_kind, request.target_id)).fetchone()
        revision = row["revision"] if row else 0
        if revision != request.expected_revision:
            raise ReviewConflict("Terms decision changed in another window; reload before saving")
        payload = {"schema": "tac_terms_review_event_v0.1", "snapshot_id": sid, "target_kind": request.target_kind,
                   "target_id": request.target_id, "revision": revision + 1, "action": request.action,
                   "effective_action": effective_action, "categories": categories, "reason": request.reason.strip(),
                   "reviewer": request.reviewer.strip(), "reviewer_kind": request.reviewer_kind,
                   "restore_revision": request.restore_revision, "term_id": target["term_id"], "axis": target["axis"],
                   "evidence_sha256": target["evidence_sha256"], "previous_event_hash": row["event_hash"] if row else "",
                   "created_at": datetime.now(UTC).isoformat(), "review_scope": "declared_local_review_not_independent_acceptance"}
        checksum = sha(canonical(payload))
        cursor = conn.execute("INSERT INTO events(snapshot,kind,target,revision,payload,event_hash) VALUES (?,?,?,?,?,?)",
                              (sid, request.target_kind, request.target_id, revision + 1, canonical(payload).decode(), checksum))
        conn.commit()
        return {**payload, "event_id": cursor.lastrowid, "event_hash": checksum}
