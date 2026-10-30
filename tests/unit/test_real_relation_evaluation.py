"""Constructed scoring controls; real source labels are preliminary, not gold."""

import copy

import pytest

from scripts.real_relation_evaluation import compare_relations, summarize


def inputs():
    text = "Parent. Child. Other."
    nodes = [{"id": i, "span": {"start": start, "end": end, "text": text[start:end]}}
             for i, (start, end) in enumerate([(0, 8), (8, 15), (15, 21)])]
    # The final span is corrected to actual length; source offsets stay literal.
    nodes[-1]["span"] = {"start": 15, "end": len(text), "text": text[15:]}
    reference = {"id": "r1", "parent": {"start": 0, "end": 6, "text": "Parent"},
                 "child": {"start": 8, "end": 13, "text": "Child"}, "relation_type": "measurement_context"}
    annotation = {"required_dependencies": [reference], "forbidden_measurement_context_dependencies": []}
    graph = {"nodes": nodes, "attempts": [{"parent": 0, "child": 1, "state": "dependency_proposal_unverified"}]}
    return text, annotation, graph


def test_match_missing_and_forbidden_are_separate_states():
    text, a, g = inputs()
    assert summarize([compare_relations(text, a, g)])["matched_preliminary_references"] == 1
    g["attempts"] = []
    assert summarize([compare_relations(text, a, g)])["missed_preliminary_references"] == 1
    a["forbidden_measurement_context_dependencies"] = a.pop("required_dependencies")
    a["required_dependencies"] = []
    g["attempts"] = [{"parent": 0, "child": 1, "state": "dependency_proposal_unverified"}]
    assert summarize([compare_relations(text, a, g)])["forbidden_context_violations"] == 1


def test_unannotated_proposals_are_not_false_positives():
    text, a, g = inputs()
    g["attempts"].append({"parent": 1, "child": 2, "state": "dependency_proposal_unverified"})
    result = compare_relations(text, a, g)
    assert result["unannotated_proposal_ids"] == [1]
    assert summarize([result])["forbidden_context_violations"] == 0


def test_unaligned_reference_is_not_an_ordinary_miss():
    text, a, g = inputs()
    a["required_dependencies"][0]["child"] = {"start": 5, "end": 10, "text": text[5:10]}
    summary = summarize([compare_relations(text, a, g)])
    assert summary["unmappable_required_references"] == 1 and summary["missed_preliminary_references"] == 0


def test_sparse_comparison_does_not_modify_inputs_or_claim_answer_accuracy():
    text, a, g = inputs()
    saved = copy.deepcopy((a, g))
    result = compare_relations(text, a, g)
    assert (a, g) == saved and result["independent_accuracy"] is None
    assert result["scientific_answer_evaluation"] == "not_performed"


@pytest.mark.parametrize("bad", ["node_text", "anchor_text", "edge_direction", "node_ids"])
def test_invalid_spans_and_direction_fail_loudly(bad):
    text, a, g = inputs()
    if bad == "node_text":
        g["nodes"][0]["span"]["text"] = "Changed"
    elif bad == "anchor_text":
        a["required_dependencies"][0]["child"]["text"] = "Changed"
    elif bad == "edge_direction":
        g["attempts"][0].update(parent=1, child=0)
    else:
        g["nodes"][1]["id"] = 100
    with pytest.raises(ValueError):
        compare_relations(text, a, g)
