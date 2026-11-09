"""Authorization/budget controls only; no actual transport or DB calls."""

import pytest

from scripts import run_reference_quote_live_20261105 as driver


def approval():
    return {"case_ids": list(driver.IDS), "request_sha256": dict(driver.REQUESTS), "maximum_model_attempts": 2,
            "maximum_oauth_attempts": 2, "model": "GigaChat-2-Max", "max_output_tokens": 1200,
            "per_http_timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0,
            "infrastructure_continuations": 0, "raw_user_approval": "Давай, да"}


@pytest.mark.parametrize("key,value", [("maximum_model_attempts", 3), ("maximum_oauth_attempts", 3),
                                     ("max_output_tokens", 1201), ("per_http_timeout_seconds", 121),
                                     ("automatic_retries", 1), ("fallbacks", 1), ("infrastructure_continuations", 1),
                                     ("case_ids", ["Q01"]), ("request_sha256", {}), ("raw_user_approval", ""),
                                     ("model", "different")])
def test_approval_rejects_any_scope_drift(key, value):
    candidate = approval()
    candidate[key] = value
    with pytest.raises(ValueError, match="Approval differs"):
        driver.validate_approval(candidate)


def test_exact_scope_is_accepted():
    driver.validate_approval(approval())


def test_no_authorization_stops_before_any_input_read(monkeypatch):
    monkeypatch.setattr(driver, "read", lambda *a: pytest.fail("No reads before approval flag"))
    with pytest.raises(PermissionError):
        driver.run("Q01", driver.files.NetworkPolicy(), authorized=False)


def test_other_case_stops_before_any_input_read(monkeypatch):
    monkeypatch.setattr(driver, "read", lambda *a: pytest.fail("Other cases forbidden"))
    with pytest.raises(ValueError, match="outside"):
        driver.run("Q02", driver.files.NetworkPolicy(), authorized=True)


def test_existing_slot_blocks_configuration_or_transport(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "BASE", tmp_path / "output")
    monkeypatch.setattr(driver.files, "LEDGER", tmp_path / "ledger")
    monkeypatch.setattr(driver, "read", lambda *a: approval())
    (driver.files.LEDGER / driver.REQUESTS["Q01"]).mkdir(parents=True)
    monkeypatch.setattr(driver, "verify_original", lambda *a: pytest.fail("No new preparation for existing slot"))
    with pytest.raises(FileExistsError, match="no repeat"):
        driver.run("Q01", driver.files.NetworkPolicy(), authorized=True)


@pytest.mark.parametrize("status", ["unhandled_or_interrupted", "failed", "unknown"])
def test_unknown_first_outcome_blocks_second(status, monkeypatch):
    monkeypatch.setattr(driver, "read", lambda path: approval() if path == driver.APPROVAL else {"status": status})
    monkeypatch.setattr(driver, "verify_original", lambda *a: pytest.fail("Unknown outcome must stop before preparation"))
    with pytest.raises(ValueError, match="stops batch"):
        driver.run("Q05", driver.files.NetworkPolicy(), authorized=True)
