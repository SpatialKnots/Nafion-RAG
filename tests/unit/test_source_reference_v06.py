import json
from pathlib import Path

import pytest

from scripts import source_reference_chains as v5
from scripts import source_reference_chains_v06 as v6
from scripts.run_source_reference_review_v06 import controls
from scripts.verify_source_reference_review_v06 import check_chains

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "docs/records/source_reference_controls_v0.6.json").read_bytes())
HEADINGS = [c for c in DATA["controls"] if c["id"].startswith("heading_v06_")]


@pytest.mark.parametrize("control", HEADINGS, ids=lambda c: c["id"])
def test_explicit_particle_owner_does_not_cross_heading(control):
    sources = [{"text": control["text"]}]
    result = v6.audit(DATA["question"], sources, baseline_adequate=False)
    assert result["source_chains"] == []
    assert not result["chain_textual_requirements_met"]
    if v5.audit(DATA["question"], sources, baseline_adequate=False)["source_chains"]:
        assert result["chain_sources"][0]["heading_rejections"]
    check_chains(DATA["question"], result, sources)


def test_all_54_controls_and_historical_failure_preserved():
    assert len(controls()["records"]) == 54
    sources = [{"text": HEADINGS[0]["text"]}]
    old = v5.audit(DATA["question"], sources, baseline_adequate=False)
    assert old["chain_textual_requirements_met"] is True
    v6.audit(DATA["question"], sources, baseline_adequate=False)
    assert v5.audit(DATA["question"], sources, baseline_adequate=False) == old


def test_rejected_heading_raw_anchor_corruption_detected():
    sources = [{"text": HEADINGS[0]["text"]}]
    result = v6.audit(DATA["question"], sources, baseline_adequate=False)
    result["chain_sources"][0]["heading_rejections"][0]["heading_spans"][0]["text"] = "invented"
    with pytest.raises(ValueError, match="Raw span differs"):
        check_chains(DATA["question"], result, sources)
