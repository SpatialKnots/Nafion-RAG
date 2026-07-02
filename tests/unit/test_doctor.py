from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.diagnostics import doctor


class FakeSession:
    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def execute(self, statement: object) -> object:
        return SimpleNamespace(scalar_one_or_none=lambda: "0001_initial_phase1")


def test_doctor_reports_missing_ocr_tools_without_crashing(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(Path.cwd())
    monkeypatch.setattr(doctor, "_current_alembic_head", lambda: "0001_initial_phase1")
    monkeypatch.setattr(doctor, "_resolve_command", lambda command: None)
    monkeypatch.setattr(doctor, "_resolve_tool", lambda candidates: None)

    report = doctor.run_doctor(Settings(data_root=tmp_path), lambda: FakeSession())  # type: ignore[arg-type]

    assert report["database"]["status"] == "PASS"
    assert report["migrations"]["status"] == "PASS"
    assert report["data_root"]["status"] == "PASS"
    assert report["ocr_command"]["status"] == "FAIL"
    assert report["tesseract_languages"]["status"] == "FAIL"
    assert report["ghostscript"]["status"] == "FAIL"


def test_doctor_accepts_required_tesseract_languages(monkeypatch) -> None:
    monkeypatch.setattr(doctor, "_resolve_tool", lambda candidates: "tesseract")
    monkeypatch.setattr(doctor, "_ocr_env", lambda: {})

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="List of available languages\neng\nrus\n", stderr="")

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)

    result = doctor._check_tesseract_languages({"eng", "rus"})

    assert result["status"] == "PASS"


def test_doctor_rejects_local_tessdata_without_hocr_config(monkeypatch, tmp_path) -> None:
    tessdata_dir = tmp_path / "tessdata"
    tessdata_dir.mkdir()
    monkeypatch.setattr(doctor, "_resolve_tool", lambda candidates: "tesseract")
    monkeypatch.setattr(doctor, "_ocr_env", lambda: {"TESSDATA_PREFIX": str(tessdata_dir)})

    result = doctor._check_tesseract_languages({"eng", "rus"})

    assert result["status"] == "FAIL"
    assert result["message"] == "tesseract hocr config is missing from TESSDATA_PREFIX"
