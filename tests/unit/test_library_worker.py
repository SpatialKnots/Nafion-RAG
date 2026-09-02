from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.db.models import LibrarySource
from app.library.worker import process_one_library_scan


class FakeSession:
    def __init__(self, sources: list[LibrarySource]) -> None:
        self.sources = sources
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def test_process_one_library_scan_scans_due_source(monkeypatch) -> None:
    source = _source(last_scan_at=None)
    session = FakeSession([source])
    calls: list[tuple[uuid.UUID, int]] = []
    monkeypatch.setattr("app.library.worker.list_library_sources", lambda active_session: active_session.sources)

    def fake_scan(active_session: object, settings: object, library_source_id: uuid.UUID, *, queue_limit: int | None = None) -> object:
        calls.append((library_source_id, queue_limit or 0))
        return SimpleNamespace()

    monkeypatch.setattr("app.library.worker.scan_and_queue_library_source", fake_scan)

    did_work = process_one_library_scan(session, _settings(library_scan_batch_size=25))  # type: ignore[arg-type]

    assert did_work is True
    assert calls == [(source.id, 25)]
    assert session.commits == 1


def test_process_one_library_scan_skips_recent_source(monkeypatch) -> None:
    source = _source(last_scan_at=datetime.now(UTC))
    session = FakeSession([source])
    monkeypatch.setattr("app.library.worker.list_library_sources", lambda active_session: active_session.sources)

    did_work = process_one_library_scan(session, _settings(library_scan_interval_seconds=60))  # type: ignore[arg-type]

    assert did_work is False
    assert session.commits == 0


def test_process_one_library_scan_skips_disabled_source(monkeypatch) -> None:
    source = _source(last_scan_at=None, enabled=False)
    session = FakeSession([source])
    monkeypatch.setattr("app.library.worker.list_library_sources", lambda active_session: active_session.sources)

    did_work = process_one_library_scan(session, _settings())  # type: ignore[arg-type]

    assert did_work is False
    assert session.commits == 0


def test_process_one_library_scan_obeys_global_disable(monkeypatch) -> None:
    source = _source(last_scan_at=None)
    session = FakeSession([source])
    monkeypatch.setattr("app.library.worker.list_library_sources", lambda active_session: active_session.sources)

    did_work = process_one_library_scan(session, _settings(library_scan_enabled=False))  # type: ignore[arg-type]

    assert did_work is False
    assert session.commits == 0


def _source(*, last_scan_at: datetime | None, enabled: bool = True, watch_enabled: bool = True) -> LibrarySource:
    return LibrarySource(
        id=uuid.uuid4(),
        name="Library",
        path="D:\\Research\\Papers",
        collection_id=uuid.uuid4(),
        enabled=enabled,
        watch_enabled=watch_enabled,
        recursive=True,
        last_scan_at=last_scan_at,
        status="active",
    )


def _settings(**overrides):
    defaults = {
        "library_scan_enabled": True,
        "library_scan_interval_seconds": 60,
        "library_scan_batch_size": 500,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)
