"""Constructed allowance/closure controls; no real DB, OAuth or model execution."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_answer_series_live_20261111 as run


@pytest.fixture
def scope(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "BASE", tmp_path / "run")
    monkeypatch.setattr(run, "LEDGER", tmp_path / "ledger")
    run.BASE.mkdir()
    return tmp_path


def approval(count=30):
    rows = [{"id": f"Case_{n:02}", "request_sha256": f"{n:064x}"} for n in range(1, count + 1)]
    run.f.write(run.BASE / "approval_v01.json", {"cases": rows})
    return rows


@pytest.mark.parametrize("path", [run.previous.USER_FILE, run.BASE / "review_v01/report.json",
                                  run.BASE / "assessment_v01/notes.json", run.BASE / "private_gold/data.json"])
def test_inference_cannot_open_original_reference_or_review(path):
    guard = run.InferenceReadGuard()
    with pytest.raises(PermissionError):
        guard("open", (str(path), "r"))
    assert guard.denied == [str(path.resolve())]


@pytest.mark.parametrize("path", [run.audit.FINAL / "Kondo_01/after.json", run.BASE / "prepared_v01/Kondo_01/request.json",
                                  run.SCOPE, run.f.ROOT / "app/generation/service.py"])
def test_inference_can_read_exact_questions_native_and_runtime(path):
    guard = run.InferenceReadGuard()
    guard("open", (str(path), "r"))
    assert guard.denied == []


def test_closure_does_not_invent_zero_attempts_for_reserved_unknown(scope):
    rows = approval()
    (run.LEDGER / rows[0]["request_sha256"]).mkdir(parents=True)
    result = run.close()
    assert len(result["cases"]) == 30 and result["remaining_allowance"] == 0
    assert result["cases"][0]["status"] == "reserved_outcome_unknown"
    assert result["model_attempts"] is result["oauth_attempts"] is None
    assert result["cases"][1]["model_attempts"] == 0
    assert all(r["allowance_closed"] and not r["resend_authorized"] for r in result["cases"])


def test_closed_scope_is_idempotent_and_preserves_original_outcomes(scope):
    rows = approval()
    saved = {"status": "runtime_api_result", "http_status": 502, "model_attempts": 1, "oauth_attempts": 1}
    folder = run.BASE / "live" / rows[0]["id"]
    folder.mkdir(parents=True)
    run.f.write(folder / "result.json", saved)
    result = run.close()
    raw = (run.BASE / "scope_closed_v01.json").read_bytes()
    assert run.close() == result
    assert (run.BASE / "scope_closed_v01.json").read_bytes() == raw
    assert run.read(folder / "result.json") == saved
    assert result["model_attempts"] == result["oauth_attempts"] == 1


def test_closure_rejects_exceeded_allowance(scope):
    for row in approval(31):
        folder = run.BASE / "live" / row["id"]
        folder.mkdir(parents=True)
        run.f.write(folder / "result.json", {"model_attempts": 1, "oauth_attempts": 1})
    with pytest.raises(ValueError, match="Allowance exceeded"):
        run.close()
    assert not (run.BASE / "scope_closed_v01.json").exists()


@pytest.mark.parametrize("status,exit_code,expected", [(503, 0, 1), (None, 1, 1), (502, 0, 30), (200, 0, 30)])
def test_batch_stops_on_transport_or_unknown_failure_without_retry_and_closes(scope, monkeypatch, status, exit_code, expected):
    monkeypatch.setattr(run, "verify_runtime", lambda: [{"id": c} for c in run.audit.IDS])
    monkeypatch.setattr(run.f, "configure", lambda: SimpleNamespace(gigachat_credentials="secret", database_url="db-secret"))
    calls, closed = [], []

    def worker(command, **kwargs):
        calls.append(command)
        value = {"id": command[-1], "http_status": status}
        return SimpleNamespace(returncode=exit_code, stdout=json.dumps(value) + "\n", stderr="secret/db-secret")

    monkeypatch.setattr(run.subprocess, "run", worker)
    monkeypatch.setattr(run, "close", lambda: closed.append(True))
    result = run.batch("send")
    assert len(calls) == expected and len(closed) == 1
    assert result["finished_all"] == (expected == 30)
    assert len({cmd[-1] for cmd in calls}) == expected
    logs = list(run.BASE.rglob("*_stderr.txt"))
    assert len(logs) == expected and all("secret" not in p.read_text() for p in logs)


def test_seal_rejects_native_drift_before_any_reservation(scope, monkeypatch):
    case = {"id": "Kondo_01"}
    monkeypatch.setattr(run, "verify_runtime", lambda: [case])
    folder = run.BASE / "prepared_v01/Kondo_01"
    folder.mkdir(parents=True)
    run.f.save(folder / "request.json", b"changed native")
    run.f.write(folder / "contract.json", {"case": case, "dispatch_allowed": True, "input_bindings": {},
                                           "request_sha256": run.f.sha(b"original native")})
    run.f.manifest(folder)
    with pytest.raises(ValueError, match="Prepared request drift"):
        run.seal()
    assert not (run.BASE / "approval_v01.json").exists() and not run.LEDGER.exists()


def test_runtime_rejects_closed_scope_before_any_dispatch(scope, monkeypatch):
    folder = run.BASE / "input_freeze_v01"
    folder.mkdir()
    run.f.write(folder / "bindings.json", {})
    run.f.manifest(folder)
    run.f.write(run.BASE / "scope_closed_v01.json", {"remaining_allowance": 0})
    monkeypatch.setattr(run.audit, "app_paths", lambda: [])
    with pytest.raises(ValueError, match="Scope is closed"):
        run.verify_runtime()


def test_runtime_rejects_added_application_file(scope, monkeypatch):
    folder = run.BASE / "input_freeze_v01"
    folder.mkdir()
    run.f.write(folder / "bindings.json", {})
    run.f.manifest(folder)
    monkeypatch.setattr(run.audit, "app_paths", lambda: [Path(run.__file__)])
    with pytest.raises(ValueError, match="Application file set changed"):
        run.verify_runtime()
