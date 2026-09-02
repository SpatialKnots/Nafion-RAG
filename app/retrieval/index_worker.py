from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Collection
from app.library.service import reconcile_library_source_vector_readiness
from app.retrieval.index_lifecycle import claim_next_vector_rebuild, complete_vector_rebuild, fail_vector_rebuild
from app.retrieval.vector_index import build_local_vector_index_generation

LOGGER = logging.getLogger(__name__)


def process_one_vector_rebuild(session: Session, settings: Settings, worker_id: str) -> bool:
    state = claim_next_vector_rebuild(session, settings, worker_id)
    if state is None:
        session.commit()
        return False
    target_revision = state.building_revision
    state_id = state.id
    collection_id = state.collection_id
    embedding_model = state.embedding_model
    session.commit()

    if target_revision is None:
        state = session.get(type(state), state_id)
        if state is not None:
            fail_vector_rebuild(state, "InvalidState", "Claimed vector rebuild did not capture a target revision")
        session.commit()
        return True

    state = session.get(type(state), state_id)
    collection = session.get(Collection, collection_id)
    if state is None or collection is None:
        session.commit()
        return True

    try:
        generation = build_local_vector_index_generation(
            session,
            data_root=settings.data_root,
            collection=collection.name,
            embedding_model=embedding_model,
            target_revision=target_revision,
            batch_size=settings.vector_rebuild_batch_size,
            build_command="vector worker rebuild",
        )
        complete_vector_rebuild(
            state,
            generation_id=generation.generation_id,
            manifest_sha256=generation.manifest_sha256,
        )
        reconcile_library_source_vector_readiness(session, settings)
    except Exception as exc:
        LOGGER.exception("vector index rebuild failed", extra={"state_id": str(state_id)})
        fail_vector_rebuild(state, type(exc).__name__, str(exc))
    session.commit()
    return True
