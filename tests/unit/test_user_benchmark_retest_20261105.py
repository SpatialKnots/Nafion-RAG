"""New live-scope controls, without database or transport."""

import pytest

from scripts import run_user_benchmark_retest_20261105 as driver


def approval():
    return {"case_ids": list(driver.IDS), "request_sha256": {cid: cid for cid in driver.IDS},
            "maximum_model_attempts": 5, "maximum_oauth_attempts": 5, "model": "GigaChat-2-Max",
            "max_output_tokens": 1200, "per_http_timeout_seconds": 120, "automatic_retries": 0,
            "fallbacks": 0, "infrastructure_continuations": 0, "raw_user_approval": "Го новый тест"}


@pytest.mark.parametrize("key,value", [("case_ids", ["Q01"]), ("request_sha256", {}),
    ("maximum_model_attempts", 6), ("maximum_oauth_attempts", 6), ("model", "other"),
    ("max_output_tokens", 1201), ("per_http_timeout_seconds", 121), ("automatic_retries", 1),
    ("fallbacks", 1), ("infrastructure_continuations", 1), ("raw_user_approval", "")])
def test_scope_drift_fails(key, value):
    candidate = approval()
    candidate[key] = value
    with pytest.raises(ValueError):
        driver.validate_approval(candidate, approval()["request_sha256"])


def test_exact_new_scope():
    driver.validate_approval(approval(), approval()["request_sha256"])


def test_no_authorization_before_reads(monkeypatch):
    monkeypatch.setattr(driver, "read", lambda *a: pytest.fail("No input reads"))
    with pytest.raises(PermissionError):
        driver.run("Q01", driver.files.NetworkPolicy(), authorized=False)
    with pytest.raises(PermissionError):
        driver.seal(authorized=False)


def test_other_case_rejected_before_reads(monkeypatch):
    monkeypatch.setattr(driver, "read", lambda *a: pytest.fail("No input reads"))
    with pytest.raises(ValueError):
        driver.run("Q06", driver.files.NetworkPolicy(), authorized=True)


def test_closed_scope_blocks_before_preparations(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "BASE", tmp_path)
    (tmp_path / "scope_close_v01.json").write_text("{}")
    monkeypatch.setattr(driver, "preparations", lambda: pytest.fail("No preparation"))
    with pytest.raises(FileExistsError):
        driver.run("Q01", driver.files.NetworkPolicy(), authorized=True)


@pytest.mark.parametrize("status", ["failed", "unhandled_or_interrupted", "unknown"])
def test_unknown_previous_stops_batch(status, tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "BASE", tmp_path)
    monkeypatch.setattr(driver, "read", lambda *a: {"status": status})
    monkeypatch.setattr(driver, "preparations", lambda: pytest.fail("No preparation"))
    with pytest.raises(ValueError, match="stops batch"):
        driver.run("Q02", driver.files.NetworkPolicy(), authorized=True)
