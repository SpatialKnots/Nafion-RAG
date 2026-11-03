from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.cross_lingual_relation_audit import audit, matching_view, requirements, source_audit

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "docs/records/cross_lingual_relation_controls_v0.1.json").read_bytes())


def sources(control):
    return [
        {"text": raw, "article_id": f"source-{index}", "title": control.get("title", "unknown")}
        for index, raw in enumerate(control.get("texts", [control.get("text", "")]))
    ]


@pytest.mark.parametrize("control", DATA["controls"], ids=lambda row: row["id"])
def test_frozen_controls(control):
    raw_sources = sources(control)
    before = copy.deepcopy(raw_sources)
    result = audit(control.get("question", DATA["default_question"]), raw_sources, baseline_adequate=False)
    assert bool(result["proposals"]) == control["candidate"]
    assert result["textual_requirements_met"] == control.get("requirements_met", control["candidate"])
    assert not result["scientific_admission"]
    assert raw_sources == before
    if "exact_fields" in control:
        checks = [field for proposal in result["proposals"] for field in proposal["field_checks"]]
        assert checks
        assert all(field["exact_local_surface_present"] for field in checks) == control["exact_fields"]
        assert all(field["owner_established"] is False for field in checks)
    if "duplicate_groups" in control:
        assert len(result["duplicates"]) == control["duplicate_groups"]
        assert len(result["repeated_proposal_spans"]) == control["duplicate_groups"]
    for analysis in result["sources"]:
        raw = raw_sources[analysis["evidence_index"]]["text"]
        for region in analysis["regions"]:
            anchors = [region["span"], *region["owner_links"], *region["relation_links"], *region["fields"]]
            anchors.extend(anchor for spans in region["role_spans"].values() for anchor in spans)
            if region["antecedent"]:
                anchors.append(region["antecedent"])
            for anchor in anchors:
                assert raw[anchor["start"] : anchor["end"]] == anchor["text"]


def test_matching_view_preserves_raw_expanded_ligature_and_join():
    raw = "Naﬁon morpho-\nlogy"
    view = matching_view(raw)
    assert view.text == "Nafion morphology"
    assert view.anchor(0, len(view.text)) == {"start": 0, "end": len(raw), "text": raw}


@pytest.mark.parametrize("question", ["Nafion swelling", "Compare H-Nafion and Li-Nafion", "Методы литирования Nafion"])
@pytest.mark.parametrize("baseline", [False, True])
def test_outside_scope_preserves_baseline(question, baseline):
    result = audit(question, [{"text": "Nafion"}], baseline_adequate=baseline)
    assert result["state"] == "out_of_scope"
    assert result["baseline_adequate"] is baseline
    assert result["baseline_preserved"]
    assert result["textual_requirements_met"] is None


def test_original_ru_question_has_no_dropped_qualifiers():
    result = requirements("Как меняется морфология частиц дисперсии Nafion в зависимости от природы растворителя?")
    assert result["in_scope"]
    assert result["unsupported_query_tokens"] == []


def test_empty_or_non_text_source_never_becomes_candidate():
    assert source_audit("")["candidate_count"] == 0
    with pytest.raises(TypeError, match="Raw source"):
        source_audit(None)


def test_textual_candidate_is_independent_of_source_identifiers():
    raw = DATA["controls"][0]["text"]
    left = audit(DATA["default_question"], [{"text": raw, "article_id": "a", "title": "Kim", "doi": "fake"}], baseline_adequate=False)
    right = audit(DATA["default_question"], [{"text": raw, "article_id": "b", "title": None}], baseline_adequate=False)
    assert left == right
