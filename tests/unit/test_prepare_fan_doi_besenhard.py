"""Synthetic parser controls; no supplied scientific references or external calls."""

import pytest

from scripts import prepare_fan_doi_besenhard_20261113 as prep
from scripts.prepare_fan_doi_besenhard_20261113 import IDS, ReferenceGuard, parse_document


def document():
    return "\r\n".join(f"### {cid}. Вопрос {cid}?\r\n\r\n**Эталонный ответ:** PRIVATE-{cid}"
                         f"\r\n\r\n**Источник:** PAGE-HINT-{cid}" for cid in IDS)


def test_exact_headings_only():
    text = document()
    cases = parse_document(text)
    assert [c["id"] for c in cases] == IDS
    for c in cases:
        assert text[c["question_span"]["start"]:c["question_span"]["end"]] == c["question_original"]
        assert "PRIVATE" not in str(c)
        assert "PAGE-HINT" not in str(c)
        assert c["question"].endswith(c["question_original"])


@pytest.mark.parametrize("change", [
    lambda t: t.replace("### F2.", "### F1."),
    lambda t: t.replace("### D10.", "### D11."),
    lambda t: t.replace("**Эталонный ответ:** PRIVATE-B10", "missing"),
    lambda t: t.replace("**Источник:** PAGE-HINT-D1", "**Источник:** a **Источник:** b"),
    lambda t: t + "\r\n### F1. Duplicate?",
])
def test_malformed_receipts_rejected(change):
    with pytest.raises(ValueError):
        parse_document(change(document()))


def test_worker_reference_files_rejected():
    guard = ReferenceGuard()
    for name in [prep.USER_FILE, prep.PRIVATE / "supplied_original.md",
                 prep.f.ROOT / "output/answer_series_live_20261111/review_v02/report.json"]:
        with pytest.raises(PermissionError):
            guard("open", (name, "r", 0))
    assert len(guard.denied) == 3


def test_worker_question_and_app_reads_allowed():
    guard = ReferenceGuard()
    for name in [prep.FREEZE / "questions.json", prep.f.ROOT / "app/generation/service.py"]:
        guard("open", (name, "r", 0))
    assert guard.denied == []
