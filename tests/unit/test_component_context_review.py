import copy
import json
from pathlib import Path

import pytest

from scripts import component_context_relations as v3
from scripts.run_component_context_review import controls
from scripts.verify_component_context_review import check_context_graph

DATA = json.loads((Path(__file__).resolve().parents[2] / "docs/records/component_context_controls_v0.3.json").read_bytes())


def sample():
    sources = [{"text": DATA["controls"][0]["text"]}]
    return v3.audit(DATA["question"], sources, baseline_adequate=False), sources


def test_original_nominal_null_loss_restored_and_prior_controls_retained():
    result = controls()
    assert result["old_complete_losses"] == {"v2": ["observed_nominal_null"], "v3": []}
    assert len(result["real_parent_records"]) == 6


def test_context_pair_raw_corruption_rejected():
    result, sources = sample()
    assert check_context_graph(DATA["question"], result, sources)["context_spans"] > 0
    node = result["typed_sources"][0]["units"][0]["variables"][0]
    node["source_context"]["accepted"][0]["pair_span"]["text"] = "invented"
    with pytest.raises(ValueError, match="Raw span differs"):
        check_context_graph(DATA["question"], result, sources)


def test_invented_context_owner_rejected():
    result, sources = sample()
    result["typed_sources"][0]["units"][0]["variables"][0]["source_context"]["accepted"][0]["value_owner_established"] = True
    with pytest.raises(ValueError, match="invented identity or quantitative owner"):
        check_context_graph(DATA["question"], result, sources)


def test_structurally_valid_false_context_kind_rejected():
    result, sources = sample()
    result["typed_sources"][0]["units"][0]["variables"][0]["source_context"]["accepted"][0]["kind"] = "invented"
    with pytest.raises(ValueError, match="exact diagnostic replay"):
        check_context_graph(DATA["question"], result, sources)


def test_constrained_question_cannot_be_promoted_to_full():
    control = next(c for c in DATA["controls"] if c["id"] == "temperature_no_propagation")
    sources = [{"text": control["text"]}]
    result = v3.audit(control["question"], sources, baseline_adequate=False)
    assert result["partial_relations"] and not result["textual_requirements_met"]
    damaged = copy.deepcopy(result)
    damaged["partial_relations"][0]["complete_requirements"] = True
    damaged["textual_requirements_met"] = True
    with pytest.raises(ValueError, match="exact diagnostic replay"):
        check_context_graph(control["question"], damaged, sources)
