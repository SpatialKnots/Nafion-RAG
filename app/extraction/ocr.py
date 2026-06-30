from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_OCR_TOOL_DIRS = [
    Path(r"C:\Program Files\Tesseract-OCR"),
    Path(r"C:\Program Files\gs\gs10.07.1\bin"),
]


def _tail(text: str, max_chars: int = 2000) -> str:
    return text[-max_chars:] if len(text) > max_chars else text


def _resolve_command(command: str) -> str | None:
    resolved = shutil.which(command)
    if resolved is not None:
        return resolved

    local_scripts_command = Path(sys.executable).parent / command
    if local_scripts_command.is_file():
        return str(local_scripts_command)

    local_scripts_exe = Path(sys.executable).parent / f"{command}.exe"
    if local_scripts_exe.is_file():
        return str(local_scripts_exe)

    return None


def _ocr_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_path = env.get("PATH", "")
    existing_parts = [part for part in existing_path.split(os.pathsep) if part]
    prepend_parts = [str(path) for path in _OCR_TOOL_DIRS if path.is_dir() and str(path) not in existing_parts]
    if prepend_parts:
        env["PATH"] = os.pathsep.join([*prepend_parts, existing_path])
    return env


def run_ocrmypdf(
    input_pdf: Path,
    output_pdf: Path,
    *,
    languages: str,
    command: str,
    timeout_seconds: int,
) -> Path:
    resolved_command = _resolve_command(command)
    if resolved_command is None:
        raise RuntimeError(f"OCR command not found: {command}")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [resolved_command, "--skip-text", "--language", languages, str(input_pdf), str(output_pdf)],
            check=False,
            capture_output=True,
            env=_ocr_env(),
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"OCR timed out after {timeout_seconds} seconds for {input_pdf}") from exc
    if completed.returncode != 0:
        stderr = _tail(completed.stderr.strip())
        stdout = _tail(completed.stdout.strip())
        detail = stderr or stdout or f"exit code {completed.returncode}"
        raise RuntimeError(f"OCR failed for {input_pdf}: {detail}")
    if not output_pdf.exists():
        raise RuntimeError(f"OCR did not create expected output: {output_pdf}")
    return output_pdf
