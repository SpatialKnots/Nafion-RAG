from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.documents.service import (
    PdfLayerUnavailableError,
    PdfNotFoundError,
    PdfStorageIntegrityError,
    build_pdf_url,
    resolve_article_pdf,
)


def test_resolve_relative_original_path_inside_data_root(tmp_path) -> None:
    data_root = tmp_path / "data"
    pdf_path = data_root / "pdf" / "article.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    article = SimpleNamespace(id="article-id", title="A/B Title", pdf_original_path="data/pdf/article.pdf", pdf_ocr_path=None)

    resolved = resolve_article_pdf(article, SimpleNamespace(data_root=data_root), "original")  # type: ignore[arg-type]

    assert resolved.path == pdf_path.resolve()
    assert resolved.media_type == "application/pdf"
    assert resolved.download_name == "A_B_Title_original.pdf"


def test_resolve_absolute_ocr_path_inside_ocr_root(tmp_path) -> None:
    data_root = tmp_path / "data"
    pdf_path = data_root / "processed" / "ocr" / "article.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    article = SimpleNamespace(id="article-id", title=None, pdf_original_path="data/pdf/article.pdf", pdf_ocr_path=str(pdf_path))

    resolved = resolve_article_pdf(article, SimpleNamespace(data_root=data_root), "ocr")  # type: ignore[arg-type]

    assert resolved.path == pdf_path.resolve()


def test_resolve_rejects_external_absolute_path(tmp_path) -> None:
    data_root = tmp_path / "data"
    external = tmp_path / "outside.pdf"
    external.write_bytes(b"%PDF-1.4\n")
    article = SimpleNamespace(id="article-id", title="Article", pdf_original_path=str(external), pdf_ocr_path=None)

    with pytest.raises(PdfStorageIntegrityError):
        resolve_article_pdf(article, SimpleNamespace(data_root=data_root), "original")  # type: ignore[arg-type]


def test_resolve_rejects_path_traversal(tmp_path) -> None:
    data_root = tmp_path / "data"
    article = SimpleNamespace(id="article-id", title="Article", pdf_original_path="pdf/../outside.pdf", pdf_ocr_path=None)

    with pytest.raises(PdfStorageIntegrityError):
        resolve_article_pdf(article, SimpleNamespace(data_root=data_root), "original")  # type: ignore[arg-type]


def test_resolve_rejects_missing_ocr_layer(tmp_path) -> None:
    article = SimpleNamespace(id="article-id", title="Article", pdf_original_path="data/pdf/article.pdf", pdf_ocr_path=None)

    with pytest.raises(PdfLayerUnavailableError):
        resolve_article_pdf(article, SimpleNamespace(data_root=tmp_path / "data"), "ocr")  # type: ignore[arg-type]


def test_resolve_rejects_missing_pdf_file(tmp_path) -> None:
    article = SimpleNamespace(id="article-id", title="Article", pdf_original_path="data/pdf/missing.pdf", pdf_ocr_path=None)

    with pytest.raises(PdfNotFoundError):
        resolve_article_pdf(article, SimpleNamespace(data_root=tmp_path / "data"), "original")  # type: ignore[arg-type]


def test_resolve_rejects_non_pdf_file(tmp_path) -> None:
    data_root = tmp_path / "data"
    text_path = data_root / "pdf" / "article.txt"
    text_path.parent.mkdir(parents=True)
    text_path.write_text("not pdf", encoding="utf-8")
    article = SimpleNamespace(id="article-id", title="Article", pdf_original_path="data/pdf/article.txt", pdf_ocr_path=None)

    with pytest.raises(PdfStorageIntegrityError):
        resolve_article_pdf(article, SimpleNamespace(data_root=data_root), "original")  # type: ignore[arg-type]


def test_build_pdf_url_uses_relative_public_route() -> None:
    assert build_pdf_url("11111111-1111-1111-1111-111111111111", "original", 7) == (
        "/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=7"
    )
