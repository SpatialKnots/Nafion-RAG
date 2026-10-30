"""Exposed constructed dependencies; no independent scientific accuracy claim."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.experiment_sentence_links import attach_dependencies, dependencies
from scripts.requested_context_links import SourceEvidence, SourcePage, audit_links

CASES = json.loads((Path(__file__).resolve().parents[2] / "docs/records/experiment_sentence_links_cases_v0.1.json").read_bytes())


def packet(text):
    return (SourceEvidence("E1", "constructed", "chunk", text, 1, 1, "original"),
            SourcePage("constructed", 1, "original", "layer", "synthetic.pdf", "a" * 64, "HEADER\n" + text))


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["id"])
def test_declared_positive_and_adversarial_dependency_expectations(case):
    e, p = packet(case["text"])
    graph = dependencies(e, [p])
    proposals = [a for a in graph["attempts"] if a["state"] == "dependency_proposal_unverified"]
    assert len(proposals) == case["expected_links"]
    for attempt in graph["attempts"]:
        span = attempt["bridge_span"]
        assert e.text[span["start"]:span["end"]] == span["text"]
        assert attempt["values_and_conditions_propagated"] is False
    for node in graph["nodes"]:
        span = node["span"]
        assert e.text[span["start"]:span["end"]] == span["text"]
        for anchor in node["page_anchors"]:
            assert p.text[anchor["start"]:anchor["end"]] == anchor["text"]
    assert graph["scientific_relation"] == "not_evaluated"


@pytest.mark.parametrize("change", [{"article_id": "other"}, {"text_layer": "ocr"},
                                   {"text": "different quote"}, {"text": CASES["cases"][0]["text"] * 2}])
def test_links_require_unique_registered_parent_and_child_anchors(change):
    e, p = packet(CASES["cases"][0]["text"])
    graph = dependencies(e, [replace(p, **change)])
    assert not any(a["state"] == "dependency_proposal_unverified" for a in graph["attempts"])


def test_sentence_and_semicolon_clause_links_are_distinguished():
    for case_id, separator in [("instrument_spectra", "semicolon_clauses"), ("instrument_spectra_period", "sentence_units")]:
        case = next(c for c in CASES["cases"] if c["id"] == case_id)
        e, p = packet(case["text"])
        assert dependencies(e, [p])["attempts"][0]["separator_kind"] == separator


def test_sidecar_does_not_upgrade_baseline_or_infer_an_exact_time_from_criterion():
    case = next(c for c in CASES["cases"] if c["id"] == "instrument_spectra")
    e, p = packet(case["text"])
    baseline = audit_links("Какова точная длительность перед измерением проводимости?", [], [e], [p])
    saved = copy.deepcopy(baseline)
    sidecar = attach_dependencies(baseline, [e], [p])
    assert baseline == saved and sidecar["baseline_modified"] is False
    assert baseline["source_candidates"][0]["kind"] == "equilibrium_criterion"
    assert "different_requested_quantity" in baseline["source_candidates"][0]["diagnostics"]
    assert sidecar["candidate_dependencies"][0]["coverage_upgrade"] is False


def test_chunks_and_articles_are_not_joined_even_with_identical_labels():
    parent, _ = packet("Conductivity of sample A was measured by impedance spectroscopy.")
    child, child_page = packet("Before this measurement, sample A was held for 15 min.")
    child = replace(child, article_id="other", citation_id="E2", chunk_id="other")
    child_page = replace(child_page, article_id="other")
    assert dependencies(parent, [])["attempts"] == []
    assert dependencies(child, [child_page])["attempts"] == []


def test_unknown_sample_identity_is_visible_and_never_inherited():
    e, p = packet("Conductivity was measured by impedance spectroscopy. Before this measurement, it was held for 15 min.")
    attempt, = dependencies(e, [p])["attempts"]
    assert attempt["sample_identity"] == "not_established"
    assert attempt["values_and_conditions_propagated"] is False


@pytest.mark.parametrize(("text", "reason"), [
    ("Conductivity measurements of sample A are discussed. Before this measurement, sample A was held for 15 min.",
     "parent_measurement_assertion_unresolved"),
    ("Before this conductivity measurement, sample A was held for 15 min. Before this measurement, it was held again.",
     "referential_parent_not_new_operation"),
    ("If conductivity of sample A was measured by impedance spectroscopy. Before this measurement, it was held for 15 min.",
     "conditional_context_unresolved"),
])
def test_mentions_references_and_conditions_do_not_become_asserted_parent_operations(text, reason):
    e, p = packet(text)
    graph = dependencies(e, [p])
    assert not any(a["state"] == "dependency_proposal_unverified" for a in graph["attempts"])
    assert reason in graph["attempts"][0]["diagnostics"]
