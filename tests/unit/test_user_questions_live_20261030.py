"""Live driver fails closed without explicit approval; no real sends in tests."""

import json
from types import SimpleNamespace

import pytest

from scripts import run_user_questions_20261030_live as live


def test_dispatch_without_explicit_approval_reads_nothing_and_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "read_scope", lambda *a: pytest.fail("Do not read before authorization"))
    with pytest.raises(ValueError, match="authorization"):
        live.dispatch(tmp_path, tmp_path, authorized=False)


@pytest.mark.parametrize("case_id,authorized", [("q1_swelling_forms", False), ("q3_lithiation_methods", True), ("invented", True)])
def test_worker_rejects_unauthorized_or_blocked_cases_before_reading_marker(tmp_path, case_id, authorized):
    with pytest.raises(ValueError, match="eligible"):
        live.send_case(tmp_path, tmp_path, case_id, live.files.NetworkPolicy(), authorized=authorized)


def test_eligible_scope_is_exactly_two_and_has_no_lithiation_bypass():
    assert live.ELIGIBLE == ("q1_swelling_forms", "q2_best_mixture")


@pytest.mark.parametrize("unknown", [False, True])
def test_dispatch_runs_only_two_fresh_processes_cannot_repeat_and_preserves_unknown(tmp_path, monkeypatch, unknown):
    review = tmp_path / "review"
    review.mkdir()
    (review / "report.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(live, "read_scope", lambda *a: {"cases": [
        {"case": {"id": cid}, "contract": {"request_sha256": cid}} for cid in live.ELIGIBLE]})
    monkeypatch.setattr(live.files, "configure", lambda: SimpleNamespace(gigachat_credentials="fake-secret", database_url="fake-db"))
    seen = []

    def subprocess(command, **kwargs):
        case_id = command[command.index("--case-id") + 1]
        seen.append(case_id)
        assert command[:4] == [live.sys.executable, "-B", "-X", "utf8"]
        assert "--authorize-two-new-model-calls" in command and kwargs["capture_output"]
        if not unknown:
            folder = tmp_path / case_id / "live"
            folder.mkdir(parents=True)
            (folder / "result.json").write_text(json.dumps({"status": "runtime_answered", "http_status": 200,
                "model_attempts": 1, "oauth_attempts": 1}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="fake-secret fake-db")

    monkeypatch.setattr(live.subprocess, "run", subprocess)
    result = live.dispatch(tmp_path, review, authorized=True)
    assert seen == list(live.ELIGIBLE[:1] if unknown else live.ELIGIBLE)
    if unknown:
        assert result["cases"][0]["model_attempts"] is None
        assert result["cases"][0]["oauth_attempts"] is None
    with pytest.raises(FileExistsError):
        live.dispatch(tmp_path, review, authorized=True)
    assert (tmp_path / "q1_swelling_forms_live_worker_stderr.txt").read_text() == "[REDACTED] [REDACTED]"
