from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
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
    try:
        completed = subprocess.run(
            [resolved, "--list-langs"],
            check=False,
            capture_output=True,
            env=_ocr_env(),
            text=True,
            timeout=30,
        )
    except Exception as exc:
        return _payload(
            "FAIL",
            "could not list tesseract languages",
            command=resolved,
            error_type=type(exc).__name__,
            error=str(exc),
            required_languages=sorted(required_languages),
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return _payload("FAIL", "tesseract language listing failed", command=resolved, error=detail)
    installed = {
        line.strip() for line in completed.stdout.splitlines() if line.strip() and not line.lower().startswith("list of available")
    }
    missing = sorted(required_languages - installed)
    if missing:
        return _payload("FAIL", "required tesseract languages are missing", command=resolved, installed=sorted(installed), missing=missing)
    return _payload("PASS", "required tesseract languages are installed", command=resolved, installed=sorted(installed))


def _check_ghostscript() -> StatusPayload:
    resolved = _resolve_tool(["gswin64c", "gswin32c", "gs"])
    if resolved is None:
        return _payload("FAIL", "ghostscript command not found", candidates=["gswin64c", "gswin32c", "gs"])
    return _payload("PASS", "ghostscript command resolved", resolved=resolved)


def run_doctor(settings: Settings, session_factory: Callable[[], Session]) -> dict[str, StatusPayload]:
    required_languages = {part for part in settings.ocr_languages.split("+") if part}
    return {
        "database": _check_database(session_factory),
        "migrations": _check_migrations(session_factory),
        "data_root": _check_data_root(settings),
        "ocr_command": _check_ocr_command(settings),
        "tesseract_languages": _check_tesseract_languages(required_languages),
        "ghostscript": _check_ghostscript(),
    }
