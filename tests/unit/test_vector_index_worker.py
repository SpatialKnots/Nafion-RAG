from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.db.models import Collection, VectorIndexState
from app.retrieval.index_worker import process_one_vector_rebuild


class FakeScalarResult:
    def __init__(self, rows: list[VectorIndexState]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self, state: VectorIndexState, collection: Collection) -> None:
        self.state = state
        self.collection = collection
        self.commits = 0

    def scalar(self, statement: object) -> VectorIndexState | None:
        if self.state.status == "stale":
            return self.state
        return None

    def scalars(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult([])

    def get(self, model: object, item_id: object) -> object | None:
        if model is VectorIndexState and item_id == self.state.id:
            return self.state
        if model is Collection and item_id == self.collection.id:
            return self.collection
        return None

    def commit(self) -> None:
        self.commits += 1


def test_process_one_vector_rebuild_builds_generation_and_marks_ready(monkeypatch, tmp_path) -> None:
    collection = Collection(id=uuid.uuid4(), name="literature")
    state = VectorIndexState(
        id=uuid.uuid4(),
        collection_id=collection.id,
        embedding_model="test/model",
        status="stale",
        desired_revision=3,
        requested_at=datetime.now(UTC) - timedelta(seconds=30),
        attempt_count=0,
    )
    session = FakeSession(state, collection)

    def fake_build(**kwargs: object) -> object:
        assert kwargs["collection"] == "literature"
        assert kwargs["embedding_model"] == "test/model"
        assert kwargs["target_revision"] == 3
        return SimpleNamespace(generation_id="generation-1", manifest_sha256="abc")

    monkeypatch.setattr("app.retrieval.index_worker.build_local_vector_index_generation", lambda *args, **kwargs: fake_build(**kwargs))

    did_work = process_one_vector_rebuild(session, _settings(tmp_path), "worker-1")  # type: ignore[arg-type]

    assert did_work is True
    assert state.status == "ready"
    assert state.active_revision == 3
    assert state.active_generation_id == "generation-1"
    assert state.active_manifest_sha256 == "abc"
    assert session.commits == 2


def test_process_one_vector_rebuild_marks_failed_on_build_error(monkeypatch, tmp_path) -> None:
    collection = Collection(id=uuid.uuid4(), name="literature")
    state = VectorIndexState(
        id=uuid.uuid4(),
        collection_id=collection.id,
        embedding_model="test/model",
        status="stale",
        desired_revision=3,
        requested_at=datetime.now(UTC) - timedelta(seconds=30),
        attempt_count=0,
    )
    session = FakeSession(state, collection)

    def fail_build(*args: object, **kwargs: object) -> object:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("app.retrieval.index_worker.build_local_vector_index_generation", fail_build)

    did_work = process_one_vector_rebuild(session, _settings(tmp_path), "worker-1")  # type: ignore[arg-type]

    assert did_work is True
    assert state.status == "failed"
    assert state.last_error_type == "RuntimeError"
    assert state.last_error_message == "model unavailable"


def _settings(tmp_path):
    return SimpleNamespace(
        data_root=tmp_path,
        vector_auto_rebuild_enabled=True,
        vector_rebuild_debounce_seconds=0,
        vector_rebuild_lease_seconds=1800,
        vector_rebuild_max_attempts=3,
        vector_rebuild_batch_size=64,
    )
