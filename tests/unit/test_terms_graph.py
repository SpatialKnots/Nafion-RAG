"""Graph projections preserve source identity, overlapping membership and safe text."""
import json
import re
from copy import deepcopy
from dataclasses import asdict

import pytest

from app.terms.contexts import build_article
from scripts.tac_experiment import digest, span
from scripts.tac_terms import propose_inventory
from scripts.tac_terms_graph import pdf_uri, project_graph, render_graph
from tests.unit.test_term_contexts import inputs, sidecar


def graph_inputs(tmp_path):
    snapshot, profiles, _, terms = inputs(tmp_path)
    return snapshot, profiles, terms, sidecar(snapshot, profiles, terms)


def test_multiple_occurrences_do_not_inflate_circle_counts_and_TAC_overlap_is_retained(tmp_path):
    snapshot, profiles, _, _ = graph_inputs(tmp_path)
    a, p = snapshot["articles"][0], profiles["profiles"][0]
    page = a["pages"][0]
    page["text"] = "Nafion membranes. Nafion membranes."
    page["text_sha256"] = digest(page["text"].encode())
    p["sections"] = [asdict(span(page, kind, 0, len(page["text"]), "synthetic")) for kind in ("T", "A")]
    row = build_article(a, p, propose_inventory(p, [], 12)).model_dump(mode="json")
    before = deepcopy((snapshot, profiles, row))
    graph = project_graph(snapshot, profiles, {"articles": [row]}, tmp_path)
    article = graph["articles"][0]
    groups = {g["kind"]: g for g in article["groups"]}
    term = next(t for t in article["terms"] if t["term"] == "nafion")
    assert term["groups"] == ["T", "A"]
    assert len(term["use_ids"]) == 4
    assert groups["T"]["count"] == len(row["terms"]) == groups["A"]["count"]
    assert groups["C"]["count"] == 0 and groups["C"]["context_ids"] == []
    assert article["count"] < groups["T"]["count"] + groups["A"]["count"]
    assert (snapshot, profiles, row) == before


def test_identical_labels_from_distinct_uploads_keep_separate_term_and_group_ids(tmp_path):
    snapshot, profiles, terms, contexts = graph_inputs(tmp_path)
    a, p = deepcopy(snapshot["articles"][0]), deepcopy(profiles["profiles"][0])
    a["article_id"] = p["article_id"] = "second-upload"
    snapshot["articles"].append(a)
    profiles["profiles"].append(p)
    contexts["articles"].append(build_article(a, p, propose_inventory(p, [], 12)).model_dump(mode="json"))
    graph = project_graph(snapshot, profiles, contexts, tmp_path)
    one, two = graph["articles"]
    assert {t["label"] for t in one["terms"]} == {t["label"] for t in two["terms"]}
    assert {t["term_id"] for t in one["terms"]}.isdisjoint(t["term_id"] for t in two["terms"])
    assert {g["id"] for g in one["groups"]}.isdisjoint(g["id"] for g in two["groups"])
    assert graph["totals"]["terms"] == len(terms["articles"][0]["inventory"]) * 2


def test_source_paths_unicode_quotes_and_all_provenance_fields_are_preserved(tmp_path):
    snapshot, profiles, _, contexts = graph_inputs(tmp_path)
    graph = project_graph(snapshot, profiles, contexts, tmp_path)
    for source, projected in [(contexts["articles"][0][kind][0]["source"], graph["articles"][0][kind][0]["source"])
                              for kind in ("contexts", "mentions")]:
        assert all(projected[key] == value for key, value in source.items())
        assert projected["original_href"] == (tmp_path / source["original_pdf_path"]).resolve().as_uri() + f'#page={source["page_number"]}'
        assert projected["layer_href"].startswith("file:")


def test_script_terminators_template_markers_and_HTML_are_data_not_executable_markup(tmp_path):
    snapshot, profiles, _, contexts = graph_inputs(tmp_path)
    graph = project_graph(snapshot, profiles, contexts, tmp_path)
    attack = '</script><img src=x onerror="alert(1)"> @@STYLE@@ 😀\u2028'
    graph["articles"][0]["title"] = attack
    result = render_graph(graph, 'file:///test?x="&y=<tag>')
    payload = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', result, re.S).group(1)
    assert "<" not in payload
    assert json.loads(payload)["articles"][0]["title"] == attack
    assert result.count('id="graph-data"') == 1
    assert 'href="file:///test?x=&quot;&amp;y=&lt;tag&gt;"' in result


@pytest.mark.parametrize("name", ["../outside.pdf", "data/source.txt"])
def test_pdf_links_reject_escaping_source_root_and_non_PDF_targets(tmp_path, name):
    with pytest.raises(ValueError, match="outside declared source root"):
        pdf_uri(name, tmp_path)
