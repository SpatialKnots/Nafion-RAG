from __future__ import annotations

from types import SimpleNamespace

from app.workers.worker import process_worker_session


def test_all_worker_role_processes_ingestion_before_vector_or_library(monkeypatch) -> None:
    calls: list[str] = []

    def fake_ingestion(session: object, settings: object, worker_id: str) -> object:
        calls.append("ingestion")
        return object()

    def fake_vector(session: object, settings: object, worker_id: str) -> bool:
        calls.append("vector")
        return True

    def fake_library(session: object, settings: object) -> bool:
        calls.append("library")
        return True

    monkeypatch.setattr("app.workers.worker.process_one_job", fake_ingestion)
    monkeypatch.setattr("app.workers.worker.process_one_vector_rebuild", fake_vector)
    monkeypatch.setattr("app.workers.worker.process_one_library_scan", fake_library)

    did_work = process_worker_session(object(), _settings("all"), "worker-1")  # type: ignore[arg-type]

    assert did_work is True
    assert calls == ["ingestion"]


def test_all_worker_role_processes_vector_after_ingestion_queue_is_empty(monkeypatch) -> None:
    calls: list[str] = []

    def fake_ingestion(session: object, settings: object, worker_id: str) -> object | None:
        calls.append("ingestion")
        return None

    def fake_vector(session: object, settings: object, worker_id: str) -> bool:
        calls.append("vector")
        return True

    def fake_library(session: object, settings: object) -> bool:
        calls.append("library")
        return True

    monkeypatch.setattr("app.workers.worker.process_one_job", fake_ingestion)
    monkeypatch.setattr("app.workers.worker.process_one_vector_rebuild", fake_vector)
    monkeypatch.setattr("app.workers.worker.process_one_library_scan", fake_library)

    did_work = process_worker_session(object(), _settings("all"), "worker-1")  # type: ignore[arg-type]

    assert did_work is True
    assert calls == ["ingestion", "vector"]


def test_all_worker_role_processes_library_scan_after_ingestion_and_vector_are_idle(monkeypatch) -> None:
    calls: list[str] = []

    def fake_ingestion(session: object, settings: object, worker_id: str) -> object | None:
        calls.append("ingestion")
        return None

    def fake_vector(session: object, settings: object, worker_id: str) -> bool:
        calls.append("vector")
        return False

    def fake_library(session: object, settings: object) -> bool:
        calls.append("library")
        return True

    monkeypatch.setattr("app.workers.worker.process_one_job", fake_ingestion)
    monkeypatch.setattr("app.workers.worker.process_one_vector_rebuild", fake_vector)
    monkeypatch.setattr("app.workers.worker.process_one_library_scan", fake_library)

    did_work = process_worker_session(object(), _settings("all"), "worker-1")  # type: ignore[arg-type]

    assert did_work is True
    assert calls == ["ingestion", "vector", "library"]


def _settings(worker_role: str):
    return SimpleNamespace(worker_role=worker_role)
