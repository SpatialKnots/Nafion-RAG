"""Constructed scope counterexamples; no provider or scientific accuracy claims."""

from dataclasses import replace

import pytest

from scripts.answer_scope_audit import PageSource, SuppliedEvidence, audit, numeric_relations, requirements, temperatures

QUESTION = "Какая максимальная степень набухания Li-Nafion при комнатной температуре?"


def page(text, **kwargs):
    return PageSource("work-a", 1, "original", "C:/constructed-fixture.pdf", "a" * 64, text,
                      "registered_original_run_page", **kwargs)


def evidence(text, **kwargs):
    return replace(SuppliedEvidence("E1", "work-a", "chunk-a", 1, 1, "original", text), **kwargs)


def run(text, claim="Максимальная степень набухания αLi = 1.54.", question=QUESTION, extra_pages=()):
    return audit(question, [{"text": claim, "citation_ids": ["E1"]}], [evidence(text)], [page(text), *extra_pages])


def check(result):
    return result["claims"][0]["checks"][0]


@pytest.mark.parametrize("question", [QUESTION, "Maximum swelling degree of Li-Nafion at room temperature?",
                                       "Макси-\nмальная степень набухания Li-Nafion?"])
def test_finite_maximum_and_form_question(question):
    req = requirements(question)
    assert req["maximum"] and req["swelling"] and req["forms"] == ["li"]


@pytest.mark.parametrize("question", ["Highest conductivity of Li-Nafion?", "What solvent was used?"])
def test_other_properties_remain_outside_scope(question):
    result = run("αLi = 1.54.", question=question)
    assert result["scientific_coverage"] == "outside_finite_maximum_swelling_scope"


def test_selected_values_never_establish_corpus_maximum_or_runtime_admission():
    result = run("Swelling αLi = 1.54 at 25°C.")
    assert result["scientific_coverage"] == "unresolved"
    assert result["runtime_action"] == "none_offline_only" and not result["answer_modified"]
    assert check(result)["numeric_surface_status"] == "present_unverified"
    assert "maximum_scope_and_candidate_completeness_not_established" in result["claims"][0]["diagnostics"]


def test_lexically_restricted_maximum_still_needs_completeness_proof():
    result = run("αLi = 1.54.", question="Максимальная степень набухания Li-Nafion среди индивидуальных растворителей?")
    assert result["requirements"]["comparison_restriction_cues"]
    assert result["requirements"]["medium_cues"]["individual_solvent"]
    assert result["scientific_coverage"] == "unresolved"


def test_room_temperature_is_not_silently_25_celsius():
    result = run("Swelling αLi = 1.54 at 25°C.")
    assert "room_temperature_numeric_equivalence_unresolved" in check(result)["temperature_check"]["diagnostics"]


def test_caption_temperature_is_visible_but_not_inherited():
    result = run("Swelling αLi = 1.54.\n\nFigure 1. Swelling at 25°C.", claim="αLi = 1.54 at 25°C.")
    assert result["source_context_inventory"][0]["temperature_candidates"]
    assert not check(result)["temperature_check"]["cited_value_statement_candidates"]
    assert "temperature_not_on_cited_value_statement" in check(result)["temperature_check"]["diagnostics"]


@pytest.mark.parametrize("text", ["Samples were cleaned at 80°C. Swelling αLi = 1.54.",
                                 "Cleaning at 80°C; swelling αLi = 1.54."])
def test_condition_from_different_operation_not_transferred(text):
    result = run(text, claim="αLi = 1.54 at 80°C.")
    assert not check(result)["temperature_check"]["cited_value_statement_candidates"]
    assert check(result)["operation_ownership"].startswith("unresolved")


def test_different_explicit_temperature_remains_diagnostic():
    result = run("Swelling αLi = 1.54 at 80°C.", claim="αLi = 1.54 at 25°C.")
    assert "different_explicit_temperature_points_locality_only" in check(result)["temperature_check"]["diagnostics"]


def test_two_temperature_value_pairs_in_one_statement_not_pooled_as_confirmation():
    result = run("αLi = 1.54 at 25°C and αLi = 1.6 at 50°C.", claim="αLi = 1.54 at 25°C.")
    assert "multiple_temperature_owners_unresolved" in check(result)["temperature_check"]["diagnostics"]
    assert result["scientific_coverage"] == "unresolved"


@pytest.mark.parametrize("raw,low,high", [("25 °С", "25", None), ("15–25°C", "15", "25"),
                                        ("-5°C", "-5", None), ("25,5 °C", "25.5", None)])
def test_celsius_points_ranges_and_raw_anchors(raw, low, high):
    found = temperatures(raw)
    assert len(found) == 1 and found[0]["low"] == low and found[0]["high"] == high
    assert raw[found[0]["start"]:found[0]["end"]] == found[0]["text"]


def test_range_is_not_a_point_temperature_match():
    result = run("αLi = 1.54 at 15–25°C.", claim="αLi = 1.54 at 25°C.")
    assert "range_point_equivalence_unresolved" in check(result)["temperature_check"]["diagnostics"]


def test_h_form_value_never_becomes_li_form_counterexample():
    result = run("Swelling αLi = 1.54. Values: 2.3 for H-form and 1.8 for Li-form.")
    larger = check(result)["larger_same_form_numeric_review_candidates"]
    assert [c["value"] for c in larger] == ["1.8"]
    assert all(c["form"] == "li" for c in larger)
    assert "property_and_material_identity_not_explicit_in_value_relation" in larger[0]["diagnostics"]


def test_claim_form_mismatch_is_explicit():
    result = run("αH = 2.3.", claim="αH = 2.3.")
    assert check(result)["requested_form_surface_status"] == "different_requested_form"


def test_posthoc_candidate_never_becomes_original_model_evidence():
    supplemental = replace(page("1.8 for Li-form."), page_number=2, origin="posthoc_original_pdf_page")
    result = run("αLi = 1.54.", extra_pages=[supplemental])
    candidate = check(result)["larger_same_form_numeric_review_candidates"][0]
    assert candidate["source"]["origin"] == "posthoc_original_pdf_page"
    assert not candidate["available_as_exact_fragment_in_supplied_evidence"]
    assert not candidate["supplied_evidence_bindings"]


def test_decimal_comparison_is_numeric_not_string_order():
    result = run("αLi = 9.9. αLi = 10.", claim="αLi = 9.9.")
    assert [r["value"] for r in check(result)["larger_same_form_numeric_review_candidates"]] == ["10"]


def test_percentage_does_not_become_dimensionless_alpha():
    result = run("αLi = 1.54. αLi = 180%.")
    assert not check(result)["larger_same_form_numeric_review_candidates"]
    assert any(c["unit"] == "percent_unmodeled" for c in result["source_candidates"])


@pytest.mark.parametrize("text", ["αLi = 1.5–1.8", "αLi = 1.5 to 1.8", "1.5–1.8 for Li-form",
                                "1.5 to 1.8 for Li-form", "αLi > 1.54"])
def test_unsupported_range_and_bound_syntax_not_read_as_scalar(text):
    assert not numeric_relations(text)


def test_regression_and_observation_cues_remain_separate_unverified_proposals():
    result = run("Regression αLi = 1.54 agrees with experimentally observed αLi = 1.536.")
    first, second = result["source_candidates"]
    assert first["nearest_preceding_basis_cue_unverified"]["kind"] == "regression"
    assert second["nearest_preceding_basis_cue_unverified"]["kind"] == "experiment"
    assert all("mixed_regression_experiment_cues_unresolved" in c["diagnostics"] for c in (first, second))


def test_negated_source_value_is_not_accepted():
    result = run("Swelling was not αLi = 1.54 at 25°C.")
    assert "negation_reference_or_coordination_unresolved" in result["source_candidates"][0]["diagnostics"]
    assert result["scientific_coverage"] == "unresolved"


def test_mixture_and_individual_scope_cues_not_resolved_by_cooccurrence():
    result = run("For pure solvents and mixtures αLi = 1.54.")
    assert "multiple_medium_scopes_unresolved" in result["source_candidates"][0]["diagnostics"]


def test_requested_individual_solvents_not_equated_with_mixture_cue():
    result = run("For mixtures αLi = 1.54.", question="Maximum swelling of Li-Nafion among pure solvents?")
    assert "different_medium_type_cues_unresolved" in check(result)["medium_scope_check"]["diagnostics"]


def test_tabular_values_are_explicitly_unparsed_not_silently_treated_as_absent():
    result = run("Table 1: solvent\nαLi\n1.54", claim="αLi = 1.54.")
    assert result["source_context_inventory"][0]["layout_diagnostics"] == ["table_column_value_extraction_not_implemented"]
    assert check(result)["numeric_surface_status"] == "not_detected_in_cited_evidence"


def test_alpha_inside_an_unrelated_identifier_not_parsed():
    assert not numeric_relations("myalphaLi = 1.54")


def test_missing_page_from_evidence_extent_rejected():
    with pytest.raises(ValueError, match="missing registered pages"):
        audit(QUESTION, [{"text": "αLi = 1.54", "citation_ids": ["E1"]}],
              [evidence("αLi = 1.54", page_end=2)], [page("αLi = 1.54")])


def test_conflicting_pdf_identity_for_same_article_rejected():
    with pytest.raises(ValueError, match="Conflicting original PDF"):
        run("αLi = 1.54", extra_pages=[replace(page("αLi = 1.8"), page_number=2, original_pdf_sha256="b" * 64)])


def test_unrelated_work_citation_cannot_support_numeric_surface():
    pages = [page("αLi = 1.54."), replace(page("αLi = 1.8."), article_id="other-work")]
    result = audit(QUESTION, [{"text": "αLi = 1.8.", "citation_ids": ["E1"]}],
                   [evidence("αLi = 1.54."), evidence("αLi = 1.8.", citation_id="E2", article_id="other-work")], pages)
    assert check(result)["numeric_surface_status"] == "not_detected_in_cited_evidence"


def test_dehyphenation_preserves_raw_source_anchor_offsets():
    raw = "Набу-\nхание alpha_\nLi = 1,54 при 25 °С."
    result = run(raw)
    for c in result["source_candidates"]:
        for key in ("relation", "number", "form_anchor", "statement"):
            span = c[key]
            assert raw[span["start"]:span["end"]] == span["text"]
    assert result["source_candidates"]


@pytest.mark.parametrize("bad", [{"original_pdf_sha256": "not-a-hash"}, {"page_number": 0},
                                 {"article_id": ""}, {"origin": "model_guess"}, {"page_number": True}, {"text_layer": "ocr"}])
def test_invalid_source_identity_rejected(bad):
    with pytest.raises(ValueError, match="identity/provenance"):
        audit(QUESTION, [{"text": "αLi = 1.54", "citation_ids": ["E1"]}], [evidence("αLi = 1.54")],
              [replace(page("αLi = 1.54"), **bad)])


@pytest.mark.parametrize("mode", ["duplicate_pages", "duplicate_citations", "unknown_citation", "empty_claims", "missing_registry"])
def test_invalid_audit_inputs_fail_explicitly(mode):
    p, e = page("αLi = 1.54"), evidence("αLi = 1.54")
    pages, supplied, claims = [p], [e], [{"text": "αLi = 1.54", "citation_ids": ["E1"]}]
    if mode == "duplicate_pages":
        pages.append(p)
    elif mode == "duplicate_citations":
        supplied.append(e)
    elif mode == "unknown_citation":
        claims[0]["citation_ids"] = ["E2"]
    elif mode == "empty_claims":
        claims = []
    else:
        pages = []
    with pytest.raises(ValueError):
        audit(QUESTION, claims, supplied, pages)
