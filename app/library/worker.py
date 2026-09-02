from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.library.service import list_library_sources, scan_and_queue_library_source


def process_one_library_scan(session: Session, settings: Settings) -> bool:
    if not settings.library_scan_enabled:
        return False

    cutoff = datetime.now(UTC) - timedelta(seconds=settings.library_scan_interval_seconds)
    for source in list_library_sources(session):
        if not source.enabled or not source.watch_enabled:
            continue
        if source.last_scan_at is not None and source.last_scan_at > cutoff:
            continue
        scan_and_queue_library_source(
            session,
            settings,
            source.id,
            queue_limit=settings.library_scan_batch_size,
        )
        session.commit()
        return True
    return False
