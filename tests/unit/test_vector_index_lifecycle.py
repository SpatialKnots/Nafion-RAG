from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.db.models import VectorIndexState
from app.retrieval.index_lifecycle import (
    VECTOR_INDEX_FAILED,
    VECTOR_INDEX_READY,
    VECTOR_INDEX_REBUILDING,
    VECTOR_INDEX_STALE,
    claim_next_vector_rebuild,
    complete_vector_rebuild,
    fail_vector_rebuild,
    get_or_create_vector_index_state,
    mark_vector_index_stale,
    recover_stale_vector_rebuilds,
)


class FakeScalarResult:
    def __init__(self, rows: list[VectorIndexState]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self, state: VectorIndexState | None = None) -> None:
        self.state = state
        self.added: list[VectorIndexState] = []

    def scalar(self, statement: object) -> VectorIndexState | None:
        if self.state is None:
            return None
        now = datetime.now(UTC)
        if self.state.status == VECTOR_INDEX_STALE and self.state.requested_at and self.state.requested_at <= now:
            return self.state
        return self.state

    def scalars(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult([self.state] if self.state is not None else [])

    def add(self, value: VectorIndexState) -> None:
        self.added.append(value)
        self.state = value

    def flush(self) -> None:
        return None


def test_get_or_create_vector_index_state_creates_stale_state() -> None:
    collection_id = uuid.uuid4()
    session = FakeSession()

    state = get_or_create_vector_index_state(
        session,  # type: ignore[arg-type]
        collection_id=collection_id,
        embedding_model=" test/model ",
    )

    assert state in session.added
    assert state.collection_id == collection_id
    assert state.embedding_model == "test/model"
    assert state.status == VECTOR_INDEX_STALE
    assert state.desired_revision == 1
    assert state.requested_at is not None


def test_mark_vector_index_stale_increments_desired_revision() -> None:
    state = _state(status=VECTOR_INDEX_READY, desired_revision=4, active_revision=4)

    updated = mark_vector_index_stale(
        FakeSession(state),  # type: ignore[arg-type]
        collection_id=state.collection_id,
        embedding_model=state.embedding_model,
    )

    assert updated is state
    assert state.status == VECTOR_INDEX_STALE
    assert state.desired_revision == 5
    assert state.building_revision is None


def test_repeated_stale_marks_coalesce_into_one_state_for_bulk_ingestion() -> None:
    state = _state(status=VECTOR_INDEX_READY, desired_revision=4, active_revision=4)
    session = FakeSession(state)

    for _index in range(5):
        updated = mark_vector_index_stale(
            session,  # type: ignore[arg-type]
            collection_id=state.collection_id,
            embedding_model=state.embedding_model,
        )

    assert updated is state
    assert session.added == []
    assert state.status == VECTOR_INDEX_STALE
    assert state.desired_revision == 9
    assert state.building_revision is None


def test_mark_vector_index_stale_preserves_rebuilding_claim() -> None:
    state = _state(status=VECTOR_INDEX_REBUILDING, desired_revision=4, building_revision=4)
    state.worker_id = "worker-1"

    mark_vector_index_stale(
        FakeSession(state),  # type: ignore[arg-type]
        collection_id=state.collection_id,
        embedding_model=state.embedding_model,
    )

    assert state.status == VECTOR_INDEX_REBUILDING
    assert state.desired_revision == 5
    assert state.building_revision == 4
    assert state.worker_id == "worker-1"


def test_claim_next_vector_rebuild_obeys_debounce_and_captures_revision() -> None:
    state = _state(status=VECTOR_INDEX_STALE, desired_revision=8)
    state.requested_at = datetime.now(UTC) - timedelta(seconds=20)
    settings = _settings(vector_rebuild_debounce_seconds=10)

    claimed = claim_next_vector_rebuild(FakeSession(state), settings, "worker-1")  # type: ignore[arg-type]

    assert claimed is state
    assert state.status == VECTOR_INDEX_REBUILDING
    assert state.building_revision == 8
    assert state.worker_id == "worker-1"
    assert state.attempt_count == 1
    assert state.heartbeat_at is not None


def test_complete_vector_rebuild_returns_to_stale_when_revision_changed() -> None:
    state = _state(status=VECTOR_INDEX_REBUILDING, desired_revision=9, building_revision=8)

    complete_vector_rebuild(state, generation_id="generation-1", manifest_sha256="abc")

    assert state.status == VECTOR_INDEX_STALE
    assert state.active_generation_id is None
    assert state.building_revision is None


def test_complete_vector_rebuild_marks_ready_for_matching_revision() -> None:
    state = _state(status=VECTOR_INDEX_REBUILDING, desired_revision=8, building_revision=8)

    complete_vector_rebuild(state, generation_id="generation-1", manifest_sha256="abc")

    assert state.status == VECTOR_INDEX_READY
    assert state.active_revision == 8
    assert state.building_revision is None
    assert state.active_generation_id == "generation-1"
    assert state.active_manifest_sha256 == "abc"
    assert state.worker_id is None


def test_fail_vector_rebuild_without_active_generation_marks_failed() -> None:
    state = _state(status=VECTOR_INDEX_REBUILDING, desired_revision=2, building_revision=2)

    fail_vector_rebuild(state, "RuntimeError", "model unavailable")

    assert state.status == VECTOR_INDEX_FAILED
    assert state.last_error_type == "RuntimeError"
    assert state.last_error_message == "model unavailable"
    assert state.building_revision is None


def test_recover_stale_vector_rebuilds_requeues_before_max_attempts() -> None:
    state = _state(status=VECTOR_INDEX_REBUILDING, desired_revision=2, building_revision=2, attempt_count=1)
    state.heartbeat_at = datetime.now(UTC) - timedelta(seconds=2000)

    recovered = recover_stale_vector_rebuilds(
        FakeSession(state),  # type: ignore[arg-type]
        _settings(vector_rebuild_lease_seconds=1000, vector_rebuild_max_attempts=3),
    )

    assert recovered == 1
    assert state.status == VECTOR_INDEX_STALE
    assert state.worker_id is None
    assert state.building_revision is None


def _state(
    *,
    status: str,
    desired_revision: int = 1,
    active_revision: int | None = None,
    building_revision: int | None = None,
    attempt_count: int = 0,
) -> VectorIndexState:
    now = datetime.now(UTC)
    return VectorIndexState(
        collection_id=uuid.uuid4(),
        embedding_model="test/model",
        status=status,
        desired_revision=desired_revision,
        active_revision=active_revision,
        building_revision=building_revision,
        requested_at=now,
        attempt_count=attempt_count,
        updated_at=now,
    )


def _settings(**overrides):
    defaults = {
        "vector_auto_rebuild_enabled": True,
        "vector_rebuild_debounce_seconds": 0,
        "vector_rebuild_lease_seconds": 1800,
        "vector_rebuild_max_attempts": 3,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)
