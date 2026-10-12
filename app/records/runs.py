"""Local manifest of a validated development artifact and current implementation."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from app.records.schema import CandidateBundle, text_hash
from app.records.sources import file_hash


def build_manifest(
    artifact: Path,
    *,
    operation: Literal["context_export", "manual_candidate", "integrity_validation"],
    source_root: Path,
) -> dict[str, object]:
    # Validate precisely the same bytes whose hash goes into the manifest.
    raw = artifact.read_bytes()
    bundle = CandidateBundle.model_validate_json(raw)
    source_root = source_root.resolve()
    if not (source_root / "app" / "records" / "schema.py").is_file():
        raise ValueError("source_root must contain the ARIADNE record implementation")
    code_paths = sorted((source_root / "app").rglob("*.py")) + [source_root / "pyproject.toml"]
    code_files = [{"path": path.relative_to(source_root).as_posix(), "sha256": file_hash(path)} for path in code_paths]
    schema = json.dumps(CandidateBundle.model_json_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "manifest_version": "records_development_manifest_v0.1",
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": str(bundle.run_id),
        "operation": operation,
        "producer": bundle.producer,
        "artifact": {"path": str(artifact.resolve()), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
        "schema_version": bundle.schema_version,
        "schema_sha256": text_hash(schema),
        "code_fingerprint_sha256": text_hash(json.dumps(code_files, sort_keys=True, separators=(",", ":"))),
        "code_files": code_files,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {name: version(name) for name in ("pydantic", "sqlalchemy", "psycopg", "pydantic-settings")},
        },
        "source_region_ids": [region.region_id for region in bundle.regions],
        "records": len(bundle.records),
        "limitations": [
            "Current source fingerprints do not identify an earlier extraction run.",
            "Manifest captures code and selected package versions, not a complete dependency lock or offline runtime.",
            "Artifact integrity validation does not establish scientific correctness or gold status.",
            "PDFs and database are referenced, not bundled; use live validation to check current sources.",
        ],
    }
