from __future__ import annotations

import os
import time
import uuid

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.queue import process_one_job
from app.retrieval.index_worker import process_one_vector_rebuild


def main() -> None:
    settings = get_settings()
    worker_id = settings.ingestion_worker_id.strip() or f"{os.uname().nodename if hasattr(os, 'uname') else 'worker'}-{uuid.uuid4()}"
    while True:
        did_work = False
        with SessionLocal() as session:
            if settings.worker_role in {"ingestion", "all"}:
                did_work = process_one_job(session, settings, worker_id) is not None
            if not did_work and settings.worker_role in {"vector", "all"}:
                did_work = process_one_vector_rebuild(session, settings, worker_id)
        if not did_work:
            time.sleep(settings.ingestion_poll_seconds)


if __name__ == "__main__":
    main()
