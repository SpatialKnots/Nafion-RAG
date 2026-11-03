"""No real transport: scope/zero-budget preservation and no repeat/continuation."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_user_reference_live_20261030 as driver


def setup_case(tmp_path, monkeypatch):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    native = b'{"model":"GigaChat-2-Max","max_tokens":1200}'
    digest = driver.smoke.sha(native)
    monkeypatch.setattr(driver, "REQUEST_SHA", digest)
    monkeypatch.setattr(driver.smoke, "LEDGER", tmp_path / "ledger")
    config = SimpleNamespace(rag_model="GigaChat-2-Max", rag_gigachat_max_tokens=1200,
                             rag_timeout_seconds=120, gigachat_scope="GIGACHAT_API_PERS")
    monkeypatch.setattr(driver.smoke, "configure", lambda: config)
    contract = {"version": driver.PREP_VERSION, "question": "Constructed test question", "generation_reached": True,
                "blocking_reasons": [], "maximum_model_attempts": 0, "maximum_oauth_attempts": 0,
                "new_slot_reservations": 0, "input_bindings": {}, "request_sha256": digest, "request_bytes": len(native)}
    (prepared / "request.json").write_bytes(native)
    (prepared / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    driver.smoke.manifest(prepared)
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"request_sha256": digest, "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
        "max_output_tokens": 1200, "per_http_timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0,
        "raw_user_approval": "CONSTRUCTED TEST APPROVAL ONLY"}), encoding="utf-8")
    return prepared, approval, config


def test_no_authorization_fails_before_files_or_configuration(monkeypatch):
    monkeypatch.setattr(driver.smoke, "configure", lambda: pytest.fail("No configuration before approval"))
    with pytest.raises(PermissionError):
        driver.run(Path("missing"), Path("missing"), Path("missing"), driver.smoke.NetworkPolicy(), authorized=False)


def test_separate_authorized_copy_preserves_original_and_scope_globals(tmp_path, monkeypatch):
    prepared, approval, config = setup_case(tmp_path, monkeypatch)
    before = (prepared / "contract.json").read_bytes()
    old_globals = driver.smoke.QUESTION, driver.smoke.VERSION, driver.smoke.PROTOCOL

    def send(authorized_inputs, live, policy):
        derived = json.loads((authorized_inputs / "contract.json").read_bytes())
        assert derived["maximum_model_attempts"] == derived["maximum_oauth_attempts"] == 1
        assert driver.smoke.QUESTION == "Constructed test question"
        assert (authorized_inputs / "request.json").read_bytes() == (prepared / "request.json").read_bytes()
        return {"fake": True}

    monkeypatch.setattr(driver.smoke, "send", send)
    assert driver.run(prepared, tmp_path / "output", approval, driver.smoke.NetworkPolicy(), authorized=True) == {"fake": True}
    assert before == (prepared / "contract.json").read_bytes()
    assert old_globals == (driver.smoke.QUESTION, driver.smoke.VERSION, driver.smoke.PROTOCOL)
    assert not driver.smoke.LEDGER.exists()


@pytest.mark.parametrize("field,bad", [("rag_gigachat_max_tokens", 1201), ("rag_timeout_seconds", 121),
                                       ("rag_model", "GigaChat-3-Pro"), ("gigachat_scope", "GIGACHAT_API_B2B")])
def test_changed_model_or_limits_fail_before_send(tmp_path, monkeypatch, field, bad):
    prepared, approval, config = setup_case(tmp_path, monkeypatch)
    setattr(config, field, bad)
    monkeypatch.setattr(driver.smoke, "send", lambda *a: pytest.fail("No transport"))
    with pytest.raises(ValueError, match="limits differ"):
        driver.run(prepared, tmp_path / "output", approval, driver.smoke.NetworkPolicy(), authorized=True)


def test_existing_append_only_slot_forbids_repeat(tmp_path, monkeypatch):
    prepared, approval, config = setup_case(tmp_path, monkeypatch)
    (driver.smoke.LEDGER / driver.REQUEST_SHA).mkdir(parents=True)
    with pytest.raises(FileExistsError, match="no repeat"):
        driver.run(prepared, tmp_path / "output", approval, driver.smoke.NetworkPolicy(), authorized=True)


def test_different_approval_cannot_authorize_this_request(tmp_path, monkeypatch):
    prepared, approval, config = setup_case(tmp_path, monkeypatch)
    value = json.loads(approval.read_bytes())
    value["request_sha256"] = "f" * 64
    approval.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="Approval does not match"):
        driver.run(prepared, tmp_path / "output", approval, driver.smoke.NetworkPolicy(), authorized=True)
