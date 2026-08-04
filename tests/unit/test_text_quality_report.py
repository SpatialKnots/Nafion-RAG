from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.extraction.text_quality_report import build_reprocess_text_quality_dry_run, build_text_quality_report


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self) -> None:
        self.collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
        self.article = SimpleNamespace(
            id=uuid.uuid4(),
            collection_id=self.collection.id,
            title="Quality paper",
            doi="10.1000/quality",
            status="indexed",
            pdf_original_path="data/pdf/original.pdf",
            pdf_ocr_path="data/processed/ocr/ocr.pdf",
        )
        self.page = SimpleNamespace(
            id=uuid.uuid4(),
            article_id=self.article.id,
            page_number=1,
            text="Table 1. Data\nA    1.0    2.0    3.0\nIEC = nSO3H / m",
            has_text_layer=True,
            ocr_used=False,
            selected_text_layer="original",
        )
        self.original_layer = SimpleNamespace(
            id=uuid.uuid4(),
            article_id=self.article.id,
            page_number=1,
            layer_type="original",
            text=self.page.text,
            has_usable_text=True,
            quality_score=0.9,
            source_pdf_path="original.pdf",
        )
        self.short_page = SimpleNamespace(
            id=uuid.uuid4(),
            article_id=self.article.id,
            page_number=2,
            text="bad\ufffd",
            has_text_layer=True,
            ocr_used=True,
            selected_text_layer="original",
        )
        self.short_original_layer = SimpleNamespace(
            id=uuid.uuid4(),
            article_id=self.article.id,
            page_number=2,
            layer_type="original",
            text="bad\ufffd",
            has_usable_text=False,
            quality_score=0.1,
            source_pdf_path="original.pdf",
        )
        self.ocr_layer = SimpleNamespace(
            id=uuid.uuid4(),
            article_id=self.article.id,
            page_number=2,
            layer_type="ocr",
            text="OCR recovered text " * 20,
            has_usable_text=True,
            quality_score=0.8,
            source_pdf_path="ocr.pdf",
        )
        self.committed = False

    def scalar(self, statement: object) -> object | None:
        if "count" in str(statement):
            return 3
        return self.collection

    def scalars(self, statement: object) -> FakeScalarResult:
        text = str(statement)
        if "FROM articles" in text:
            return FakeScalarResult([self.article])
        if "FROM pages" in text:
            return FakeScalarResult([self.page, self.short_page])
        if "FROM page_text_layers" in text:
            return FakeScalarResult([self.original_layer, self.short_original_layer, self.ocr_layer])
        return FakeScalarResult([])

    def execute(self, statement: object) -> object:
        text = str(statement)
        if "chunks.source_type" in text:
            rows = [("body", 2), ("method", 1)]
        elif "chunks.text_layer" in text:
            rows = [("original", 3)]
        else:
            rows = []
        return SimpleNamespace(all=lambda: rows)

    def commit(self) -> None:
        self.committed = True


def test_text_quality_report_collects_diagnostics_without_mutation(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr("app.extraction.text_quality_report.shutil.which", lambda command: None)

    report = build_text_quality_report(session, _settings(), "literature")  # type: ignore[arg-type]

    assert report["collection"] == "literature"
    assert report["article_count"] == 1
    assert report["page_count"] == 2
    assert report["short_original_page_count"] == 2
    assert report["ocr_used_pages"] == 1
    assert report["caption_candidates"][0]["caption_count"] == 1
    assert report["formula_candidates"][0]["formula_like_line_count"] == 1
    assert report["source_type_distribution"] == {"body": 2, "method": 1}
    assert report["ocr_diagnostics"]["version_status"] == "command_not_found"
    assert session.committed is False


def test_reprocess_text_quality_dry_run_reports_candidate_actions_without_mutation(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr("app.extraction.text_quality_report.shutil.which", lambda command: None)

    report = build_reprocess_text_quality_dry_run(session, _settings(), session.article)  # type: ignore[arg-type]

    assert report["dry_run"] is True
    assert report["mutation_performed"] is False
    assert report["current_counts"] == {"pages": 2, "page_text_layers": 3, "chunks": 3}
    assert report["candidate_actions"]["evaluate_table_or_caption_evidence"] >= 1
    assert report["candidate_actions"]["evaluate_formula_evidence"] >= 1
    assert report["rollback_note"].startswith("Dry run only")
    assert session.committed is False


def _settings() -> object:
    return SimpleNamespace(
        text_quality_short_page_chars=80,
        text_quality_control_char_ratio=0.01,
        ocr_enabled=True,
        ocr_command="ocrmypdf",
        ocr_languages="eng+rus",
        ocr_reprocess_allow_existing=False,
    )
