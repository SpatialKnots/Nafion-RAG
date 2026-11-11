"""Identical-native reuse is read-only and requires the exact prior request bytes."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import gigachat_answer_smoke as f
from scripts.review_query_rewriting_v02_20261110 import reuse_result


def fixture(tmp_path):
    original, prepared, ledger = tmp_path / "original", tmp_path / "prepared", tmp_path / "ledger"
    original.mkdir()
    prepared.mkdir()
    raw = b'{"model":"test","question":"same"}'
    digest = f.sha(raw)
    slot = ledger / digest
    slot.mkdir(parents=True)
    f.save(original / "request.json", raw)
    f.save(prepared / "request.json", raw)
    result = {"status": "runtime_answered", "model_attempts": 1}
    f.write(original / "result.json", result)
    f.write(slot / "result.json", result)
    f.write(slot / "attempt.json", {"output": str(original)})
    f.manifest(original)
    return original, prepared, ledger, digest, result


def test_reuse_matches_bytes_without_writing_old_outputs_or_slots(tmp_path):
    original, prepared, ledger, digest, result = fixture(tmp_path)
    before = f.bindings([*original.iterdir(), *(ledger / digest).iterdir()])
    with patch.object(f, "LEDGER", ledger):
        actual, folder = reuse_result(prepared, digest)
    assert actual == result and folder == original
    f.verify(before)


def test_different_prepared_body_cannot_reuse_prior_answer(tmp_path):
    _, prepared, ledger, digest, _ = fixture(tmp_path)
    (prepared / "request.json").write_bytes(b"different")
    with patch.object(f, "LEDGER", ledger), pytest.raises(ValueError, match="identical"):
        reuse_result(prepared, digest)


def test_ledger_cannot_direct_reader_outside_output_tree(tmp_path):
    _, prepared, ledger, digest, _ = fixture(tmp_path)
    (ledger / digest / "attempt.json").write_bytes(f.encode({"output": str(Path(f.ROOT) / "data/not-an-output")}))
    with patch.object(f, "LEDGER", ledger), pytest.raises(ValueError, match="outside"):
        reuse_result(prepared, digest)
