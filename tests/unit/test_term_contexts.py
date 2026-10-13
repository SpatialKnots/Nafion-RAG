"""Synthetic source identity/context tests; no scientific labels."""

from copy import deepcopy
from dataclasses import asdict

import pytest

from app.terms.contexts import build_article, validate_article
from app.terms.schema import ArticleContexts
from scripts.tac_experiment import digest, span
from scripts.tac_review_html import render_table
from scripts.tac_term_contexts import VERSION, validate_contexts, verify_pdfs
from scripts.tac_terms import propose_inventory
from tests.unit.test_tac_term_inventory import inventory_fixture


def inputs(tmp_path):
    snapshot, profiles, metadata, terms = inventory_fixture(tmp_path)
    a = snapshot["articles"][0]
    for p in a["pages"]:
        p.update(layer_pdf_path=a["original_pdf_path"], layer_pdf_sha256=a["original_pdf_sha256"])
    return snapshot, profiles, metadata, terms


def sidecar(snapshot, profiles, terms):
    a, p, t = snapshot["articles"][0], profiles["profiles"][0], terms["articles"][0]
    return {
        "schema": VERSION,
        "state": "unclassified_source_bound_terms",
        "inventory_sha256": "e" * 64,
        "snapshot_sha256": terms["snapshot_sha256"],
        "profiles_sha256": terms["profiles_sha256"],
        "articles": [build_article(a, p, t).model_dump(mode="json")],
    }


def test_exact_sources_and_contexts_keep_inventory_and_preview_independent(tmp_path):
    snapshot, profiles, _, terms = inputs(tmp_path)
    a, p, t = snapshot["articles"][0], profiles["profiles"][0], terms["articles"][0]
    original = deepcopy((a, p, t))
    first = build_article(a, p, t)
    changed_preview = propose_inventory(p, [], 12)
    assert first == build_article(a, p, changed_preview)
    assert (a, p, t) == original
    assert len(first.terms) == len(t["inventory"])
    assert len(first.uses) == sum(len(c["evidence"]) for c in t["inventory"])
    for mention in first.mentions:
        s = mention.source
        assert a["pages"][0]["text"][s.start : s.end] == s.quote
    assert first.contexts[0].source.quote == p["sections"][0]["quote"]
    assert first.containment and all(u.state == "unclassified" for u in first.uses)


def test_repeated_mentions_and_same_term_in_distinct_contexts_stay_separate(tmp_path):
    snapshot, profiles, _, _ = inputs(tmp_path)
    a, p = snapshot["articles"][0], profiles["profiles"][0]
    page = a["pages"][0]
    page["text"] = "Nafion membranes; Nafion membranes.\nNafion membranes."
    page["text_sha256"] = digest(page["text"].encode())
    boundary = page["text"].index("\n")
    p["sections"] = [
        asdict(span(page, "T", 0, boundary, "synthetic")),
        asdict(span(page, "A", boundary + 1, len(page["text"]), "synthetic")),
    ]
    inv = propose_inventory(p, [], 12)
    row = build_article(a, p, inv)
    t = next(t for t in row.terms if t.term == "nafion")
    uses = [u for u in row.uses if u.term_id == t.term_id]
    assert len(uses) == 3 and len({u.mention_id for u in uses}) == 3 and len({u.context_id for u in uses}) == 2
    by_use = {u.use_id: u for u in row.uses}
    assert all(by_use[r.outer_use_id].context_id == by_use[r.inner_use_id].context_id for r in row.containment)


def test_paths_move_without_reidentifying_sources_but_separate_uploads_keep_own_ids(tmp_path):
    snapshot, profiles, _, terms = inputs(tmp_path)
    a, p, t = snapshot["articles"][0], profiles["profiles"][0], terms["articles"][0]
    first = build_article(a, p, t)
    moved = deepcopy(a)
    moved["original_pdf_path"] = "moved/source.pdf"
    moved["pages"][0]["layer_pdf_path"] = "moved/source.pdf"
    second = build_article(moved, p, t)
    assert [m.mention_id for m in first.mentions] == [m.mention_id for m in second.mentions]
    assert [c.context_id for c in first.contexts] == [c.context_id for c in second.contexts]
    other_a, other_p = deepcopy(a), deepcopy(p)
    other_a["article_id"] = other_p["article_id"] = "duplicate-upload"
    other = build_article(other_a, other_p, propose_inventory(other_p, [], 12))
    assert {m.mention_id for m in first.mentions}.isdisjoint(m.mention_id for m in other.mentions)


def test_source_version_and_selected_layer_changes_reidentify_mentions(tmp_path):
    snapshot, profiles, _, terms = inputs(tmp_path)
    a, p, t = snapshot["articles"][0], profiles["profiles"][0], terms["articles"][0]
    old_ids = {m.mention_id for m in build_article(a, p, t).mentions}
    a["pages"][0]["text"] += " Changed outside the TAC fragment."
    a["pages"][0]["text_sha256"] = digest(a["pages"][0]["text"].encode())
    p["sections"][0]["page_text_sha256"] = a["pages"][0]["text_sha256"]
    version = build_article(a, p, propose_inventory(p, [], 12))
    assert old_ids.isdisjoint(m.mention_id for m in version.mentions)
    a["pages"][0].update(layer="ocr", layer_id="synthetic-ocr", layer_pdf_path="ocr.pdf", layer_pdf_sha256="f" * 64)
    p["sections"][0].update(layer="ocr", layer_id="synthetic-ocr")
    layer = build_article(a, p, propose_inventory(p, [], 12))
    assert {m.mention_id for m in version.mentions}.isdisjoint(m.mention_id for m in layer.mentions)


def test_overlapping_TAC_kinds_share_physical_mentions_but_keep_distinct_uses(tmp_path):
    snapshot, profiles, _, _ = inputs(tmp_path)
    a, p = snapshot["articles"][0], profiles["profiles"][0]
    section = p["sections"][0]
    p["sections"] = [section, {**section, "kind": "A"}]
    row = build_article(a, p, propose_inventory(p, [], 12))
    assert len(row.contexts) == 2 and len(row.uses) == 2 * len(row.mentions)
    assert len({u.use_id for u in row.uses}) == len(row.uses)


def test_missing_page_is_an_explicit_gap_and_fragments_never_join(tmp_path):
    snapshot, profiles, _, _ = inputs(tmp_path)
    a, p = snapshot["articles"][0], profiles["profiles"][0]
    q = deepcopy(a["pages"][0])
    q.update(page=3, layer_id="synthetic-page-3", text="Nafion membranes.", text_sha256=digest(b"Nafion membranes."))
    a["pages"].append(q)
    p["sections"] = [asdict(span(a["pages"][0], "C", 0, 16, "synthetic")), asdict(span(q, "C", 0, len(q["text"]), "synthetic"))]
    row = build_article(a, p, propose_inventory(p, [], 12))
    group = next(g for g in row.section_groups if g.kind == "C")
    assert len(group.context_ids) == 2
    assert group.transitions[0].geometry == "page_gap" and group.transitions[0].text_continuity == "not_asserted"
    sources = {c.context_id: c.source for c in row.contexts}
    assert [sources[i].page_number for i in group.context_ids] == [1, 3]


@pytest.mark.parametrize(
    "mutation",
    [
        "quote",
        "layer",
        "offset",
        "pdf_hash",
        "context_quote",
        "context_missing",
        "use_context",
        "use_term",
        "duplicate_use",
        "missing_use",
        "false_containment",
        "missing_containment",
        "scientific_state",
    ],
)
def test_context_contract_rejects_corruption_and_fabricated_relations(tmp_path, mutation):
    snapshot, profiles, _, terms = inputs(tmp_path)
    a, p, t = snapshot["articles"][0], profiles["profiles"][0], terms["articles"][0]
    data = build_article(a, p, t).model_dump(mode="json")
    s = data["mentions"][0]["source"]
    if mutation == "quote":
        s["quote"] = "Fake"
    elif mutation == "layer":
        s["text_layer_id"] = "wrong"
    elif mutation == "offset":
        s["start"] += 1
    elif mutation == "pdf_hash":
        s["layer_pdf_sha256"] = "f" * 64
    elif mutation == "context_quote":
        data["contexts"][0]["source"]["quote"] = "Fake context"
    elif mutation == "context_missing":
        data["contexts"].clear()
    elif mutation == "use_context":
        data["uses"][0]["context_id"] = "f" * 64
    elif mutation == "use_term":
        data["uses"][0]["term_id"] = "f" * 64
    elif mutation == "duplicate_use":
        data["uses"].append(deepcopy(data["uses"][0]))
    elif mutation == "missing_use":
        data["uses"].pop()
    elif mutation == "false_containment":
        data["containment"][0]["inner_use_id"] = data["containment"][0]["outer_use_id"]
    elif mutation == "missing_containment":
        data["containment"].clear()
    elif mutation == "scientific_state":
        data["uses"][0]["state"] = "accepted"
    with pytest.raises(ValueError):
        validate_article(a, p, t, data)


def test_html_shares_context_templates_and_binds_every_use_without_extra_columns(tmp_path):
    snapshot, profiles, metadata, terms = inputs(tmp_path)
    contexts = sidecar(snapshot, profiles, terms)
    validate_contexts(snapshot, profiles, terms, contexts, "e" * 64)
    html = render_table(
        snapshot,
        profiles,
        metadata,
        tmp_path,
        "c" * 64,
        terms=terms,
        terms_sha256="e" * 64,
        term_contexts=contexts,
        term_contexts_sha256="f" * 64,
    )
    assert html.count("<th>") == 8 and "materializeContext" in html and "Лексические вложения" in html
    row = contexts["articles"][0]
    for c in row["contexts"]:
        assert html.count(f'id="context-{c["context_id"]}"') == 1
    for u in row["uses"]:
        assert f'data-use-id="{u["use_id"]}"' in html
    with pytest.raises(ValueError, match="input"):
        validate_contexts(snapshot, profiles, terms, contexts, "a" * 64)
    assert ArticleContexts.model_validate(row).article_id == "synthetic"


def test_physical_hash_failure_and_source_root_escape_are_not_hidden(tmp_path):
    snapshot, _, _, _ = inputs(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        verify_pdfs(snapshot, tmp_path)
    snapshot["articles"][0]["original_pdf_path"] = "../outside.pdf"
    with pytest.raises(ValueError, match="outside"):
        verify_pdfs(snapshot, tmp_path)
