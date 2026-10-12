"""Immutable numeric review snapshots and a separate, transactional decision log."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ReviewConflict(ValueError):
    pass


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_snapshot(root: Path, snapshot_id: str | None = None) -> tuple[str, dict[str, Any]]:
    if snapshot_id is None:
        snapshot_id = (root / 'current').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'[0-9a-f]{64}', snapshot_id):
        raise ValueError('Invalid snapshot identifier')
    raw = (root / 'snapshots' / f'{snapshot_id}.json').read_bytes()
    if sha(raw) != snapshot_id:
        raise ReviewConflict('Snapshot checksum mismatch')
    snapshot: dict[str, Any] = json.loads(raw)
    if snapshot['schema_version'] != 1:
        raise ValueError('Unsupported review snapshot schema')
    return snapshot_id, snapshot


@contextmanager
def connection(root: Path) -> Iterator[sqlite3.Connection]:
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / 'decisions.sqlite3', timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS decisions (
            snapshot TEXT NOT NULL, item TEXT NOT NULL, revision INTEGER NOT NULL,
            verdict TEXT NOT NULL, comment TEXT NOT NULL, reviewer TEXT NOT NULL,
            page INTEGER NOT NULL, occurrence_start INTEGER NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(snapshot, item, revision))''')
        conn.commit()
        yield conn
    finally:
        conn.close()


def decision_history(root: Path, snapshot_id: str) -> list[dict[str, Any]]:
    with connection(root) as conn:
        return [dict(row) for row in conn.execute(
            'SELECT * FROM decisions WHERE snapshot=? ORDER BY created_at, item, revision', (snapshot_id,),
        )]


def latest_decisions(root: Path, snapshot_id: str) -> dict[str, dict[str, Any]]:
    return {row['item']: row for row in decision_history(root, snapshot_id)}


def save_decision(
    root: Path, *, snapshot_id: str, item_id: str, expected_revision: int,
    verdict: str, comment: str, reviewer: str, page: int, occurrence_start: int,
) -> int:
    _, snapshot = load_snapshot(root, snapshot_id)
    item = next((r for r in snapshot['records'] if r['id'] == item_id), None)
    if item is None:
        raise ValueError('Unknown review item')
    source = snapshot['sources'][item['chunk_id']]
    if (verdict not in {'acceptable', 'blocker', 'ambiguous'} or not comment.strip() or not reviewer.strip()
            or not source['page_start'] <= page <= source['page_end']
            or occurrence_start not in {o['start'] for o in item['occurrences']}):
        raise ValueError('Invalid decision or occurrence')
    with connection(root) as conn:
        # One transaction prevents lost updates across threads/processes.
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT MAX(revision) FROM decisions WHERE snapshot=? AND item=?',
                           (snapshot_id, item_id)).fetchone()
        revision = row[0] or 0
        if revision != expected_revision:
            raise ReviewConflict('Decision changed in another window; reload before saving')
        revision += 1
        conn.execute('INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?)', (
            snapshot_id, item_id, revision, verdict, comment.strip(), reviewer.strip(), page,
            occurrence_start, datetime.now(UTC).isoformat(),
        ))
        conn.commit()
    return revision


def code_hashes() -> dict[str, str]:
    directory = Path(__file__).resolve().parent
    return {name: sha((directory / name).read_bytes()) for name in ('extraction.py', 'context_cues.py')}
