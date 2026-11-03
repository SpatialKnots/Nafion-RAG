import copy
import json
from pathlib import Path

import pytest

from scripts import particle_attachment_audit as v7
from scripts import source_reference_chains_v06 as v6
from scripts.verify_particle_attachment_review import base_result, check_atoms

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "docs/records/particle_attachment_controls_v0.7.json").read_bytes())
REAL = json.loads((ROOT / "docs/records/particle_attachment_cases_v0.7.json").read_bytes())


@pytest.mark.parametrize("case", DATA["controls"], ids=lambda c: c["id"])
def test_constructed_controls(case):
    question = case.get("question", DATA["question"])
    sources = [{"text": t, "title": case.get("title")} for t in case.get("texts", [case.get("text", "")])]
    before = copy.deepcopy(sources)
    result = v7.audit(question, sources, baseline_adequate=True)
    assert bool(result["particle_relations"]) == case["eligible"]
    assert result["particle_requirements_met"] == case["complete"]
    assert sources == before
    assert base_result(result) == v6.audit(question, sources, baseline_adequate=True)
    check_atoms(question, result, sources)
    if "unique" in case:
        assert len(result["exact_particle_groups"]) == case["unique"]
        assert len(result["particle_relations"]) == 2


@pytest.mark.parametrize("case", REAL["cases"], ids=lambda c: c["id"])
def test_frozen_real_role_annotations(case):
    sources = [{"text": case["raw_span"]["text"]}]
    result = v7.audit(DATA["question"], sources, baseline_adequate=False)
    units = [u for source in result["atomic_sources"] for u in source["units"]]
    assert any(u["particle_owners"] for u in units) == case["annotation"]["particle_owner"]
    assert any(m["kind"] == "explicit_dispersion" for u in units for m in u["medium_attachments"]) == case["annotation"]["dispersion"]
    assert result["particle_requirements_met"] is False
    check_atoms(DATA["question"], result, sources)


@pytest.mark.parametrize("baseline", [True, False])
def test_outside_scope_preserves_decision(baseline):
    result = v7.audit("Nafion swelling", [{"text": DATA["controls"][0]["text"]}], baseline_adequate=baseline)
    assert result["baseline_adequate"] is baseline
    assert result["particle_requirements_met"] is None
    assert result["particle_relations"] == []


def sample():
    sources = [{"text": DATA["controls"][0]["text"]}]
    return v7.audit(DATA["question"], sources, baseline_adequate=False), sources


def test_corrupt_owner_anchor_rejected():
    result, sources = sample()
    result["atomic_sources"][0]["units"][0]["particle_owners"][0]["text"] = "invented"
    with pytest.raises(ValueError, match="Raw span differs"):
        check_atoms(DATA["question"], result, sources)


def test_invented_quantitative_owner_rejected():
    result, sources = sample()
    result["atomic_sources"][0]["units"][0]["value_owner_established"] = True
    with pytest.raises(ValueError, match="invented a scientific owner"):
        check_atoms(DATA["question"], result, sources)


def test_shape_description_cannot_become_requested_dependency():
    case = next(c for c in DATA["controls"] if c["id"] == "reported_shape")
    sources = [{"text": case["text"]}]
    result = v7.audit(DATA["question"], sources, baseline_adequate=False)
    result["particle_requirements_met"] = True
    with pytest.raises(ValueError, match="Exact atomic replay differs"):
        check_atoms(DATA["question"], result, sources)
