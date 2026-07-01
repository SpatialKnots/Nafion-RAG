from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.extraction import ocr


def test_run_ocrmypdf_rejects_missing_command(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda command: None)

    with pytest.raises(RuntimeError, match="OCR command not found"):
        ocr.run_ocrmypdf(tmp_path / "in.pdf", tmp_path / "out.pdf", languages="eng", command="missing", timeout_seconds=1)


def test_run_ocrmypdf_reports_nonzero_exit(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda command: "ocrmypdf")

    def fake_run(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=2, stdout="", stderr="bad scan")

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="bad scan"):
        ocr.run_ocrmypdf(tmp_path / "in.pdf", tmp_path / "out.pdf", languages="eng", command="ocrmypdf", timeout_seconds=1)


def test_run_ocrmypdf_returns_created_output(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda command: "ocrmypdf")
    output_pdf = tmp_path / "out.pdf"

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        Path(args[-1]).write_bytes(b"%PDF-1.7 ocr")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)

    assert ocr.run_ocrmypdf(tmp_path / "in.pdf", output_pdf, languages="eng", command="ocrmypdf", timeout_seconds=1) == output_pdf


def test_run_ocrmypdf_uses_force_ocr_when_requested(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda command: "ocrmypdf")
    output_pdf = tmp_path / "out.pdf"
    captured_args: list[str] = []

    def fake_run(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        captured_args.extend(args)
        Path(args[-1]).write_bytes(b"%PDF-1.7 ocr")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)

    ocr.run_ocrmypdf(tmp_path / "in.pdf", output_pdf, languages="eng", command="ocrmypdf", timeout_seconds=1, force=True)

    assert "--force-ocr" in captured_args
    assert "--skip-text" not in captured_args


def test_resolve_command_falls_back_to_python_scripts_dir(monkeypatch, tmp_path) -> None:
    scripts_dir = tmp_path / "Scripts"
    scripts_dir.mkdir()
    command_path = scripts_dir / "ocrmypdf.exe"
    command_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(ocr.shutil, "which", lambda command: None)
    monkeypatch.setattr(ocr.sys, "executable", str(scripts_dir / "python.exe"))

    assert ocr._resolve_command("ocrmypdf") == str(command_path)


def test_ocr_env_prepends_existing_tool_dirs(monkeypatch, tmp_path) -> None:
    tesseract_dir = tmp_path / "Tesseract-OCR"
    ghostscript_dir = tmp_path / "gs" / "bin"
    tesseract_dir.mkdir()
    ghostscript_dir.mkdir(parents=True)

    monkeypatch.setattr(ocr, "_OCR_TOOL_DIRS", [tesseract_dir, ghostscript_dir])
    monkeypatch.setenv("PATH", "original")

    env = ocr._ocr_env()

    assert env["PATH"].startswith(f"{tesseract_dir}{ocr.os.pathsep}{ghostscript_dir}{ocr.os.pathsep}")
