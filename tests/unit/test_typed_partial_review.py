import copy
import json
from pathlib import Path

import pytest

from scripts.typed_partial_relations import audit
from scripts.verify_typed_partial_relation_review import check_graph

DATA = json.loads((Path(__file__).resolve().parents[2] / "docs/records/typed_partial_controls_v0.2.json").read_bytes())


def sample():
    source = [{"text": "Nafion particle morphology depends on the alpha/beta ratio."}]
    return audit(DATA["question"], source, baseline_adequate=False), source


def test_raw_graph_component_corruption_is_rejected():
    result, sources = sample()
    assert check_graph(result, sources) > 0
    result["typed_sources"][0]["units"][0]["variables"][0]["components"][0]["span"]["text"] = "wrong"
    with pytest.raises(ValueError, match="Raw span differs"):
        check_graph(result, sources)


def test_partial_edge_cannot_silently_become_full_requirements():
    result, sources = sample()
    damaged = copy.deepcopy(result)
    damaged["textual_requirements_met"] = True
    with pytest.raises(ValueError, match="Partial and full requirements conflated"):
        check_graph(damaged, sources)
