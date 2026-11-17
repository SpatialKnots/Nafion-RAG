"""Negative scope controls before any external answer dispatch."""

from copy import deepcopy

import pytest

from scripts import run_fan_doi_besenhard_answers_20261113 as run


def inputs():
    native = b'{"model":"GigaChat-2-Max","max_tokens":1200}'
    case = {"id": "Synthetic", "question": "original"}
    approved = {"id": "Synthetic", "request_sha256": run.f.sha(native)}
    contract = {"case": case, "generation_reached": True, "eligible_for_future_scope": True,
        "article_scope_matches": True, "dispatch_allowed": False, "request_sha256": run.f.sha(native),
        "request_bytes": len(native), "transaction_read_only": "on", "transaction_end": "rollback",
        "network_denials": [], "reference_read_denials": []}
    return case, approved, contract, native


def test_eligible_preparation_keeps_original_dispatch_flag_false():
    case, approved, contract, native = inputs()
    before = deepcopy(contract)
    run.validate_case(case, approved, contract, native)
    assert contract == before


@pytest.mark.parametrize("field,value", [
    ("generation_reached", False), ("eligible_for_future_scope", False),
    ("article_scope_matches", False), ("dispatch_allowed", True),
    ("transaction_read_only", "off"), ("transaction_end", "commit"),
    ("network_denials", ["unexpected"]), ("request_sha256", "a" * 64),
])
def test_changed_or_unproven_preparation_is_rejected(field, value):
    case, approved, contract, native = inputs()
    with pytest.raises(ValueError):
        run.validate_case(case, approved, {**contract, field: value}, native)


def test_different_case_or_native_cannot_use_allowance():
    case, approved, contract, native = inputs()
    with pytest.raises(ValueError):
        run.validate_case(case, {**approved, "id": "Other"}, contract, native)
    with pytest.raises(ValueError):
        run.validate_case(case, approved, contract, native + b" ")


def test_answer_worker_guard_blocks_references_and_assessments():
    guard = run.ReferenceGuard()
    for path in (run.profile.baseline.USER_FILE, run.profile.baseline.PRIVATE / "supplied_original.md",
                 run.BASE / "assessment_v01/report.json"):
        with pytest.raises(PermissionError):
            guard("open", (str(path), "r", 0))


def test_answer_authorization_and_prepared_inputs_are_readable():
    guard = run.ReferenceGuard()
    for path in (run.BASE / "authorized_inputs_v01/authorization.json", run.SCOPE,
                 run.profile.BASE / "prepared_v01/F1/manifest.json"):
        guard("open", (str(path), "r", 0))
    assert not guard.denied
