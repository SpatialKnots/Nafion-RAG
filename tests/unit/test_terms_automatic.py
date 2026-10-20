"""Synthetic generalization/source-isolation tests for automatic contextual Terms."""
import json
from copy import deepcopy

import pytest

from app.terms.classification import Taxonomy, classify_article, subset
from scripts.tac_experiment import digest
from scripts.tac_term_classification import DEFAULT_TAXONOMY, build_classification, validate_classification
from tests.unit.test_term_classification import assigned, fixture


def automatic_policy():
    return Taxonomy.model_validate(json.loads(DEFAULT_TAXONOMY.read_bytes()))


def test_same_word_different_uses_classified_automatically_and_basis_is_exact(tmp_path):
    row = fixture(tmp_path, "Glass transition temperature increased. At room temperature, conductivity was measured.")
    before = deepcopy(row)
    result = classify_article(row, automatic_policy(), "a" * 64)
    types = assigned(row, result, "temperature", "type")
    assert len(types) == 2
    assert {p["category"] for a in types for p in a["proposals"]} == {"property", "condition"}
    assert all(a["state"] == "proposed" for a in types)
    contexts = {c["source"]["region_id"]: c["source"] for c in row["contexts"]}
    for assignment in types:
        for proposal in assignment["proposals"]:
            for basis in proposal["basis"]:
                source = contexts[basis["source_region_id"]]
                assert source["quote"][basis["start"] - source["start"]:basis["end"] - source["start"]] == basis["quote"]
                assert digest(basis["quote"].encode()) == basis["quote_sha256"]
                assert "review required" not in " ".join(assignment["diagnostics"])
    assert row == before


def test_generic_quantity_unknown_material_and_same_use_intersection_remain_explicit(tmp_path):
    row = fixture(tmp_path, "We investigated perovskite. Temperature. Compared with perovskite, conductivity improved.",
                  [{"concept": "synthetic_unknown", "alias": "perovskite", "language": "en"}])
    result = classify_article(row, automatic_policy(), "a" * 64)
    assert assigned(row, result, "temperature", "type")[0]["state"] == "unresolved"
    assert all(a["state"] == "unclassified" for a in assigned(row, result, "perovskite", "type"))
    assert subset(row, result["assignments"], {"type": "material_substance", "role": "study_object"}, "rank")["count"] == 0
    assert all(p["producer"] == "policy" for a in result["assignments"] for p in a["proposals"])


def test_specific_onset_property_overrides_thermal_setting_without_cross_sentence_leakage(tmp_path):
    row = fixture(tmp_path, "The onset of gas generation was observed at a higher temperature. At a lower temperature, water was present.")
    result = classify_article(row, automatic_policy(), "a" * 64)
    types = assigned(row, result, "temperature", "type")
    assert len(types) == 2
    mentions = {m["mention_id"]: m["source"]["start"] for m in row["mentions"]}
    types.sort(key=lambda a: mentions[a["mention_id"]])
    assert [a["proposals"][0]["category"] for a in types] == ["property", "condition"]
    assert all(a["state"] == "proposed" for a in types)


def test_prepared_membrane_comparison_generalizes_without_promoting_unbound_temperature(tmp_path):
    row = fixture(tmp_path, "At higher temperature (120 °C), membranes prepared from water were smaller than those at lower temperature. "
                  "A higher temperature was reported.")
    result = classify_article(row, automatic_policy(), "a" * 64)
    types = assigned(row, result, "temperature", "type")
    assert len(types) == 3
    assert sum(a["state"] == "proposed" for a in types) == 2
    assert sum(a["state"] == "unresolved" for a in types) == 1
    assert all(a["proposals"][0]["category"] == "condition" for a in types if a["state"] == "proposed")


def test_word_per_line_nested_concentration_and_unrelated_generic_use(tmp_path):
    row = fixture(tmp_path, "Charge\ncarrier\nconcentration was extracted. Critical gelation concentration was observed. Concentration.")
    result = classify_article(row, automatic_policy(), "a" * 64)
    types = assigned(row, result, "concentration", "type")
    assert len(types) == 3
    assert sum(a["state"] == "proposed" for a in types) == 2
    assert sum(a["state"] == "unresolved" for a in types) == 1
    assert all(a["proposals"][0]["category"] == "property" for a in types if a["state"] == "proposed")


def test_new_corpus_recomputes_membership_and_changed_context_rejects_old_sidecar(tmp_path):
    row = fixture(tmp_path, "At room temperature, water was studied.")
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_bytes())
    data = build_classification({"articles": [row]}, taxonomy, "a" * 64, "b" * 64)
    data["taxonomy_content_sha256"] = digest(json.dumps(taxonomy, sort_keys=True, ensure_ascii=False).encode())
    assert data["schema"] == "tac_term_classification_v0.4"
    (tmp_path / "new").mkdir()
    new_row = fixture(tmp_path / "new", "Glass transition temperature was observed.")
    new = build_classification({"articles": [new_row]}, taxonomy, "c" * 64, "b" * 64)
    assert assigned(row, data["articles"][0], "temperature", "type")[0]["proposals"][0]["category"] == "condition"
    assert assigned(new_row, new["articles"][0], "temperature", "type")[0]["proposals"][0]["category"] == "property"
    with pytest.raises(ValueError, match="mismatch"):
        validate_classification({"articles": [new_row]}, data, "c" * 64)
    with pytest.raises(ValueError, match="manual input"):
        build_classification({"articles": [row]}, taxonomy, "a" * 64, "b" * 64, {})


def test_conflicting_equal_priority_context_rules_abstain_and_invalid_capture_is_rejected(tmp_path):
    data = json.loads(DEFAULT_TAXONOMY.read_bytes())
    rule = next(r for r in data["rules"] if r["rule_id"] == "temperature_glass_transition_v02")
    data["rules"].append(dict(rule, rule_id="synthetic_tied_context", category="condition"))
    row = fixture(tmp_path, "Glass transition temperature increased.")
    result = classify_article(row, Taxonomy.model_validate(data), "a" * 64)
    assignment = assigned(row, result, "temperature", "type")[0]
    assert assignment["state"] == "unresolved"
    assert {p["category"] for p in assignment["proposals"]} == {"property", "condition"}
    data["rules"][-1]["pattern"] = "temperature"
    with pytest.raises(ValueError, match="named term span"):
        Taxonomy.model_validate(data)
