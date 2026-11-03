from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import component_context_relations as v3
from scripts import typed_partial_relations as v2
from scripts.verify_typed_partial_relation_review import check_graph

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "docs/records/component_context_controls_v0.3.json").read_bytes())
OLD = json.loads((ROOT / "docs/records/typed_partial_controls_v0.2.json").read_bytes())
REAL = json.loads((ROOT / "docs/records/typed_partial_real_cases_v0.2.json").read_bytes())


@pytest.mark.parametrize("control", DATA["controls"], ids=lambda row: row["id"])
def test_new_controls(control):
    sources = [{"text": t, "title": control.get("title")} for t in control.get("texts", [control.get("text", "")])]
    original = copy.deepcopy(sources)
    result = v3.audit(control.get("question", DATA["question"]), sources, baseline_adequate=True)
    assert bool(result["partial_relations"]) == control["partial"]
    assert result["textual_requirements_met"] == control["complete"]
    assert sources == original
    assert not result["scientific_admission"]
    check_graph(result, sources)
    edges = [edge for source in result["typed_sources"] for unit in source["units"] for edge in unit["edges"]]
    accepted = [b for e in edges for b in e["context_bindings"]]
    if "binding" in control:
        assert {b["kind"] for b in accepted} == ({control["binding"]} if control["binding"] else set())
    if "status" in control:
        assert {e["status"] for e in edges if e["partial_relation"]} == {control["status"]}
    for source in result["typed_sources"]:
        raw = sources[source["evidence_index"]]["text"]
        for unit in source["units"]:
            for node in unit["variables"]:
                for binding in [*node["source_context"]["accepted"], *node["source_context"]["rejected"]]:
                    for key in ("span", "pair_span", "sentence_span", "target_dispersion_span"):
                        span = binding[key]
                        if span:
                            assert raw[span["start"]:span["end"]] == span["text"]


@pytest.mark.parametrize("control", OLD["controls"], ids=lambda row: row["id"])
def test_v2_controls_preserved(control):
    result = v3.audit(
        control.get("question", OLD["question"]),
        [{"text": t} for t in control.get("texts", [control.get("text", "")])], baseline_adequate=False,
    )
    assert bool(result["partial_relations"]) == control["partial"]
    assert result["textual_requirements_met"] == control["complete"]


@pytest.mark.parametrize("case", REAL["cases"], ids=lambda row: row["id"])
def test_real_windows_preserved(case):
    sources = [{"text": case["raw_span"]["text"]}]
    result = v3.audit(DATA["question"], sources, baseline_adequate=False)
    assert bool(result["partial_relations"]) == case["annotation"]["partial_relation"]
    assert result["textual_requirements_met"] is False
    check_graph(result, sources)


@pytest.mark.parametrize("baseline", [True, False])
def test_outside_scope_and_previous_analyzer_unchanged(baseline):
    sources = [{"text": "alpha and beta were used as solvents for Nafion dispersions."}]
    before = v2.audit(DATA["question"], sources, baseline_adequate=baseline)
    result = v3.audit("Nafion swelling", sources, baseline_adequate=baseline)
    assert result["baseline_adequate"] is baseline
    assert result["textual_requirements_met"] is None
    assert result["partial_relations"] == []
    assert v2.audit(DATA["question"], sources, baseline_adequate=baseline) == before
