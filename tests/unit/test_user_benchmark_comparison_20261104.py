"""Ensure side-by-side presentation preserves text and distinguishes errors."""

from scripts import review_user_benchmark_live_20261104 as review


def test_original_answer_is_not_rewritten():
    original = "Строка 1\n\nЧисло −65.0 Дж/г [E2]; 137%."
    assert review.program_text({"http_status": 200, "body": {"status": "answered", "answer": original}}) == original


def test_technical_failure_not_presented_as_model_answer():
    value = review.program_text({"http_status": 502, "body": {"detail": "filtered"}})
    assert value == "Техническая ошибка HTTP 502: filtered"


def test_abstention_remains_no_answer():
    value = review.program_text({"http_status": 200, "body": {"status": "insufficient_evidence", "answer": None}})
    assert value == "Ответ не выдан: insufficient_evidence"
    assert review.program_text(None).startswith("Не отправлен")


def test_reference_markup_is_escaped_and_numbers_kept():
    html = review.markdown("**Условие** <script>alert(1)</script>\n\n| A | B |\n|---|---:|\n| b1 | 0.228 |")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<strong>Условие</strong>" in html
    assert "<td>0.228</td>" in html
    assert html.count("<tr>") == 2


def test_json_diagnostic_is_escaped():
    html = review.detail("<img>", {"text": "</pre><script>"})
    assert "<img>" not in html and "<script>" not in html
    assert "&lt;img&gt;" in html
