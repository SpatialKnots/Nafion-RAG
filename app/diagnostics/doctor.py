from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, VectorIndexState
from app.extraction.ocr import _OCR_TOOL_DIRS, _ocr_env, _resolve_command

StatusPayload = dict[str, Any]


def _payload(status: str, message: str, **details: object) -> StatusPayload:
    return {"status": status, "message": message, **details}


def _check_database(session_factory: Callable[[], Session]) -> StatusPayload:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        return _payload("FAIL", "database connection failed", error_type=type(exc).__name__, error=str(exc))
    return _payload("PASS", "database connection succeeded")


def _current_alembic_head() -> str | None:
    config_path = Path("alembic.ini")
    if not config_path.exists():
        return None
    config = Config(str(config_path))
    return ScriptDirectory.from_config(config).get_current_head()


def _check_migrations(session_factory: Callable[[], Session]) -> StatusPayload:
    expected_head = _current_alembic_head()
    if expected_head is None:
        return _payload("WARN", "alembic.ini not found")
    try:
        with session_factory() as session:
            current = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except Exception as exc:
        return _payload(
            "FAIL",
            "could not read alembic_version",
            expected_head=expected_head,
            error_type=type(exc).__name__,
            error=str(exc),
        )
    if current == expected_head:
        return _payload("PASS", "database is at current migration head", current=current, expected_head=expected_head)
    return _payload("FAIL", "database migration head mismatch", current=current, expected_head=expected_head)


def _check_data_root(settings: Settings) -> StatusPayload:
    try:
        settings.data_root.mkdir(parents=True, exist_ok=True)
        probe = settings.data_root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        return _payload("FAIL", "data root is not writable", path=str(settings.data_root), error_type=type(exc).__name__, error=str(exc))
    return _payload("PASS", "data root is writable", path=str(settings.data_root))


def _check_ocr_command(settings: Settings) -> StatusPayload:
    resolved = _resolve_command(settings.ocr_command)
    if resolved is None:
        return _payload("FAIL", "OCR command not found", command=settings.ocr_command)
    return _payload("PASS", "OCR command resolved", command=settings.ocr_command, resolved=resolved)


def _resolve_tool(candidates: list[str]) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    for tool_dir in _OCR_TOOL_DIRS:
        for candidate in candidates:
            path = tool_dir / candidate
            if path.is_file():
                return str(path)
            exe_path = tool_dir / f"{candidate}.exe"
            if exe_path.is_file():
                return str(exe_path)
    return None


def _check_tesseract_languages(required_languages: set[str]) -> StatusPayload:
    resolved = _resolve_tool(["tesseract"])
    if resolved is None:
        return _payload("FAIL", "tesseract command not found", required_languages=sorted(required_languages))
    ocr_env = _ocr_env()
    tessdata_prefix = ocr_env.get("TESSDATA_PREFIX")
    if tessdata_prefix is not None and not (Path(tessdata_prefix) / "configs" / "hocr").is_file():
        return _payload(
            "FAIL",
            "tesseract hocr config is missing from TESSDATA_PREFIX",
            command=resolved,
            tessdata_prefix=tessdata_prefix,
            missing=str(Path(tessdata_prefix) / "configs" / "hocr"),
            required_languages=sorted(required_languages),
        )
    try:
        completed = subprocess.run(
            [resolved, "--list-langs"],
            check=False,
            capture_output=True,
            env=ocr_env,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        return _payload(
            "FAIL",
            "could not list tesseract languages",
            command=resolved,
            tessdata_prefix=tessdata_prefix,
            error_type=type(exc).__name__,
            error=str(exc),
            required_languages=sorted(required_languages),
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return _payload("FAIL", "tesseract language listing failed", command=resolved, tessdata_prefix=tessdata_prefix, error=detail)
    installed = {
        line.strip() for line in completed.stdout.splitlines() if line.strip() and not line.lower().startswith("list of available")
    }
    missing = sorted(required_languages - installed)
    if missing:
        return _payload(
            "FAIL",
            "required tesseract languages are missing",
            command=resolved,
            tessdata_prefix=tessdata_prefix,
            installed=sorted(installed),
            missing=missing,
        )
    return _payload(
        "PASS",
        "required tesseract languages are installed",
        command=resolved,
        tessdata_prefix=tessdata_prefix,
        installed=sorted(installed),
    )


def _check_ghostscript() -> StatusPayload:
    resolved = _resolve_tool(["gswin64c", "gswin32c", "gs"])
    if resolved is None:
        return _payload("FAIL", "ghostscript command not found", candidates=["gswin64c", "gswin32c", "gs"])
    return _payload("PASS", "ghostscript command resolved", resolved=resolved)


def _check_corpus_files(session_factory: Callable[[], Session]) -> StatusPayload:
    try:
        with session_factory() as session:
            articles = list(session.scalars(select(Article).order_by(Article.title)))
    except Exception as exc:
        return _payload("FAIL", "could not inspect indexed corpus files", error_type=type(exc).__name__, error=str(exc))

    missing_original: list[dict[str, str]] = []
    missing_ocr: list[dict[str, str]] = []
    for article in articles:
        original_path = Path(article.pdf_original_path)
        if not original_path.exists():
            missing_original.append({"article_id": str(article.id), "path": article.pdf_original_path})
        if article.pdf_ocr_path:
            ocr_path = Path(article.pdf_ocr_path)
            if not ocr_path.exists():
                missing_ocr.append({"article_id": str(article.id), "path": article.pdf_ocr_path})

    if missing_original or missing_ocr:
        return _payload(
            "WARN",
            "indexed corpus has missing stored PDF files",
            article_count=len(articles),
            missing_original_count=len(missing_original),
            missing_ocr_count=len(missing_ocr),
            missing_original_examples=missing_original[:5],
            missing_ocr_examples=missing_ocr[:5],
        )
    return _payload("PASS", "indexed corpus files are present", article_count=len(articles))


def _check_upload_storage(settings: Settings) -> StatusPayload:
    upload_root = settings.data_root / "uploads"
    incoming = upload_root / "incoming"
    queued = upload_root / "queued"
    try:
        incoming.mkdir(parents=True, exist_ok=True)
        queued.mkdir(parents=True, exist_ok=True)
        probe = incoming / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        return _payload("FAIL", "upload storage is not writable", path=str(upload_root), error_type=type(exc).__name__, error=str(exc))
    return _payload("PASS", "upload storage is writable", incoming=str(incoming), queued=str(queued))


def _check_ingestion_settings(settings: Settings) -> StatusPayload:
    return _payload(
        "PASS",
        "ingestion queue settings are valid",
        upload_max_file_size_mb=settings.upload_max_file_size_mb,
        upload_max_files_per_request=settings.upload_max_files_per_request,
        ingestion_lease_seconds=settings.ingestion_lease_seconds,
        ingestion_heartbeat_seconds=settings.ingestion_heartbeat_seconds,
        ingestion_max_attempts=settings.ingestion_max_attempts,
    )


def _check_text_quality_settings(settings: Settings) -> StatusPayload:
    return _payload(
        "PASS",
        "text quality audit settings are valid",
        short_page_chars=settings.text_quality_short_page_chars,
        control_char_ratio=settings.text_quality_control_char_ratio,
        ocr_reprocess_allow_existing=settings.ocr_reprocess_allow_existing,
    )


def _check_vector_index_lifecycle(settings: Settings, session_factory: Callable[[], Session]) -> StatusPayload:
    try:
        with session_factory() as session:
            states = list(session.scalars(select(VectorIndexState).order_by(VectorIndexState.embedding_model)))
    except Exception as exc:
        return _payload("FAIL", "could not inspect vector index lifecycle state", error_type=type(exc).__name__, error=str(exc))
    if not states:
        return _payload("WARN", "no vector index lifecycle state rows exist")

    ready = 0
    stale = 0
    failed = 0
    incomplete_ready: list[str] = []
    for state in states:
        if state.status == "ready":
            ready += 1
            if state.active_revision != state.desired_revision or not state.active_generation_id or not state.active_manifest_sha256:
                incomplete_ready.append(str(state.id))
        elif state.status == "stale":
            stale += 1
        elif state.status == "failed":
            failed += 1
    if incomplete_ready:
        return _payload(
            "FAIL",
            "ready vector index state is incomplete or stale",
            state_count=len(states),
            incomplete_ready_state_ids=incomplete_ready[:10],
        )
    status = "PASS" if ready else "WARN"
    return _payload(
        status,
        "vector index lifecycle state inspected",
        state_count=len(states),
        ready=ready,
        stale=stale,
        failed=failed,
        auto_rebuild_enabled=settings.vector_auto_rebuild_enabled,
    )


def run_doctor(settings: Settings, session_factory: Callable[[], Session]) -> dict[str, StatusPayload]:
    required_languages = {part for part in settings.ocr_languages.split("+") if part}
    return {
        "database": _check_database(session_factory),
        "migrations": _check_migrations(session_factory),
        "data_root": _check_data_root(settings),
        "upload_storage": _check_upload_storage(settings),
        "ingestion_settings": _check_ingestion_settings(settings),
        "text_quality_settings": _check_text_quality_settings(settings),
        "vector_index_lifecycle": _check_vector_index_lifecycle(settings, session_factory),
        "corpus_files": _check_corpus_files(session_factory),
        "ocr_command": _check_ocr_command(settings),
        "tesseract_languages": _check_tesseract_languages(required_languages),
        "ghostscript": _check_ghostscript(),
    }
