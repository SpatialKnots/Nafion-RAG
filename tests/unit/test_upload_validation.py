from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz  # type: ignore[import-untyped]
import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.ingestion.upload import UploadValidationError, stage_upload_file


def _settings(tmp_path: Path, *, max_mb: int = 1) -> object:
    return SimpleNamespace(
        data_root=tmp_path / "data",
        upload_max_file_size_mb=max_mb,
        upload_read_chunk_bytes=8,
    )


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    return payload


def _upload(tmp_path: Path, name: str, payload: bytes, content_type: str = "application/pdf") -> UploadFile:
    path = tmp_path / name
    path.write_bytes(payload)
    return UploadFile(path.open("rb"), filename=name, headers=Headers({"content-type": content_type}), size=None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_stage_upload_accepts_valid_pdf_and_hashes(tmp_path) -> None:
    upload = _upload(tmp_path, "paper.PDF", _pdf_bytes())

    staged = await stage_upload_file(upload, _settings(tmp_path))  # type: ignore[arg-type]

    assert staged.path.is_file()
    assert staged.original_filename == "paper.PDF"
    assert len(staged.checksum_sha256) == 64
    assert staged.file_size_bytes > 0


@pytest.mark.anyio
async def test_stage_upload_rejects_non_pdf_extension(tmp_path) -> None:
    upload = _upload(tmp_path, "paper.txt", _pdf_bytes())

    with pytest.raises(UploadValidationError, match="Only .pdf"):
        await stage_upload_file(upload, _settings(tmp_path))  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_stage_upload_rejects_invalid_signature_and_removes_part(tmp_path) -> None:
    upload = _upload(tmp_path, "paper.pdf", b"not a pdf")

    with pytest.raises(UploadValidationError) as exc_info:
        await stage_upload_file(upload, _settings(tmp_path))  # type: ignore[arg-type]

    assert exc_info.value.code == "invalid_pdf_signature"
    incoming = tmp_path / "data" / "uploads" / "incoming"
    assert not list(incoming.glob("*.part"))
