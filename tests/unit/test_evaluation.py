from __future__ import annotations

import pytest

from app.evaluation.retrieval import load_questions


def test_load_questions_rejects_malformed_entries(tmp_path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text("- id: q01\n  expected_article_dois: []\n  expected_keywords: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="q01.query"):
        load_questions(path)


def test_load_questions_accepts_expected_fields(tmp_path) -> None:
    path = tmp_path / "questions.yaml"
    path.write_text(
        "- id: q01\n"
        "  query: Li-Nafion conductivity\n"
        "  expected_article_dois:\n"
        "    - 10.1000/Example\n"
        "  expected_keywords:\n"
        "    - conductivity\n",
        encoding="utf-8",
    )

    questions = load_questions(path)

    assert questions[0].id == "q01"
    assert questions[0].expected_article_dois == ["10.1000/example"]
    assert questions[0].expected_keywords == ["conductivity"]
