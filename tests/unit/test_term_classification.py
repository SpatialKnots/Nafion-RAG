"""Scientific categories stay proposals; context/source and subset contracts are enforced."""
import json
from copy import deepcopy
from dataclasses import asdict

import pytest

from app.terms.classification import ManualProposal, Taxonomy, classify_article, subset
from app.terms.contexts import build_article
from scripts.tac_experiment import digest, span
from scripts.tac_review_html import render_table
from scripts.tac_term_classification import DEFAULT_TAXONOMY, LEGACY_TAXONOMY, build_classification, validate_classification
from scripts.tac_terms import propose_inventory
from scripts.tac_terms_graph import attach_classification, project_graph
from tests.unit.test_term_contexts import inputs, sidecar


def fixture(tmp_path, text="Nafion membranes. We measured ionic conductivity. Temperature.", seeds=None):
    snapshot, profiles, _, _ = inputs(tmp_path)
    a, p = snapshot["articles"][0], profiles["profiles"][0]
    page = a["pages"][0]
    page.update(text=text, text_sha256=digest(text.encode()))
    p["sections"] = [asdict(span(page, "A", 0, len(text), "synthetic"))]
    row = build_article(a, p, propose_inventory(p, seeds or [], 12)).model_dump(mode="json")
    return row


def policy():
    return Taxonomy.model_validate(json.loads(LEGACY_TAXONOMY.read_bytes()))


def assigned(row, result, term, axis):
    t = next(t for t in row["terms"] if t["term"] == term)
    return [a for a in result["assignments"] if a["term_id"] == t["term_id"] and a["axis"] == axis]


def test_unknown_and_conflicting_categories_remain_visible_without_acceptance(tmp_path):
    row = fixture(tmp_path)
    before = deepcopy(row)
    result = classify_article(row, policy(), "a" * 64)
    assert row == before
    assert len(result["assignments"]) == 3 * len(row["uses"])
    temperature = assigned(row, result, "temperature", "type")[0]
    assert temperature["state"] == "unresolved"
    assert {p["category"] for p in temperature["proposals"]} == {"property", "condition"}
    assert assigned(row, result, "ionic conductivity", "type")[0]["state"] == "proposed"
    assert all(a["state"] != "accepted" for a in result["assignments"])
    unknown = next(g for g in result["groups"]["type"] if g["category"] == "unclassified")
    assert unknown["count"] > 0
    for category in ("property", "condition", "unresolved"):
        assert temperature["term_id"] in next(g for g in result["groups"]["type"] if g["category"] == category)["term_ids"]


def test_role_and_origin_differ_for_same_term_in_different_contextual_uses(tmp_path):
    row = fixture(tmp_path, "We investigated Nafion. Compared with Nafion, conductivity improved. We observed Nafion.")
    result = classify_article(row, policy(), "a" * 64)
    roles = assigned(row, result, "nafion", "role")
    assert {p["category"] for a in roles for p in a["proposals"]} == {"study_object", "comparison"}
    assert any(a["state"] == "unclassified" for a in roles)
    origins = assigned(row, result, "nafion", "origin")
    assert sum(a["state"] == "proposed" for a in origins) == 1
    assert sum(a["state"] == "unclassified" for a in origins) == 2
    # Study-object and own-report refer to distinct mentions: intersection must not
    # accidentally combine different uses of the same lexical term.
    view = subset(row, result["assignments"], {"role": "study_object", "origin": "own_report"}, "rank")
    assert view["count"] == 0


def test_word_per_line_and_unicode_evidence_preserve_exact_offsets(tmp_path):
    row = fixture(tmp_path, "😀 We measured\nionic\nconductivity. Nafion.")
    result = classify_article(row, policy(), "a" * 64)
    sources = {m["source"]["region_id"]: m["source"] for m in row["mentions"]}
    sources.update({c["source"]["region_id"]: c["source"] for c in row["contexts"]})
    for a in result["assignments"]:
        for proposal in a["proposals"]:
            for b in proposal["basis"]:
                source = sources[b["source_region_id"]]
                assert b["quote"] == source["quote"][b["start"] - source["start"]:b["end"] - source["start"]]
                assert digest(b["quote"].encode()) == b["quote_sha256"]


def test_method_role_requires_full_method_type_and_adjacent_cue(tmp_path):
    row = fixture(tmp_path, "Using impedance spectroscopy, we analyzed Nafion. Using Nafion, we cast membranes.",
                  [{"concept": "synthetic_method", "alias": "impedance spectroscopy", "language": "en"}])
    result = classify_article(row, policy(), "a" * 64)
    assert assigned(row, result, "impedance spectroscopy", "role")[0]["proposals"][0]["category"] == "method"
    assert all(a["state"] == "unclassified" for a in assigned(row, result, "nafion", "role"))


def test_subset_orders_are_deterministic_and_counts_deduplicate_repeated_mentions(tmp_path):
    row = fixture(tmp_path, "Water and Nafion. Nafion and water.")
    result = classify_article(row, policy(), "a" * 64)
    filters = {"type": "material_substance"}
    views = [subset(row, result["assignments"], filters, sort) for sort in ("rank", "alphabetical", "source")]
    assert all(v["count"] == 2 for v in views)
    assert views[0]["use_ids"] == views[1]["use_ids"] == views[2]["use_ids"]
    labels = {t["term_id"]: t["term"] for t in row["terms"]}
    assert [labels[i] for i in views[1]["term_ids"]] == ["nafion", "water"]
    assert [labels[i] for i in views[2]["term_ids"]] == ["water", "nafion"]


def test_manual_proposals_remain_proposals_and_require_known_target(tmp_path):
    row = fixture(tmp_path)
    use = row["uses"][0]
    manual = ManualProposal(use_id=use["use_id"], axis="origin", category="cited_work", reason="Synthetic review reason",
                            declared_reviewer="fixture", declared_reviewer_kind="human")
    result = classify_article(row, policy(), "a" * 64, [manual])
    assignment = next(a for a in result["assignments"] if a["axis"] == "origin" and a["use_id"] == use["use_id"])
    assert assignment["state"] in {"proposed", "unresolved"}
    assert any(p["declared_reviewer"] == "human:fixture" for p in assignment["proposals"])
    with pytest.raises(ValueError, match="target/category"):
        classify_article(row, policy(), "a" * 64, [manual.model_copy(update={"use_id": "f" * 64})])


@pytest.mark.parametrize("mutation", ["quote", "offset", "target", "state", "group", "view", "taxonomy"])
def test_corrupted_assertions_policy_and_saved_views_rejected(tmp_path, mutation):
    row = fixture(tmp_path)
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_bytes())
    contexts = {"articles": [row]}
    data = build_classification(contexts, taxonomy, "a" * 64, "b" * 64)
    data["taxonomy_content_sha256"] = digest(json.dumps(taxonomy, sort_keys=True, ensure_ascii=False).encode())
    validate_classification(contexts, data, "a" * 64)
    if mutation in {"quote", "offset"}:
        basis = next(p["basis"][0] for a in data["articles"][0]["assignments"] for p in a["proposals"])
        basis["quote" if mutation == "quote" else "start"] = "changed" if mutation == "quote" else 999
    elif mutation == "target":
        data["articles"][0]["assignments"][0]["use_id"] = "c" * 64
    elif mutation == "state":
        data["articles"][0]["assignments"][0]["state"] = "accepted"
    elif mutation == "group":
        data["articles"][0]["groups"]["type"][0]["count"] += 1
    elif mutation == "view":
        data["saved_views"][0]["sort"] = "invented"
    else:
        data["taxonomy"]["categories"]["type"]["property"] = "Changed"
    with pytest.raises(ValueError, match="mismatch"):
        validate_classification(contexts, data, "a" * 64)


def test_identity_stable_replays_and_changes_when_taxonomy_version_changes(tmp_path):
    row = fixture(tmp_path)
    one = classify_article(row, policy(), "a" * 64)
    assert one == classify_article(deepcopy(row), policy(), "a" * 64)
    two = classify_article(row, policy(), "b" * 64)
    assert {a["assignment_id"] for a in one["assignments"]}.isdisjoint(a["assignment_id"] for a in two["assignments"])


def test_graph_and_review_bind_same_classifications_without_adding_columns(tmp_path):
    snapshot, profiles, metadata, terms = inputs(tmp_path)
    contexts = sidecar(snapshot, profiles, terms)
    taxonomy = json.loads(DEFAULT_TAXONOMY.read_bytes())
    data = build_classification(contexts, taxonomy, "d" * 64, "b" * 64)
    data["taxonomy_content_sha256"] = digest(json.dumps(taxonomy, sort_keys=True, ensure_ascii=False).encode())
    graph = project_graph(snapshot, profiles, contexts, tmp_path)
    attach_classification(graph, contexts, data, "d" * 64)
    assert graph["schema"] == "tac_terms_graph_v0.2"
    assert graph["articles"][0]["assignments"] == data["articles"][0]["assignments"]
    html = render_table(snapshot, profiles, metadata, tmp_path, terms["profiles_sha256"], terms=terms,
                        terms_sha256="e" * 64, term_contexts=contexts, term_contexts_sha256="d" * 64,
                        classification=data, classification_sha256="f" * 64)
    assert html.count("<th>") == 8
    assert html.count('class="classification"') == 3 * len(contexts["articles"][0]["uses"])
    assert 'class="classification-subsets"' in html
    with pytest.raises(ValueError, match="mismatch"):
        attach_classification(graph, contexts, data, "c" * 64)
