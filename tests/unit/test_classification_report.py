from __future__ import annotations

from app.classification.report import write_classification_report


def test_write_classification_report_creates_timestamped_json(tmp_path) -> None:
    report = {"summary": {"article_count": 1}, "articles": []}

    output_path = write_classification_report(report, tmp_path)

    assert output_path.parent == tmp_path / "exports"
    assert output_path.name.startswith("classification_report_")
    assert output_path.name.endswith(".json")
    assert '"article_count": 1' in output_path.read_text(encoding="utf-8")
