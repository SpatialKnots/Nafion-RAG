from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Collection, VectorIndexState

VECTOR_INDEX_READY = "ready"
VECTOR_INDEX_STALE = "stale"
VECTOR_INDEX_REBUILDING = "rebuilding"
VECTOR_INDEX_FAILED = "failed"
STORED_VECTOR_INDEX_STATUSES = {
    VECTOR_INDEX_READY,
    VECTOR_INDEX_STALE,
    VECTOR_INDEX_REBUILDING,
    VECTOR_INDEX_FAILED,
}


def vector_index_state_to_response(state: VectorIndexState) -> dict[str, object]:
    return {
        "id": str(state.id),
        "collection_id": str(state.collection_id),
        "collection": state.collection.name if state.collection is not None else None,
        "embedding_model": state.embedding_model,
        "status": state.status,
        "desired_revision": state.desired_revision,
        "active_revision": state.active_revision,
        "building_revision": state.building_revision,
        "active_generation_id": state.active_generation_id,
        "active_manifest_sha256": state.active_manifest_sha256,
        "requested_at": state.requested_at,
        "started_at": state.started_at,
        "finished_at": state.finished_at,
        "heartbeat_at": state.heartbeat_at,
        "attempt_count": state.attempt_count,
        "last_error_type": state.last_error_type,
        "last_error_message": _public_error_message(state.last_error_message),
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def list_vector_index_states(session: Session) -> list[VectorIndexState]:
    return list(
        session.scalars(
            select(VectorIndexState).join(Collection).order_by(Collection.name, VectorIndexState.embedding_model)
        )
    )


def get_vector_index_state_by_collection_name(
    session: Session,
    *,
    collection_name: str,
    embedding_model: str,
    create: bool = False,
) -> VectorIndexState | None:
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")
    state = session.scalar(
        select(VectorIndexState)
        .where(VectorIndexState.collection_id == collection.id)
        .where(VectorIndexState.embedding_model == _normalize_embedding_model(embedding_model))
    )
    if state is None and create:
        return get_or_create_vector_index_state(session, collection_id=collection.id, embedding_model=embedding_model)
    return state


def get_or_create_vector_index_state(
    session: Session,
    *,
    collection_id: UUID,
    embedding_model: str,
) -> VectorIndexState:
    normalized_model = _normalize_embedding_model(embedding_model)
    state = session.scalar(
        select(VectorIndexState)
        .where(VectorIndexState.collection_id == collection_id)
        .where(VectorIndexState.embedding_model == normalized_model)
    )
    if state is not None:
        return state

    now = datetime.now(UTC)
    state = VectorIndexState(
        collection_id=collection_id,
        embedding_model=normalized_model,
        status=VECTOR_INDEX_STALE,
        desired_revision=1,
        requested_at=now,
        updated_at=now,
    )
    session.add(state)
    session.flush()
    return state


def mark_vector_index_stale(
    session: Session,
    *,
    collection_id: UUID,
    embedding_model: str,
) -> VectorIndexState:
    state = get_or_create_vector_index_state(session, collection_id=collection_id, embedding_model=embedding_model)
    now = datetime.now(UTC)
    state.desired_revision += 1
    if state.status != VECTOR_INDEX_REBUILDING:
        state.status = VECTOR_INDEX_STALE
        state.building_revision = None
        state.worker_id = None
        state.heartbeat_at = None
    state.requested_at = now
    state.updated_at = now
    return state


def request_vector_rebuild(
    session: Session,
    *,
    collection_name: str,
    embedding_model: str,
) -> VectorIndexState:
    collection = session.scalar(select(Collection).where(Collection.name == collection_name))
    if collection is None:
        raise ValueError(f"Unknown collection: {collection_name}")
    return mark_vector_index_stale(session, collection_id=collection.id, embedding_model=embedding_model)


def claim_next_vector_rebuild(session: Session, settings: Settings, worker_id: str) -> VectorIndexState | None:
    if not settings.vector_auto_rebuild_enabled:
        return None
    recover_stale_vector_rebuilds(session, settings)
    ready_cutoff = datetime.now(UTC) - timedelta(seconds=settings.vector_rebuild_debounce_seconds)
    state = session.scalar(
        select(VectorIndexState)
        .where(VectorIndexState.status == VECTOR_INDEX_STALE)
        .where(VectorIndexState.requested_at <= ready_cutoff)
        .where(VectorIndexState.attempt_count < settings.vector_rebuild_max_attempts)
        .order_by(VectorIndexState.requested_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if state is None:
        return None

    now = datetime.now(UTC)
    state.status = VECTOR_INDEX_REBUILDING
    state.building_revision = state.desired_revision
    state.worker_id = worker_id
    state.attempt_count += 1
    state.started_at = now
    state.heartbeat_at = now
    state.updated_at = now
    state.last_error_type = None
    state.last_error_message = None
    return state


def heartbeat_vector_rebuild(state: VectorIndexState) -> None:
    now = datetime.now(UTC)
    state.heartbeat_at = now
    state.updated_at = now


def complete_vector_rebuild(
    state: VectorIndexState,
    *,
    generation_id: str,
    manifest_sha256: str,
) -> None:
    if state.status != VECTOR_INDEX_REBUILDING or state.building_revision is None:
        raise ValueError("vector index state is not rebuilding")
    now = datetime.now(UTC)
    if state.desired_revision != state.building_revision:
        state.status = VECTOR_INDEX_STALE
        state.building_revision = None
        state.requested_at = now
        state.worker_id = None
        state.heartbeat_at = None
        state.updated_at = now
        return

    state.status = VECTOR_INDEX_READY
    state.active_revision = state.building_revision
    state.building_revision = None
    state.active_generation_id = _require_non_empty(generation_id, "generation_id")
    state.active_manifest_sha256 = _require_non_empty(manifest_sha256, "manifest_sha256")
    state.worker_id = None
    state.heartbeat_at = None
    state.finished_at = now
    state.updated_at = now
    state.last_error_type = None
    state.last_error_message = None


def fail_vector_rebuild(state: VectorIndexState, error_type: str, error_message: str) -> None:
    now = datetime.now(UTC)
    state.status = VECTOR_INDEX_FAILED if state.active_revision is None else VECTOR_INDEX_READY
    state.building_revision = None
    state.worker_id = None
    state.heartbeat_at = None
    state.finished_at = now
    state.updated_at = now
    state.last_error_type = _require_non_empty(error_type, "error_type")
    state.last_error_message = error_message[:1000]


def recover_stale_vector_rebuilds(session: Session, settings: Settings) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.vector_rebuild_lease_seconds)
    states = list(
        session.scalars(
            select(VectorIndexState)
            .where(VectorIndexState.status == VECTOR_INDEX_REBUILDING)
            .where(VectorIndexState.heartbeat_at < cutoff)
            .order_by(VectorIndexState.requested_at)
        )
    )
    now = datetime.now(UTC)
    recovered = 0
    for state in states:
        if state.attempt_count >= settings.vector_rebuild_max_attempts and state.active_revision is None:
            state.status = VECTOR_INDEX_FAILED
            state.last_error_type = "LeaseExpired"
            state.last_error_message = "Vector rebuild lease expired and max attempts were exhausted"
            state.finished_at = now
        else:
            state.status = VECTOR_INDEX_STALE
            state.requested_at = now
        state.building_revision = None
        state.worker_id = None
        state.heartbeat_at = None
        state.updated_at = now
        recovered += 1
    return recovered


def _normalize_embedding_model(embedding_model: str) -> str:
    normalized = embedding_model.strip()
    if not normalized:
        raise ValueError("embedding_model must not be empty")
    return normalized


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _public_error_message(message: str | None) -> str | None:
    if message is None:
        return None
    lowered = message.lower()
    if "\\" in message or "/" in message or "traceback" in lowered:
        return "Vector index rebuild failed. See local logs for details."
    return message[:300]
