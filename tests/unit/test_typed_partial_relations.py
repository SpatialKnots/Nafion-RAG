from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import cross_lingual_relation_audit as v1
from scripts.typed_partial_relations import audit, segmentation_only

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = json.loads((ROOT / "docs/records/typed_partial_controls_v0.2.json").read_bytes())
REAL = json.loads((ROOT / "docs/records/typed_partial_real_cases_v0.2.json").read_bytes())


@pytest.mark.parametrize("control", CONTROLS["controls"], ids=lambda row: row["id"])
def test_constructed_controls(control):
    sources = [{"text": text, "title": control.get("title")} for text in control.get("texts", [control.get("text", "")])]
    original = copy.deepcopy(sources)
    result = audit(control.get("question", CONTROLS["question"]), sources, baseline_adequate=True)
    assert bool(result["partial_relations"]) == control["partial"]
    assert result["textual_requirements_met"] == control["complete"]
    assert not result["scientific_admission"]
    assert sources == original
    nodes = [node for source in result["typed_sources"] for unit in source["units"] for node in unit["variables"]]
    if "kind" in control:
        assert control["kind"] in {node["kind"] for node in nodes}
    if "unique_relations" in control:
        assert len(result["exact_relation_groups"]) == control["unique_relations"]
        assert len(result["partial_relations"]) == 2
    for source in result["typed_sources"]:
        text = sources[source["evidence_index"]]["text"]
        for unit in source["units"]:
            spans = [unit["span"], *[node["span"] for node in unit["variables"]]]
            spans.extend(component["span"] for node in unit["variables"] for component in node["components"])
            spans.extend(edge["predicate_span"] for edge in unit["edges"])
            for span in spans:
                assert text[span["start"] : span["end"]] == span["text"]


@pytest.mark.parametrize("case", REAL["cases"], ids=lambda row: row["id"])
def test_frozen_real_excerpts(case):
    result = audit(CONTROLS["question"], [{"text": case["raw_span"]["text"]}], baseline_adequate=False)
    assert bool(result["partial_relations"]) == case["annotation"]["partial_relation"]
    assert result["textual_requirements_met"] is False
    assert case["parent_text"][case["raw_span"]["start"] : case["raw_span"]["end"]] == case["raw_span"]["text"]


def test_serial_adapter_restores_original_region_function():
    original = v1._regions
    segmentation_only(CONTROLS["question"], [{"text": CONTROLS["controls"][0]["text"]}], baseline_adequate=False)
    assert v1._regions is original
    audit(CONTROLS["question"], [{"text": CONTROLS["controls"][0]["text"]}], baseline_adequate=False)
    assert v1._regions is original


@pytest.mark.parametrize("baseline", [True, False])
def test_outside_scope_preserves_baseline(baseline):
    result = audit("Nafion swelling", [{"text": "unrelated"}], baseline_adequate=baseline)
    assert result["baseline_adequate"] is baseline
    assert result["textual_requirements_met"] is None
    assert result["partial_relations"] == []


def test_component_names_are_not_a_solvent_catalogue():
    one = audit(
        CONTROLS["question"],
        [{"text": "Nafion particle morphology depends on the unfamiliarX/unfamiliarY ratio."}],
        baseline_adequate=False,
    )
    assert one["partial_relations"][0]["query_variable_scope"] == "component_ratio_solvent_scope_unresolved"
    assert not one["textual_requirements_met"]
