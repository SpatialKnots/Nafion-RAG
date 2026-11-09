"""Real Unicode failure regressions and literal diagnostic controls; no transport."""

import pytest

from scripts.review_reference_quote_live_20261105 import character_comparison


def test_exact_text_and_citation_match():
    result = character_comparison({"E1": ["Quote 12.3"]}, [{"text": "Quote 12.3", "citation_ids": ["E1"]}])
    assert result["all_required_claims_exact"] and result["exact_claims"] == 1
    assert result["claims"][0]["character_changes"] == []


@pytest.mark.parametrize("expected,actual,old_points,new_points", [
    ("«ABSTRACT: 12.3»", "\uababSTRACT: 12.3»", ["U+00AB", "U+0041", "U+0042"], ["U+ABAB"]),
    ("«Dissolution: 12.3»", "\u0abdissolution: 12.3»", ["U+00AB", "U+0044"], ["U+0ABD"]),
])
def test_unicode_change_is_preserved_not_silently_repaired(expected, actual, old_points, new_points):
    result = character_comparison({"E1": [expected]}, [{"text": actual, "citation_ids": ["E1"]}])
    record = result["claims"][0]
    assert not result["all_required_claims_exact"] and result["exact_claims"] == 0
    assert record["actual_claim"]["text"] == actual
    assert record["digit_surface_sequences_equal"]
    assert not record["scientific_value_or_unit_ownership_validated"]
    assert record["character_changes"][0]["expected_codepoints"] == old_points
    assert record["character_changes"][0]["actual_codepoints"] == new_points


def test_numeric_change_is_not_called_equal():
    result = character_comparison({"E1": ["0.034"]}, [{"text": "0.035", "citation_ids": ["E1"]}])
    assert not result["claims"][0]["digit_surface_sequences_equal"]


def test_wrong_citation_does_not_pass_even_for_exact_text():
    result = character_comparison({"E1": ["raw quote"]}, [{"text": "raw quote", "citation_ids": ["other"]}])
    assert result["claims"][0]["exact_text"] and not result["claims"][0]["exact_citation"]
    assert not result["all_required_claims_exact"] and result["exact_claims"] == 0


def test_missing_second_quote_is_not_complete():
    result = character_comparison({"E1": ["method"], "E2": ["table"]}, [{"text": "method", "citation_ids": ["E1"]}])
    assert result["exact_claims"] == 1 and not result["all_required_claims_exact"]
