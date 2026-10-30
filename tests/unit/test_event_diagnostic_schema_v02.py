"""Regression for native/local diagnostic contract divergence; no live calls."""

import copy
import json

import pytest
from pydantic import ValidationError

from scripts.event_diagnostic_schema_v02 import DiagnosticConstraint, corrected_request
from scripts.gigachat_event_proposal import build_request, catalog


@pytest.mark.parametrize(("value", "accepted"), [("", False), (" ", False), ("\n", False),
                                                 (None, False), (12, False), ("No additional uncertainty.", True)])
def test_nonblank_schema_contract_rejects_empty_whitespace_and_wrong_types(value, accepted):
    if accepted:
        assert DiagnosticConstraint.model_validate({"diagnostic": value}).diagnostic == value
    else:
        with pytest.raises(ValidationError):
            DiagnosticConstraint.model_validate({"diagnostic": value})


def test_correction_changes_only_diagnostic_schema_and_instruction_without_mutating_v01():
    original = build_request("How long?", catalog("Held for 2 hours."), model="GigaChat-2-Max", max_tokens=1200)
    frozen = copy.deepcopy(original)
    candidate = corrected_request(original)
    assert original == frozen and candidate != original
    assert "minLength" not in original["response_format"]["schema"]["properties"]["diagnostic"]
    assert candidate["response_format"]["schema"]["properties"]["diagnostic"]["minLength"] == 1
    assert candidate["response_format"]["schema"]["properties"]["diagnostic"]["pattern"] == r"\S"
    candidate["messages"][0] = original["messages"][0]
    candidate["response_format"]["schema"]["properties"]["diagnostic"] = (
        original["response_format"]["schema"]["properties"]["diagnostic"])
    assert json.dumps(candidate, sort_keys=True) == json.dumps(original, sort_keys=True)
