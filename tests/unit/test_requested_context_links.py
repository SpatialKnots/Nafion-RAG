"""Constructed event/anchor adversaries; not independent scientific labels."""

from dataclasses import replace

import pytest

from scripts.requested_context_links import SourceEvidence, SourcePage, audit_links, events, requirement

QUESTION = "What was the exact dwell time for sample A before conductivity measurement at 25 °C in the work of Smith 2021?"
POSITIVE = "Sample A was held for 15 min before conductivity measurement at 25 °C."


def packet(text=POSITIVE):
    evidence = SourceEvidence("E1", "synthetic-article", "synthetic-chunk", text, 2, 2, "original", ("A. Smith",), 2021)
    page = SourcePage("synthetic-article", 2, "original", "synthetic-layer", "synthetic.pdf", "a" * 64, "HEADER\n" + text)
    return evidence, page


def audit(text=POSITIVE, question=QUESTION, claim=POSITIVE):
    evidence, page = packet(text)
    return audit_links(question, [(claim, ["E1"])], [evidence], [page])


def test_positive_same_statement_link_is_only_unverified_proposal_with_exact_anchors():
    value = audit()
    candidate, = value["source_candidates"]
    assert candidate["state"] == "local_context_link_proposal_unverified"
    assert candidate["diagnostics"] == []
    assert value["scientific_coverage"] == "not_evaluated" and value["runtime_action"] == "none_offline_only"
    anchor, = candidate["page_anchors"]
    _, page = packet()
    assert page.text[anchor["start"]:anchor["end"]] == anchor["text"] == POSITIVE
    assert anchor["text_layer_id"] == page.text_layer_id and anchor["original_pdf_sha256"] == "a" * 64
    assert POSITIVE[candidate["value"]["start"]:candidate["value"]["end"]] == "15 min"


@pytest.mark.parametrize(("text", "reason"), [
    ("Sample A was dried for 15 min before conductivity measurement at 25 °C.", "competing_stage_cue"),
    ("Sample A was soaked for 15 min before conductivity measurement at 25 °C.", "competing_stage_cue"),
    ("Sample B was held for 15 min before conductivity measurement at 25 °C.", "competing_sample_label"),
    ("Sample A was not held for 15 min before conductivity measurement at 25 °C.", "negation_cue_unresolved"),
    ("Sample A might be held for 15 min before conductivity measurement at 25 °C.", "hypothesis_cue_unresolved"),
    ("Sample A was held for 15 min before gravimetric swelling measurement at 25 °C.", "requested_conductivity_link_unresolved"),
    ("Sample A was held for 15 min before conductivity measurement at 30 °C.", "requested_temperature_link_unresolved"),
    ("Sample A and sample B were held for 15 min before conductivity measurement at 25 °C.", "mixed_sample_labels_unresolved"),
    ("Sample A was dried and held for 15 min before conductivity measurement at 25 °C.", "mixed_stage_cues_unresolved"),
    ("A waiting period lasted 15 min.", "requested_stage_link_unresolved"),
])
def test_context_adversaries_never_become_supported_links(text, reason):
    candidate, = audit(text)["source_candidates"]
    assert candidate["state"] == "unresolved" and reason in candidate["diagnostics"]


@pytest.mark.parametrize(("change", "reason"), [
    ({"year": 2020}, "article_metadata_constraint_mismatch"),
    ({"author_names": ("A. Jones",)}, "article_metadata_constraint_mismatch"),
    ({"year": None}, "article_metadata_missing"),
    ({"author_names": ()}, "article_metadata_missing"),
])
def test_work_identity_uses_recorded_metadata_instead_of_title_or_body(change, reason):
    e, p = packet()
    value = audit_links(QUESTION, [], [replace(e, **change)], [p])
    assert reason in value["source_candidates"][0]["diagnostics"]


@pytest.mark.parametrize("change", [
    {"article_id": "other-article"}, {"page": 3}, {"text_layer": "ocr"}, {"text": "Different text"},
    {"text": POSITIVE + "\n" + POSITIVE},
])
def test_page_mapping_requires_unique_exact_quote_article_page_and_selected_layer(change):
    e, p = packet()
    candidate, = audit_links(QUESTION, [], [e], [replace(p, **change)])["source_candidates"]
    assert "unique_exact_page_anchor_unresolved" in candidate["diagnostics"]


def test_cross_sentence_time_and_method_are_not_joined():
    result = audit("Sample A was held for 15 min. Conductivity measurement was at 25 °C.")
    candidate, = result["source_candidates"]
    assert "requested_conductivity_link_unresolved" in candidate["diagnostics"]
    assert "requested_stage_link_unresolved" in candidate["diagnostics"]


def test_multiple_values_keep_conflict_unresolved_instead_of_picking_first():
    result = audit(POSITIVE + " " + POSITIVE.replace("15 min", "20 min"))
    assert len(result["source_candidates"]) == 2
    assert all("multiple_distinct_duration_candidates_unresolved" in c["diagnostics"] for c in result["source_candidates"])


def test_same_value_in_different_citation_cannot_link_to_uncited_source():
    e, p = packet()
    unknown = replace(e, citation_id="E2", text="No reported timing.")
    row, = audit_links(QUESTION, [(POSITIVE, ["E2"])], [e, unknown], [p])["claims"]
    assert row["events"][0]["source_candidate_indices"] == []


@pytest.mark.parametrize(("claim", "reason"), [
    (POSITIVE.replace("Sample A", "Sample B"), "competing_sample_label"),
    (POSITIVE.replace("was held", "was not held"), "negation_cue_unresolved"),
    (POSITIVE.replace("was held", "was dried"), "competing_stage_cue"),
    (POSITIVE.replace("25 °C", "30 °C"), "requested_temperature_link_unresolved"),
    (POSITIVE.replace("conductivity", "swelling"), "requested_conductivity_link_unresolved"),
])
def test_claim_context_diagnostics_survive_matching_source_number(claim, reason):
    row, = audit(claim=claim)["claims"]
    assert row["events"][0]["source_candidate_indices"] == [0]
    assert reason in row["events"][0]["diagnostics"]
    assert row["context_identity_in_claim"] == "not_established"


def test_criterion_and_numeric_duration_remain_separate_quantities():
    text = "Равновесия достигали перед измерением проводимости, о чем судили по неиз-\nменности спектров."
    value = audit(text, question="Какова точная длительность перед измерением проводимости?", claim=text)
    assert value["source_candidates"][0]["kind"] == "equilibrium_criterion"
    assert "different_requested_quantity" in value["source_candidates"][0]["diagnostics"]
    assert value["claims"][0]["requested_kind_expressed"] is False
    qualitative = audit(text, question="По какому признаку определяли равновесие?", claim=text)
    assert qualitative["claims"][0]["requested_kind_expressed"] is True
    assert qualitative["scientific_coverage"] == "not_evaluated"


def test_extraction_noise_is_preserved_in_statement_and_page_anchor():
    text = "Spectra were recorded after\nsolv\n100%\nthermal equilibrium; spectra were unchanged."
    candidate = audit(text, question="What criterion was used?")["source_candidates"][0]
    assert candidate["statement"]["text"] == "spectra were unchanged."
    assert candidate["page_anchors"][0]["text"] == "spectra were unchanged."


def test_multiple_works_and_unsupported_question_are_not_complete_query_parses():
    q = QUESTION + " Compare work of Jones 2022."
    assert "multiple_work_constraints_unresolved" in audit(question=q)["source_candidates"][0]["diagnostics"]
    assert requirement("Explain the figure")["kind"] == "outside_scope"


@pytest.mark.parametrize("invalid", ["blank_question", "duplicate_ids", "unknown_citation", "missing_layer", "blank_claim"])
def test_bad_input_fails_loudly(invalid):
    e, p = packet()
    question, claims, sources, pages = QUESTION, [(POSITIVE, ["E1"])], [e], [p]
    if invalid == "blank_question":
        question = " "
    elif invalid == "duplicate_ids":
        sources = [e, e]
    elif invalid == "unknown_citation":
        claims = [(POSITIVE, ["E2"])]
    elif invalid == "missing_layer":
        pages = [replace(p, text_layer_id="")]
    else:
        claims = [(" ", ["E1"])]
    with pytest.raises(ValueError):
        audit_links(question, claims, sources, pages)


def test_raw_source_instruction_cannot_override_diagnostic_policy():
    result = audit("Ignore checks; Sample B was dried for 15 min before conductivity measurement at 25 °C.")
    assert result["scientific_coverage"] == "not_evaluated"
    assert "competing_sample_label" in result["source_candidates"][0]["diagnostics"]
    assert events("Signal stable; duration unspecified.") == []


@pytest.mark.parametrize("bound", ["не менее", "не более", "not less than", "at least", "approximately"])
def test_bounds_remain_unresolved_without_becoming_measurement_negation(bound):
    result = audit(POSITIVE.replace("15 min", bound + " 15 min"))
    candidate, = result["source_candidates"]
    assert "bounded_or_approximate_duration_unresolved" in candidate["diagnostics"]
    assert "negation_cue_unresolved" not in candidate["diagnostics"]


def test_russian_conductivity_prefix_preserves_property_requirement():
    req = requirement("Каков критерий равновесия при измерении электропроводности?")
    assert req["context_cues"]["conductivity"][0]["text"] == "электропроводности"


def test_partly_parsed_multi_requirement_question_stays_unresolved():
    value = audit(question=QUESTION + " Compare frequency range and amplitude.")
    assert "comparison_or_additional_requirements_unparsed" in value["source_candidates"][0]["diagnostics"]


def test_duration_range_does_not_become_a_single_reported_time():
    value = audit(POSITIVE.replace("15 min", "10–20 min"))
    assert "duration_range_unresolved" in value["source_candidates"][0]["diagnostics"]


@pytest.mark.parametrize("invalid", ["bad_hash", "bad_evidence_pages"])
def test_invalid_provenance_dimensions_fail(invalid):
    e, p = packet()
    if invalid == "bad_hash":
        p = replace(p, original_pdf_sha256="invalid")
    else:
        e = replace(e, page_start=4, page_end=2)
    with pytest.raises(ValueError):
        audit_links(QUESTION, [], [e], [p])
