from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import VectorIndexState
from app.retrieval.vector_index import VECTOR_CURRENT_POINTER_FILENAME, vector_index_generation_root


def cleanup_vector_index_generations(session: Session, settings: Settings, *, apply: bool = False) -> dict[str, Any]:
    states = list(session.query(VectorIndexState).all())
    actions: list[dict[str, object]] = []
    for state in states:
        collection = state.collection
        if collection is None:
            continue
        root = vector_index_generation_root(settings.data_root, collection.name, state.embedding_model)
        if not root.exists():
            continue
        active_from_pointer = _read_current_generation(root)
        protected = {item for item in [active_from_pointer, state.active_generation_id] if item}
        generation_root = root / "generations"
        generations = sorted(
            [path for path in generation_root.iterdir() if path.is_dir()] if generation_root.exists() else [],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        kept_previous = 0
        for generation in generations:
            if generation.name in protected:
                continue
            if kept_previous < max(0, settings.vector_index_keep_generations - 1):
                kept_previous += 1
                continue
            actions.append(_cleanup_action(root, generation, "old_generation"))

        staging_root = root / "staging"
        cutoff = datetime.now(UTC) - timedelta(hours=settings.vector_staging_retention_hours)
        if staging_root.exists():
            for staging in sorted(path for path in staging_root.iterdir() if path.is_dir()):
                modified = datetime.fromtimestamp(staging.stat().st_mtime, tz=UTC)
                if modified < cutoff:
                    actions.append(_cleanup_action(root, staging, "old_staging"))

    if apply:
        for action in actions:
            path = Path(str(action["path"]))
            if path.exists():
                shutil.rmtree(path)
            action["applied"] = True
    return {"status": "applied" if apply else "dry_run", "actions": actions, "action_count": len(actions)}


def _read_current_generation(root: Path) -> str | None:
    current_path = root / VECTOR_CURRENT_POINTER_FILENAME
    if not current_path.exists():
        return None
    payload = json.loads(current_path.read_text(encoding="utf-8"))
    generation_id = payload.get("generation_id") if isinstance(payload, dict) else None
    return generation_id if isinstance(generation_id, str) else None


def _cleanup_action(root: Path, path: Path, reason: str) -> dict[str, object]:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_root != resolved_path and resolved_root not in resolved_path.parents:
        raise ValueError("vector cleanup candidate resolved outside index root")
    return {"reason": reason, "path": str(path), "applied": False}
