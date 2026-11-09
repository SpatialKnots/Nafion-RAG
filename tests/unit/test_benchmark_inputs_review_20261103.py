"""Frozen native identity checks; constructed payloads only."""

import pytest

from scripts import gigachat_answer_smoke as files
from scripts.review_benchmark_inputs_20261103 import detail, verify_native


@pytest.mark.parametrize("change", [None, "hash", "size", "model", "limit", "question", "role"])
def test_native_identity_and_verbatim_question(change):
    question = "constructed question"
    value = {"model": "GigaChat-2-Max", "max_tokens": 1200, "messages": [{"role": "user", "content": question}]}
    if change == "model":
        value["model"] = "another-model"
    elif change == "limit":
        value["max_tokens"] = 1201
    elif change == "question":
        value["messages"][0]["content"] = "different question"
    elif change == "role":
        value["messages"][0]["role"] = "system"
    raw = files.encode(value)
    contract = {"request_sha256": files.sha(raw), "request_bytes": len(raw)}
    if change == "hash":
        contract["request_sha256"] = "0" * 64
    elif change == "size":
        contract["request_bytes"] += 1
    if change:
        with pytest.raises(ValueError):
            verify_native(raw, contract, question)
    else:
        assert verify_native(raw, contract, question) == value


def test_source_markup_is_text_not_executable_html():
    rendered = detail("<title>", "<script>constructed</script>")
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered and "&lt;title&gt;" in rendered
