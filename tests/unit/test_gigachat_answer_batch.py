"""Batch scope, isolation and no-repeat guards without inference or a database."""

import json
from types import SimpleNamespace

import pytest

from scripts import gigachat_answer_batch as batch
from scripts import gigachat_answer_smoke as smoke


def test_case_scope_restores_question_after_failure():
    question, protocol = smoke.QUESTION, smoke.PROTOCOL
    with pytest.raises(RuntimeError, match="constructed"):
        with batch.case_scope({"question": "different question"}):
            assert smoke.QUESTION == "different question"
            raise RuntimeError("constructed")
    assert smoke.QUESTION == question and smoke.PROTOCOL == protocol


def test_send_without_authorization_stops_before_loading_or_transport(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "read_batch", lambda *a: pytest.fail("must not load before authorization"))
    with pytest.raises(ValueError, match="authorization"):
        batch.send(tmp_path, smoke.NetworkPolicy())


def test_send_skips_gates_and_preparation_errors_and_cannot_repeat(tmp_path, monkeypatch):
    cases = [{"id": str(i), "question": str(i), "preparation_status": status,
              "prepared": str(tmp_path / str(i) / "prepared")}
             for i, status in enumerate(("ready", "gate_rejected", "preparation_failed", "ready"))]
    monkeypatch.setattr(batch, "read_batch", lambda *a: {"cases": cases})
    (tmp_path / "batch_contract.json").write_text(json.dumps({"cases": cases}), encoding="utf-8")
    seen = []

    def run_worker(mode, root, case):
        assert mode == "send"
        seen.append(case["question"])
        return {"status": "constructed_result", "model_attempts": 1, "oauth_attempts": 1}

    monkeypatch.setattr(batch, "run_worker", run_worker)
    result = batch.send(tmp_path, smoke.NetworkPolicy(), authorized=True)
    assert seen == ["0", "3"]
    assert result["total_cases"] == 4 and result["actual_model_attempts"] == 2
    assert result["cases"][1]["status"] == "gate_rejected"
    assert result["cases"][2]["status"] == "preparation_failed"
    with pytest.raises(FileExistsError):
        batch.send(tmp_path, smoke.NetworkPolicy(), authorized=True)
    assert seen == ["0", "3"]


def test_question_inventory_is_exactly_four_distinct_cases():
    cases = batch.load_cases()
    assert len(cases) == len({c["id"] for c in cases}) == 4
    assert all(c["assessment_rule"].strip() for c in cases)


@pytest.mark.parametrize("mode", ["prepare", "send"])
def test_each_case_launches_a_fresh_scoped_process(tmp_path, monkeypatch, mode):
    case = {"id": "constructed", "question": "constructed question"}
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        folder = tmp_path / "cases" / case["id"]
        folder.mkdir(parents=True)
        (folder / (mode + "_worker_result.json")).write_text(json.dumps({"id": case["id"]}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="constructed stdout", stderr="constructed-key")

    monkeypatch.setattr(batch.subprocess, "run", run)
    monkeypatch.setattr("app.core.config.Settings", lambda: SimpleNamespace(
        gigachat_credentials="constructed-key", database_url="constructed-db-url"))
    assert batch.run_worker(mode, tmp_path, case)["id"] == case["id"]
    command, options = calls[0]
    assert command[:4] == [batch.sys.executable, "-B", "-X", "utf8"]
    assert "--worker" in command and command[command.index("--case-id") + 1] == "constructed"
    assert ("--authorize-four-case-gigachat-batch" in command) == (mode == "send")
    assert options["capture_output"] is True and options["cwd"] == batch.ROOT
    assert (tmp_path / "cases/constructed" / (mode + "_worker_stderr.txt")).read_text() == "[REDACTED]"


def test_worker_cannot_send_without_parent_dispatch_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "send", lambda *a, **k: pytest.fail("unauthorized worker must not send"))
    value = batch.worker("send", tmp_path, {"id": "constructed", "question": "question"},
                         smoke.NetworkPolicy(), authorized=True)
    assert value["status"] == "worker_failed" and value["error_type"] == "ValueError"
    assert "parent" in value["error"]
