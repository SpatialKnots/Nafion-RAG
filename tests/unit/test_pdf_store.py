from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.pdf_store import copy_original_pdf, ocr_pdf_path, stable_pdf_name


def test_stable_pdf_name_keeps_pdf_suffix() -> None:
    name = stable_pdf_name("a" * 64, Path("My Paper.PDF"))

    assert name.startswith("aaaaaaaaaaaaaaaa_")
    assert name.endswith(".pdf")


def test_copy_original_pdf_rejects_non_pdf(tmp_path) -> None:
    source = tmp_path / "paper.txt"
    source.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ValueError, match="Only PDF"):
        copy_original_pdf(source, tmp_path / "data", "a" * 64)


def test_copy_original_pdf_preserves_content(tmp_path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7 test")

    copied = copy_original_pdf(source, tmp_path / "data", "b" * 64)

    assert copied.read_bytes() == b"%PDF-1.7 test"
    assert copied.parent == tmp_path / "data" / "pdf"


def test_ocr_pdf_path_uses_processed_ocr_dir(tmp_path) -> None:
    path = ocr_pdf_path(Path("Paper.PDF"), tmp_path / "data", "c" * 64)

    assert path.parent == tmp_path / "data" / "processed" / "ocr"
    assert path.name.startswith("cccccccccccccccc_")
    assert path.name.endswith(".pdf")
