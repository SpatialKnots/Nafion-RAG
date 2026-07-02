from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

_OCR_TOOL_DIRS = [
    Path(r"C:\Program Files\Tesseract-OCR"),
    Path(r"C:\Program Files\gs\gs10.07.1\bin"),
]
_LOCAL_TESSDATA_DIR = Path("data") / "tessdata"


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


def _windows_short_path(path: Path) -> str:
    path_string = str(path)
    if os.name != "nt":
        return path_string
    try:
        get_short_path_name = ctypes.windll.kernel32.GetShortPathNameW
        required_length = get_short_path_name(path_string, None, 0)
        if required_length > 0:
            buffer = ctypes.create_unicode_buffer(required_length)
            if get_short_path_name(path_string, buffer, required_length) != 0 and buffer.value and buffer.value != path_string:
                return buffer.value
    except (AttributeError, OSError, ValueError):
        pass
    candidates = [path_string]
    try:
        relative_path = path.relative_to(Path.cwd().resolve())
        candidates.insert(0, str(relative_path))
    except ValueError:
        pass
    for candidate in candidates:
        try:
            completed = subprocess.run(
                ["cmd.exe", "/c", f"for %I in ({candidate}) do @echo %~sI"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        short_path = completed.stdout.strip()
        if completed.returncode == 0 and short_path:
            return short_path
    return path_string


def _ocr_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_path = env.get("PATH", "")
    existing_parts = [part for part in existing_path.split(os.pathsep) if part]
    prepend_parts = [str(path) for path in _OCR_TOOL_DIRS if path.is_dir() and str(path) not in existing_parts]
    if prepend_parts:
        env["PATH"] = os.pathsep.join([*prepend_parts, existing_path])
    local_tessdata = _LOCAL_TESSDATA_DIR.resolve()
    if local_tessdata.is_dir():
        env["TESSDATA_PREFIX"] = _windows_short_path(local_tessdata)
    return env


def run_ocrmypdf(
    input_pdf: Path,
    output_pdf: Path,
    *,
    languages: str,
    command: str,
    timeout_seconds: int,
    force: bool = False,
) -> Path:
    resolved_command = _resolve_command(command)
    if resolved_command is None:
        raise RuntimeError(f"OCR command not found: {command}")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    if output_pdf.exists():
        output_pdf.unlink()
    ocr_mode = "--force-ocr" if force else "--skip-text"
    try:
        completed = subprocess.run(
            [resolved_command, ocr_mode, "--language", languages, str(input_pdf), str(output_pdf)],
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
