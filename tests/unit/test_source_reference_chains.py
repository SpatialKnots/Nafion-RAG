import copy
import json
from pathlib import Path

import pytest

from scripts import component_context_relations_v04 as v4
from scripts import source_reference_chains as v5
from scripts.verify_source_reference_review import base_result, check_chains

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "docs/records/source_reference_controls_v0.5.json").read_bytes())
REAL = json.loads((ROOT / "docs/records/source_reference_cases_v0.5.json").read_bytes())


@pytest.mark.parametrize("control", DATA["controls"], ids=lambda c: c["id"])
def test_declared_controls(control):
    sources = [{"text": t, "title": control.get("title")} for t in control.get("texts", [control.get("text", "")])]
    question = control.get("question", DATA["question"])
    before = copy.deepcopy(sources)
    result = v5.audit(question, sources, baseline_adequate=True)
    assert bool(result["source_chains"]) == control["binding"]
    assert result["chain_textual_requirements_met"] == control["complete"]
    assert sources == before
    assert base_result(result) == v4.audit(question, sources, baseline_adequate=True)
    check_chains(question, result, sources)
    if "unique_paths" in control:
        assert len(result["exact_chain_groups"]) == control["unique_paths"]
        assert len(result["source_chains"]) == 2
    if "pair" in control:
        assert {p["declaration"]["pair_span"]["text"] for s in result["chain_sources"] for p in s["paths"]} == {control["pair"]}


@pytest.mark.parametrize("case", REAL["context_cases"], ids=lambda c: c["id"])
def test_frozen_real_contexts(case):
    sources = [{"text": case["raw_span"]["text"]}]
    result = v5.audit(DATA["question"], sources, baseline_adequate=False)
    assert bool(result["source_chains"]) == case["annotation"]["binding"]
    assert result["chain_textual_requirements_met"] is False
    if case["annotation"]["binding"]:
        path = result["chain_sources"][0]["paths"][0]
        assert path["relation_kind"] == "context_association"
        assert "particle_property_attachment_unresolved" in path["missing_roles"]
    check_chains(DATA["question"], result, sources)


@pytest.mark.parametrize("case", REAL["old_cases"], ids=lambda c: c["id"])
def test_original_windows_have_no_fabricated_context(case):
    sources = [{"text": case["raw_span"]["text"]}]
    result = v5.audit(DATA["question"], sources, baseline_adequate=False)
    assert result["source_chains"] == []
    assert not result["chain_textual_requirements_met"]


@pytest.mark.parametrize("baseline", [True, False])
def test_outside_scope_preserved(baseline):
    result = v5.audit("Nafion swelling", [{"text": DATA["controls"][0]["text"]}], baseline_adequate=baseline)
    assert result["baseline_adequate"] is baseline
    assert result["chain_textual_requirements_met"] is None
    assert result["source_chains"] == []


def sample():
    sources = [{"text": DATA["controls"][0]["text"]}]
    return v5.audit(DATA["question"], sources, baseline_adequate=False), sources


def test_corrupt_hop_anchor_rejected():
    result, sources = sample()
    result["chain_sources"][0]["paths"][0]["hops"][0]["reference_span"]["text"] = "invented"
    with pytest.raises(ValueError, match="Raw span differs"):
        check_chains(DATA["question"], result, sources)


def test_invented_owner_rejected():
    result, sources = sample()
    result["chain_sources"][0]["paths"][0]["value_owner_established"] = True
    with pytest.raises(ValueError, match="invented scientific owner"):
        check_chains(DATA["question"], result, sources)


def test_context_association_cannot_silently_become_complete():
    control = next(c for c in DATA["controls"] if c["id"] == "association_only")
    sources = [{"text": control["text"]}]
    result = v5.audit(DATA["question"], sources, baseline_adequate=False)
    result["chain_textual_requirements_met"] = True
    with pytest.raises(ValueError, match="Exact reference-chain replay differs"):
        check_chains(DATA["question"], result, sources)
