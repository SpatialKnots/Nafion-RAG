"""Separate append-only full-record revisions; no production or Terms writes."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from app.records.checks import RecordCheckReport, check_bundle
from app.records.schema import CandidateBundle, ContractModel, EvidenceSpan, NonEmpty, RecordCandidate, Sha256
from app.records.sources import file_hash
from app.records.table_export import export_table

VERSION = "records_revision_store_v0.1"
DB_NAME = "record_revisions.sqlite3"
APPLICATION_ID = int.from_bytes(b"RREV", "big")
ReviewStatus = Literal["unreviewed", "confirmed", "rejected", "needs_changes"]
_FILES = ("schema.py", "checks.py", "readiness.py", "review.py", "sources.py", "table_export.py", "revision_store.py", "revision_ui.py")


class RevisionConflict(ValueError):
    """Explicit stale revision/context or invalid scientific review transition."""


class RevisionRequest(ContractModel):
    snapshot_id: Sha256
    record_key: NonEmpty
    expected_revision: int = Field(ge=0)
    action: Literal["edit", "decide", "restore"]
    actor: NonEmpty
    actor_kind: Literal["human", "assistant"]
    reason: NonEmpty
    candidate: RecordCandidate | None = None
    decision: ReviewStatus | None = None
    restore_revision: int | None = Field(default=None, ge=0)
    source_reviewed: bool = False

    @model_validator(mode="after")
    def validate_action(self) -> RevisionRequest:
        if not self.actor.strip() or not self.reason.strip():
            raise ValueError("Actor and reason must not be whitespace")
        if self.action == "edit":
            valid = self.candidate is not None and self.decision is None and self.restore_revision is None
        elif self.action == "decide":
            valid = self.candidate is None and self.decision is not None and self.restore_revision is None
        else:
            valid = self.candidate is None and self.decision is None and self.restore_revision is not None
        if not valid:
            raise ValueError("Payload fields do not match revision action")
        return self


class RevisionEvent(ContractModel):
    snapshot_id: Sha256
    record_key: NonEmpty
    revision: int = Field(ge=1)
    previous_event_hash: str
    created_at: datetime
    action: Literal["edit", "decide", "restore"]
    actor: NonEmpty
    actor_kind: Literal["human", "assistant"]
    reason: NonEmpty
    source_reviewed: bool
    restore_revision: int | None = Field(default=None, ge=0)
    candidate: RecordCandidate
    checks: RecordCheckReport
    declared_review_status: ReviewStatus


def canonical(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def code_hashes() -> dict[str, str]:
    base = Path(__file__).resolve().parent
    return {name: file_hash(base / name) for name in _FILES}


@contextmanager
def connection(root: Path, *, writable: bool = False) -> Iterator[sqlite3.Connection]:
    # mode=rw/ro never creates or repairs an absent database.
    uri = (root / DB_NAME).resolve().as_uri() + ("?mode=rw" if writable else "?mode=ro")
    conn = sqlite3.connect(uri, uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        if (conn.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or conn.execute("PRAGMA user_version").fetchone()[0] != 1):
            raise RevisionConflict("Unsupported record revision database")
        yield conn
    finally:
        conn.close()


def initialize_store(inputs: Sequence[Path], root: Path, *, source_root: Path) -> str:
    if root.exists():
        raise FileExistsError(f"Record review directory already exists: {root}")
    # Validation failure can leave a partial directory, never a valid initialized DB.
    export_table(inputs, root / "baseline", source_root=source_root)
    snapshot = {"version": VERSION, "baseline_table_sha256": file_hash(root / "baseline/table.json"),
                "baseline_manifest_sha256": file_hash(root / "baseline/manifest.json"), "code": code_hashes()}
    raw = canonical(snapshot)
    snapshot_id = digest(raw)
    with (root / "snapshot.json").open("xb") as stream:
        stream.write(raw)
    conn = sqlite3.connect(root / DB_NAME)
    try:
        with conn:
            conn.execute("CREATE TABLE meta (snapshot_id TEXT NOT NULL)")
            conn.execute("INSERT INTO meta VALUES (?)", (snapshot_id,))
            conn.execute("""CREATE TABLE events (
                event_id INTEGER PRIMARY KEY, record_key TEXT NOT NULL, revision INTEGER NOT NULL,
                payload TEXT NOT NULL, event_hash TEXT NOT NULL, UNIQUE(record_key, revision))""")
            conn.execute("CREATE TRIGGER immutable_update BEFORE UPDATE ON events "
                         "BEGIN SELECT RAISE(ABORT,'Immutable record revision'); END")
            conn.execute("CREATE TRIGGER immutable_delete BEFORE DELETE ON events "
                         "BEGIN SELECT RAISE(ABORT,'Immutable record revision'); END")
            conn.execute(f"PRAGMA application_id={APPLICATION_ID}")
            conn.execute("PRAGMA user_version=1")
    finally:
        conn.close()
    return snapshot_id


def _baseline(root: Path) -> tuple[str, dict[str, Any], dict[str, Any], bool]:
    raw = (root / "snapshot.json").read_bytes()
    snapshot_id = digest(raw)
    snapshot = json.loads(raw)
    if snapshot["version"] != VERSION:
        raise RevisionConflict("Unsupported record review snapshot")
    for name, key in (("table.json", "baseline_table_sha256"), ("manifest.json", "baseline_manifest_sha256")):
        if file_hash(root / "baseline" / name) != snapshot[key]:
            raise RevisionConflict(f"Changed record baseline: {name}")
    manifest = json.loads((root / "baseline/manifest.json").read_bytes())
    for name, expected in manifest["outputs"].items():
        path = (root / "baseline" / name).resolve()
        if not path.is_relative_to((root / "baseline").resolve()) or file_hash(path) != expected:
            raise RevisionConflict(f"Changed baseline artifact: {name}")
    for pdf in manifest["pdfs"]:
        if file_hash(Path(pdf["path"])) != pdf["sha256"]:
            raise RevisionConflict(f"Changed source PDF: {pdf['path']}")
    report = json.loads((root / "baseline/table.json").read_bytes())
    return snapshot_id, snapshot, report, snapshot["code"] != code_hashes()


def _validate_candidate(case: dict[str, Any], candidate: RecordCandidate) -> RecordCheckReport:
    data = dict(case["candidate_bundle"])
    data["records"] = [candidate.model_dump(mode="json")]
    return check_bundle(CandidateBundle.model_validate(data))[0]


def _state(root: Path, conn: sqlite3.Connection) -> dict[str, Any]:
    sid, snapshot, baseline, stale = _baseline(root)
    meta = conn.execute("SELECT snapshot_id FROM meta").fetchall()
    if len(meta) != 1 or meta[0]["snapshot_id"] != sid:
        raise RevisionConflict("Record snapshot/database context mismatch")
    states: dict[str, dict[str, Any]] = {}
    cases = {}
    for case in baseline["cases"]:
        bundle = CandidateBundle.model_validate(case["candidate_bundle"])
        cases[case["case_id"]] = case
        for record, checks in zip(bundle.records, check_bundle(bundle), strict=True):
            key = f"{case['case_id']}:{record.record_id}"
            states[key] = {"record_key": key, "case_id": case["case_id"], "revision": 0,
                           "original_candidate": record.model_dump(mode="json"), "candidate": record.model_dump(mode="json"),
                           "checks": checks.model_dump(mode="json"), "declared_review_status": "unreviewed", "history": []}
    previous: dict[str, str] = {}
    for row in conn.execute("SELECT * FROM events ORDER BY event_id"):
        raw = row["payload"].encode("utf-8")
        if digest(raw) != row["event_hash"]:
            raise RevisionConflict("Changed record revision event hash")
        event = RevisionEvent.model_validate_json(raw)
        key = event.record_key
        if key not in states:
            raise RevisionConflict("Unknown record in revision history")
        current = states[key]
        if (event.snapshot_id != sid or row["record_key"] != key or row["revision"] != event.revision
                or event.revision != current["revision"] + 1 or event.previous_event_hash != previous.get(key, "")):
            raise RevisionConflict("Broken record revision/context chain")
        _assert_identity(event.candidate, current["original_candidate"])
        if event.created_at.utcoffset() is None or not event.actor.strip() or not event.reason.strip():
            raise RevisionConflict("Malformed revision actor/reason/timestamp")
        checks = _validate_candidate(cases[current["case_id"]], event.candidate)
        if not stale and checks != event.checks:
            raise RevisionConflict("Saved checks do not match record revision")
        if event.action in {"edit", "restore"} and event.declared_review_status != "unreviewed":
            raise RevisionConflict("Edited/restored record retained a decision")
        if event.action == "decide" and (event.candidate.model_dump(mode="json") != current["candidate"]
                                         or event.restore_revision is not None):
            raise RevisionConflict("Decision changed candidate content")
        if event.action == "edit" and (event.candidate.model_dump(mode="json") == current["candidate"]
                                       or event.restore_revision is not None):
            raise RevisionConflict("Invalid edit in revision history")
        if event.action == "restore":
            target = current["original_candidate"] if event.restore_revision == 0 else next(
                (old["candidate"] for old in current["history"] if old["revision"] == event.restore_revision), None)
            if target is None or event.candidate.model_dump(mode="json") != target:
                raise RevisionConflict("Restore does not match a historical candidate")
        if event.declared_review_status == "confirmed":
            if (event.actor_kind != "human" or not event.source_reviewed
                    or event.checks.technical_outcome == "incomplete" or event.action != "decide"):
                raise RevisionConflict("Invalid human confirmation in revision history")
        current.update(revision=event.revision, candidate=event.candidate.model_dump(mode="json"),
                       checks=event.checks.model_dump(mode="json"), declared_review_status=event.declared_review_status)
        current["history"].append(event.model_dump(mode="json") | {"event_hash": row["event_hash"]})
        previous[key] = row["event_hash"]
    return {"version": VERSION, "snapshot_id": sid, "context": snapshot, "stale_code": stale,
            "scientific_admission": "not_evaluated", "baseline": baseline, "records": list(states.values())}


def load_state(root: Path) -> dict[str, Any]:
    with connection(root) as conn:
        # A consistent SQLite read snapshot across metadata and the complete event history.
        conn.execute("BEGIN")
        return _state(root, conn)


def _assert_identity(candidate: RecordCandidate, original: dict[str, Any]) -> None:
    if str(candidate.record_id) != original["record_id"] or str(candidate.article_id) != original["article_id"]:
        raise RevisionConflict("Record/article identity cannot be edited")


def save_revision(root: Path, request: RevisionRequest) -> dict[str, Any]:
    request = RevisionRequest.model_validate_json(request.model_dump_json())
    with connection(root, writable=True) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        state = _state(root, conn)
        if request.snapshot_id != state["snapshot_id"] or state["stale_code"]:
            raise RevisionConflict("Changed record snapshot/code; create a separately versioned review context")
        current = next((item for item in state["records"] if item["record_key"] == request.record_key), None)
        if current is None:
            raise RevisionConflict("Unknown record key")
        if current["revision"] != request.expected_revision:
            raise RevisionConflict(f"Stale revision: expected {request.expected_revision}, current {current['revision']}")
        candidate = RecordCandidate.model_validate(current["candidate"])
        status: ReviewStatus = "unreviewed"
        if request.action == "edit":
            assert request.candidate is not None
            if request.candidate == candidate:
                raise RevisionConflict("Edit contains no candidate changes")
            candidate = request.candidate
        elif request.action == "restore":
            if request.restore_revision == 0:
                candidate = RecordCandidate.model_validate(current["original_candidate"])
            else:
                old = next((event for event in current["history"] if event["revision"] == request.restore_revision), None)
                if old is None:
                    raise RevisionConflict("Unknown restore revision")
                candidate = RecordCandidate.model_validate(old["candidate"])
        else:
            assert request.decision is not None
            status = request.decision
        _assert_identity(candidate, current["original_candidate"])
        case = next(case for case in state["baseline"]["cases"] if case["case_id"] == current["case_id"])
        checks = _validate_candidate(case, candidate)
        if status == "confirmed" and (request.actor_kind != "human" or not request.source_reviewed
                                      or checks.technical_outcome == "incomplete"):
            raise RevisionConflict("Confirmation requires a declared human, source-review attestation and complete technical prerequisites")
        event = RevisionEvent(
            snapshot_id=state["snapshot_id"], record_key=request.record_key, revision=current["revision"] + 1,
            previous_event_hash=current["history"][-1]["event_hash"] if current["history"] else "",
            created_at=datetime.now(UTC), action=request.action, actor=request.actor, actor_kind=request.actor_kind,
            reason=request.reason, source_reviewed=request.source_reviewed, restore_revision=request.restore_revision,
            candidate=candidate, checks=checks, declared_review_status=status,
        )
        payload = canonical(event.model_dump(mode="json"))
        event_hash = digest(payload)
        # Recheck immutable source/context files immediately before inserting the event.
        if _baseline(root)[0] != state["snapshot_id"] or code_hashes() != state["context"]["code"]:
            raise RevisionConflict("Record context changed during save")
        conn.execute("INSERT INTO events(record_key,revision,payload,event_hash) VALUES (?,?,?,?)",
                     (request.record_key, event.revision, payload.decode("utf-8"), event_hash))
        return event.model_dump(mode="json") | {"event_hash": event_hash}


def locate_evidence(bundle: CandidateBundle, region_id: str, quote: str, occurrence: int) -> EvidenceSpan:
    if not quote or occurrence < 1:
        raise ValueError("Exact nonempty quote and positive occurrence are required")
    region = next((item for item in bundle.regions if item.region_id == region_id), None)
    if region is None:
        raise ValueError("Unknown frozen source region")
    start = -1
    for _ in range(occurrence):
        start = region.quote.find(quote, start + 1)
        if start < 0:
            raise ValueError("Requested exact source occurrence not found; text was not normalized")
    return EvidenceSpan(region_id=region_id, start=start, end=start + len(quote), quote=quote)


def export_review(root: Path) -> dict[str, Any]:
    state = load_state(root)
    if state["stale_code"]:
        raise RevisionConflict("Cannot export applied reviews under changed code")
    return {"export_version": "records_review_export_v0.1", **state,
            "review_identity": "Caller-declared; not authenticated or independently certified",
            "csv_policy": "Formula-like cells have a leading apostrophe; csv_escaped_columns declares them. JSON remains exact."}


def review_csv(data: dict[str, Any]) -> str:
    from app.records.review import observations_for_review

    rows: list[dict[str, str]] = []
    for item in data["records"]:
        record = RecordCandidate.model_validate(item["candidate"])
        row = {"record_key": item["record_key"], "revision": str(item["revision"]), "snapshot_id": data["snapshot_id"],
               "record_id": str(record.record_id), "article_id": str(record.article_id),
               "declared_review_status": item["declared_review_status"], "candidate_review_state": record.review_state,
               "scientific_admission": "not_evaluated", "li_ion_confirmation": record.li_ion_confirmation,
               "technical_outcome": item["checks"]["technical_outcome"], "representation": record.value.representation,
               "evidence_json_pointer": f"review.json#/records/{len(rows)}"}
        last = item["history"][-1] if item["history"] else {}
        row.update(actor=last.get("actor", ""), actor_kind=last.get("actor_kind", ""), reason=last.get("reason", ""))
        for name, observation in observations_for_review(record):
            row[name] = observation.raw_text or ""
            row[name + ".status"] = observation.status
        escaped = []
        for key, value in row.items():
            if value[:1] in {"\t", "\r", "\n"} or value.lstrip()[:1] in {"=", "+", "-", "@"}:
                row[key] = "'" + value
                escaped.append(key)
        row["csv_escaped_columns"] = json.dumps(escaped)
        rows.append(row)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]) if rows else ["record_key", "revision", "declared_review_status"],
                            quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
