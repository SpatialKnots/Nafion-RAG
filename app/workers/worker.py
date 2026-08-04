from __future__ import annotations

import os
import time
import uuid

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.queue import process_one_job


def main() -> None:
    settings = get_settings()
    worker_id = settings.ingestion_worker_id.strip() or f"{os.uname().nodename if hasattr(os, 'uname') else 'worker'}-{uuid.uuid4()}"
    while True:
        with SessionLocal() as session:
            job = process_one_job(session, settings, worker_id)
        if job is None:
            time.sleep(settings.ingestion_poll_seconds)


if __name__ == "__main__":
    main()
