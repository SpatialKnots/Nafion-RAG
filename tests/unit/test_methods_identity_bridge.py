"""Read-only real-source bridge candidate and separate constructed controls."""

import hashlib
import json
import re
from pathlib import Path

import pytest

from app.classification.rules import classify_source_type
from app.extraction.text_quality import detect_formula_like_lines
from app.generation.fact_types import SourceView
from app.generation.providers import Evidence
from app.generation.source_role_assembly import prepare as assemble
from scripts.methods_identity_bridge_20261109 import BASES, CODE, BridgeError, inspect, raw_code

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "output/methods_identity_bridge_20261109"
CASES = json.loads((BASE / "controls_v02.json").read_bytes())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_real_and_constructed_bridge_outcomes(case):
    sources = [Evidence(**e) for e in case["sources"]]
    if not case["expected_candidate"]:
        with pytest.raises(BridgeError):
            inspect(*sources, case["layers"])
        return
    result = inspect(*sources, case["layers"])
    assert result["status"] == "finite_ordered_methods_identity_candidate"
    assert not result["scientific_ownership_verified"] and not result["values_propagated"]
    assert not result["production_admission_changed"]
    if case["id"] == "coherent_numeric_change":
        assert [result[k] for k in ("base_concentration", "additive_concentration", "reported_total")] == ["0.8", "0.2", "1.0"]
    else:
        assert result["base_concentration"] == "1.2" and result["additive_concentration"] == "0.15"
        assert result["reported_total"] == "1.35"
    assert result["ratio"] == "1:1:1"
    assert result["solvents"] == ["FEC", "DMC", "HFE"]
    if case["id"] == "opaque_target_code":
        assert result["target_code"] == "TGT-999-LiPD"
    elif case["id"] == "joint_permutation":
        assert result["product_position"] == 1
    else:
        assert result["target_code"] == "FDH-1.35M-LiPD" and result["product_position"] == 2
    if case["id"] == "coherent_base_reordering":
        assert result["base_position"] == 1


def test_every_provenance_anchor_matches_unchanged_raw_parent():
    case = CASES[0]
    sources = [Evidence(**e) for e in case["sources"]]
    result = inspect(*sources, case["layers"])
    by_chunk = {s.chunk_id: s for s in sources}
    count = 0

    def visit(value):
        nonlocal count
        if isinstance(value, dict):
            if {"chunk_id", "start", "end", "text", "raw_chunk_sha256"} <= set(value):
                source = by_chunk[value["chunk_id"]]
                assert source.text[value["start"]:value["end"]] == value["text"]
                assert hashlib.sha256(source.text.encode()).hexdigest() == value["raw_chunk_sha256"]
                assert source.article_id == value["article_id"] and source.citation_id == value["citation_id"]
                count += 1
            for item in value.values():
                visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(result["bindings"])
    assert count > 20


def test_caption_trigger_is_whole_chunk_heuristic_not_a_Methods_identity():
    case = CASES[0]
    sources = [Evidence(**e) for e in case["sources"]]
    result = inspect(*sources, case["layers"])
    methods = sources[1]
    assert methods.source_type == "figure_caption"
    assert classify_source_type(methods.text) == "figure_caption"
    trigger = re.search(r"^\s*Figure\s+2", methods.text, re.M)
    assert trigger is not None
    assert "2.1. Material Preparation." in methods.text[:trigger.start()]
    section = result["bindings"]["methods_section"]
    assert classify_source_type(section["text"]) == "formula_block"
    lines = [line for line in section["text"].splitlines() if line.strip()]
    assert len(detect_formula_like_lines(section["text"])) / len(lines) >= 0.3
    assert result["source_types_retained"][methods.chunk_id] == "figure_caption"


def test_audit_candidate_does_not_relax_current_runtime_assembly():
    case = CASES[0]
    sources = [Evidence(**e) for e in case["sources"]]
    assert inspect(*sources, case["layers"])["status"] == "finite_ordered_methods_identity_candidate"
    blocked = assemble(case["question"], sources, case["reference"], case["layers"])
    assert not blocked.eligible and blocked.reason == "assembly_source_scope_unresolved"


def test_raw_codes_preserve_structural_hyphen_lost_by_word_dehyphenation():
    source = Evidence(**{**CASES[0]["sources"][1], "text": "AAA-1.0M-\nLiPF6"})
    view = SourceView(source)
    match = view.one("(?P<code>" + CODE + ")")
    assert match["code"] == "AAA-1.0MLiPF6"
    assert raw_code(view, match, "code") == "AAA-1.0M-LiPF6"
    real = Evidence(**CASES[0]["sources"][1])
    real_view = SourceView(real)
    bases = real_view.one(BASES)
    assert raw_code(real_view, bases, "code3") == "FDH-1.2M-LiPF6"
