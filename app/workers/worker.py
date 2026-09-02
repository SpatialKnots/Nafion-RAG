from __future__ import annotations

import os
import time
import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.ingestion.queue import process_one_job
from app.library.worker import process_one_library_scan
from app.retrieval.index_worker import process_one_vector_rebuild


def process_worker_session(session: Session, settings: Settings, worker_id: str) -> bool:
    did_work = False
    if settings.worker_role in {"ingestion", "all"}:
        did_work = process_one_job(session, settings, worker_id) is not None
    if not did_work and settings.worker_role in {"vector", "all"}:
        did_work = process_one_vector_rebuild(session, settings, worker_id)
    if not did_work and settings.worker_role in {"library", "all"}:
        did_work = process_one_library_scan(session, settings)
    return did_work


def main() -> None:
    settings = get_settings()
    worker_id = settings.ingestion_worker_id.strip() or f"{os.uname().nodename if hasattr(os, 'uname') else 'worker'}-{uuid.uuid4()}"
    while True:
        with SessionLocal() as session:
            did_work = process_worker_session(session, settings, worker_id)
        if not did_work:
            time.sleep(settings.ingestion_poll_seconds)


if __name__ == "__main__":
    main()
