from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Article, Page, PageTextLayer
from app.documents.service import PageEvidenceNotFoundError, PdfStorageIntegrityError
from app.records.sources import file_hash, source_region_from_page, source_regions_from_pages, verify_live_region


@pytest.fixture
def source_fixture(tmp_path: Path) -> tuple[MagicMock, Settings, Article, Page, PageTextLayer]:
    data_root = tmp_path / "data"
    pdf = data_root / "pdf" / "a.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4\nsynthetic storage integrity fixture; not a parsed PDF")
    article = Article(id=uuid4(), title="Synthetic", pdf_original_path=str(pdf), checksum_sha256=file_hash(pdf))
    raw = "Li-Naﬁon\nionic conductivity at room temperature"
    page = Page(article_id=article.id, page_number=1, text=raw, selected_text_layer="original")
    layer = PageTextLayer(
        id=uuid4(), article_id=article.id, page_number=1, layer_type="original", text=raw, source_pdf_path=str(pdf),
    )
    session = MagicMock(spec=Session)
    session.get.return_value = article
    session.scalars.return_value.one_or_none.side_effect = [page, layer]
    return session, Settings(data_root=data_root), article, page, layer


def export(fixture: tuple[MagicMock, Settings, Article, Page, PageTextLayer], **kwargs):
    session, settings, article, _, _ = fixture
    return source_region_from_page(
        session, settings, article.id, 1, selection_basis="manual_development", selection_note="Synthetic fixture.", **kwargs,
    )


def test_selected_layer_exact_text_and_no_writes(source_fixture) -> None:
    session, _, article, _, layer = source_fixture
    region = export(source_fixture, start=0, end=8)
    assert region.quote == "Li-Naﬁon"
    assert region.page_text == layer.text
    assert region.original_pdf_sha256 == article.checksum_sha256
    assert region.text_layer_id == layer.id
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()
    queries = [call.args[0].compile().params for call in session.scalars.call_args_list]
    assert all(article.id in query.values() and 1 in query.values() for query in queries)


def test_ocr_tracks_separate_pdf_identity(source_fixture) -> None:
    session, settings, article, page, layer = source_fixture
    ocr = settings.data_root / "processed" / "ocr" / "a.pdf"
    ocr.parent.mkdir(parents=True)
    ocr.write_bytes(b"%PDF-1.4\nsynthetic OCR copy")
    article.pdf_ocr_path = str(ocr)
    page.selected_text_layer = "ocr"
    layer.layer_type = "ocr"
    layer.source_pdf_path = str(ocr)
    region = export(source_fixture)
    assert region.text_layer == "ocr"
    assert region.layer_pdf_sha256 == file_hash(ocr) != region.original_pdf_sha256
    assert region.layer_pdf_path == str(ocr.resolve())
    assert file_hash(Path(article.pdf_original_path)) == article.checksum_sha256
    session.commit.assert_not_called()


@pytest.mark.parametrize("mutation,error", [
    ("pdf_changed", "Original PDF checksum"),
    ("text_mismatch", "differs from recorded"),
    ("outside_path", "outside the allowed"),
    ("different_pdf", "differs from registered"),
    ("unknown_layer", "Unsupported recorded"),
])
def test_adapter_fails_on_stale_or_wrong_source(source_fixture, mutation: str, error: str) -> None:
    _, settings, article, page, layer = source_fixture
    if mutation == "pdf_changed":
        Path(article.pdf_original_path).write_bytes(b"changed")
    elif mutation == "text_mismatch":
        page.text = "selected text changed"
    elif mutation == "outside_path":
        layer.source_pdf_path = str(settings.data_root.parent / "outside.pdf")
    elif mutation == "different_pdf":
        other = settings.data_root / "pdf" / "other.pdf"
        other.write_bytes(b"%PDF-other")
        layer.source_pdf_path = str(other)
    else:
        page.selected_text_layer = "invented"
    with pytest.raises(PdfStorageIntegrityError, match=error):
        export(source_fixture)


def test_missing_recorded_layer_is_not_reconstructed(source_fixture) -> None:
    session, _, _, page, _ = source_fixture
    session.scalars.return_value.one_or_none.side_effect = [page, None]
    with pytest.raises(PageEvidenceNotFoundError, match="Missing recorded"):
        export(source_fixture)


def test_explicit_layer_does_not_require_selected_page(source_fixture) -> None:
    session, _, _, page, layer = source_fixture
    page.text = "different selected text"
    session.scalars.return_value.one_or_none.side_effect = [layer]
    assert export(source_fixture, layer="original").page_text == layer.text


def test_negative_region_offset_is_rejected(source_fixture) -> None:
    with pytest.raises(ValidationError):
        export(source_fixture, start=-1)


def test_live_verification_detects_modified_text_layer(source_fixture) -> None:
    session, settings, _, _, layer = source_fixture
    region = export(source_fixture)
    session.scalars.return_value.one_or_none.side_effect = [layer]
    verify_live_region(session, settings, region)
    layer.text += " new evidence"
    session.scalars.return_value.one_or_none.side_effect = [layer]
    with pytest.raises(PdfStorageIntegrityError, match="differs from live"):
        verify_live_region(session, settings, region)


def test_output_refuses_overwrite(tmp_path: Path) -> None:
    from app.records.cli import write_new

    target = tmp_path / "candidate.json"
    target.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_new(target, "replacement")
    assert target.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize("pages", [[], [0], [-1, 1], [1, 1]])
def test_page_batch_rejects_invalid_scope_before_reads(source_fixture, pages: list[int]) -> None:
    session, settings, article, _, _ = source_fixture
    with pytest.raises(ValueError):
        source_regions_from_pages(
            session, settings, article.id, pages,
            selection_basis="fixed_page", selection_note="Synthetic batch scope.",
        )
    session.get.assert_not_called()


def test_batch_keeps_distinct_pages_and_declared_order(source_fixture) -> None:
    session, settings, article, page, layer = source_fixture
    page2 = Page(article_id=article.id, page_number=2, text="Page two", selected_text_layer="original")
    layer2 = PageTextLayer(
        id=uuid4(), article_id=article.id, page_number=2, layer_type="original", text=page2.text,
        source_pdf_path=layer.source_pdf_path,
    )
    session.scalars.return_value.one_or_none.side_effect = [page2, layer2, page, layer]
    regions = source_regions_from_pages(
        session, settings, article.id, [2, 1], selection_basis="fixed_page", selection_note="Synthetic order check.",
    )
    assert [region.page_number for region in regions] == [2, 1]
    assert [region.quote for region in regions] == ["Page two", page.text]
    assert regions[0].region_id != regions[1].region_id
