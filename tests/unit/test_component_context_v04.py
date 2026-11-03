import json
from pathlib import Path

import pytest

from scripts import component_context_relations as v3
from scripts import component_context_relations_v04 as v4
from scripts.run_component_context_review_v04 import controls
from scripts.verify_component_context_review_v04 import check_context_graph

DATA = json.loads((Path(__file__).resolve().parents[2] / "docs/records/component_context_controls_v0.4.json").read_bytes())


@pytest.mark.parametrize("control", DATA["controls"], ids=lambda c: c["id"])
def test_exposed_adverse_variants(control):
    sources = [{"text": control["text"]}]
    result = v4.audit(DATA["question"], sources, baseline_adequate=False)
    assert bool(result["partial_relations"]) == control["partial"]
    assert result["textual_requirements_met"] == control["complete"]
    check_context_graph(DATA["question"], result, sources)


def test_all_prior_controls_retained_without_rewriting_v3_failures():
    result = controls()
    assert result["old_complete_losses"] == {"v2": ["observed_nominal_null"], "v4": []}
    assert len(result["records"]) == 145  #139 constructed plus6 frozen real windows
    for control in DATA["controls"][:2]:
        sources = [{"text": control["text"]}]
        before = v3.audit(DATA["question"], sources, baseline_adequate=False)
        assert before["textual_requirements_met"] is True
        assert v4.audit(DATA["question"], sources, baseline_adequate=False)["textual_requirements_met"] is False
        assert v3.audit(DATA["question"], sources, baseline_adequate=False) == before
