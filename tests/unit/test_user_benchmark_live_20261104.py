"""Budget/identity controls only; no real provider or database operations."""

from pathlib import Path

import pytest

from scripts import run_user_benchmark_live_20261104 as driver


def approval():
    return {"case_ids": list(driver.IDS), "request_sha256": {k: k for k in driver.IDS},
            "maximum_model_attempts": 5, "maximum_oauth_attempts": 5,
            "model": "GigaChat-2-Max", "max_output_tokens": 1200,
            "per_http_timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0,
            "raw_user_approval": "CONSTRUCTED TEST APPROVAL"}


@pytest.mark.parametrize("key,value", [("maximum_model_attempts", 6), ("maximum_oauth_attempts", 6),
                                     ("max_output_tokens", 1201), ("per_http_timeout_seconds", 121),
                                     ("automatic_retries", 1), ("fallbacks", 1), ("raw_user_approval", ""),
                                     ("case_ids", ["Q01"]), ("request_sha256", {}), ("model", "different")])
def test_approval_rejects_scope_drift(key, value):
    value_before = approval()
    requests = value_before["request_sha256"].copy()
    value_before[key] = value
    with pytest.raises(ValueError, match="Approval differs"):
        driver.validate_approval(value_before, requests)


def test_no_authorization_stops_before_scope_or_configuration(monkeypatch):
    monkeypatch.setattr(driver, "read_scope", lambda: pytest.fail("No operations before authorization"))
    with pytest.raises(PermissionError):
        driver.run("Q01", driver.files.NetworkPolicy(), authorized=False)


def test_existing_slot_blocks_transport(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "BASE", tmp_path / "output")
    monkeypatch.setattr(driver.files, "LEDGER", tmp_path / "ledger")
    (driver.files.LEDGER / "digest").mkdir(parents=True)
    report = {"cases": [{"case": {"id": "Q01"}, "contract": {"request_sha256": "digest"}}]}
    monkeypatch.setattr(driver, "read_scope", lambda: (report, {"Q01": Path("unused")}))
    monkeypatch.setattr(driver.files, "configure", lambda: pytest.fail("No configuration or transport"))
    with pytest.raises(FileExistsError, match="no repeat"):
        driver.run("Q01", driver.files.NetworkPolicy(), authorized=True)
