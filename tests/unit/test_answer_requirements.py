"""Finite diagnostic map; no inference decisions, source rewrites or model calls."""

import copy
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.generation.providers import Evidence

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "output/answer_requirements_20261109/controls_v01.json").read_bytes())
REAL = CASES[0]["parent"]


def build(p=None):
    from app.generation.answer_requirements import build_requirements

    return build_requirements(p or copy.deepcopy(REAL))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_declared_controls_and_unchanged_preparation(case):
    p = copy.deepcopy(case["parent"])
    before = copy.deepcopy(p)
    result = build(p)
    assert p == before
    assert result["scientific_support"] == "not_evaluated"
    assert result["selection_changed"] is False and result["admission_changed"] is False
    assert not result["generation_performed"] and not result["external_request_constructed"]
    if result["status"] == "not_applicable":
        assert case["id"] in {"unsupported_query"}
        assert result["requirements"] == []
    else:
        assert len(result["requirements"]) == 4
        assert result["requirements"][-1]["state"] == case["expected_identity"]
        assert all(row["scientific_support"] == "not_evaluated" for row in result["requirements"])
        assert all(not row["next_action"]["executed"] for row in result["requirements"])


@pytest.mark.parametrize("cid,state", [("cue_only", "grammar_unrecognized"), ("no_cues", "not_found_in_inspected_context"),
                                       ("missing_registry", "uninspected_selected_sources")])
def test_missing_scanned_source_and_unsupported_grammar_are_distinct(cid, state):
    result = build(next(c["parent"] for c in CASES if c["id"] == cid))
    assert all(row["state"] == state for row in result["requirements"][:3])
    assert all(not row["candidates"] for row in result["requirements"][:3])
    if cid == "cue_only":
        assert all(row["cue_anchors"] for row in result["requirements"][:3])
    if cid == "missing_registry":
        assert result["scan_scope"]["inspected_parents"] == 0
        assert len(result["scan_scope"]["uninspected"]) == 3


def test_recognized_fact_anchors_are_exact_raw_sources_not_baseline_metadata():
    p = copy.deepcopy(REAL)
    p["baseline_metadata"]["source_facts"] = {"records": [{"facts": [{"value": "invented"}]}]}
    result = build(p)
    count = 0
    for row in result["requirements"][:3]:
        assert row["state"] == "recognized_source_pattern"
        for candidate in row["candidates"]:
            for fact in candidate["facts"]:
                anchor = fact["support"]
                source = p["sources"]["chunks"][anchor["chunk_id"]]
                assert source["text"][anchor["start"]:anchor["end"]] == anchor["text"]
                assert hashlib.sha256(source["text"].encode()).hexdigest() == anchor["raw_chunk_sha256"]
                assert "invented" not in json.dumps(fact)
                count += 1
    assert count >= 5


@pytest.mark.parametrize("change", ["raw", "article", "layer", "pages", "source_type", "duplicate_citation", "generation", "version"])
def test_broken_preparation_source_binding_fails_visibly(change):
    p = copy.deepcopy(REAL)
    e = p["evidence"][0]
    raw = p["sources"]["chunks"][e["chunk_id"]]
    if change == "raw":
        e["text"] += " altered"
    elif change == "article":
        raw["article_id"] = "foreign"
    elif change == "layer":
        raw["text_layer"] = "ocr"
    elif change == "pages":
        raw["page_end"] += 1
    elif change == "source_type":
        raw["source_type"] = "other"
    elif change == "duplicate_citation":
        p["evidence"][1]["citation_id"] = e["citation_id"]
    elif change == "generation":
        p["generation_performed"] = True
    else:
        p["version"] = "unknown"
    with pytest.raises(ValueError):
        build(p)


def test_complete_derived_graph_restores_registered_raw_parents_and_detects_tampering():
    from app.generation.methods_identity import POLICY, prepare

    p = copy.deepcopy(REAL)
    raw = [Evidence(**e) for e in p["evidence"]]
    layers = p["sources"]["chunk_layers"]
    reference = p["baseline_metadata"]["retrieval"]["explicit_source_reference"]
    bundle = prepare(p["question"], raw, reference, layers, policy=POLICY)
    assert bundle.eligible
    p["evidence"] = [asdict(e) for e in bundle.evidence]
    result = build(p)
    assert result["requirements"][-1]["state"] == "textual_contract_available"
    assert result["scan_scope"]["restored_derived_parents"] == 3
    p["evidence"][1]["text"] = p["evidence"][1]["text"].replace("dimethyl carbonate", "diethyl carbonate")
    with pytest.raises(ValueError):
        build(p)


@pytest.mark.parametrize("change", ["question", "source", "blocker", "map"])
def test_stale_map_and_parent_changes_are_rejected(change):
    from app.generation.answer_requirements import validate_requirements

    p, result = copy.deepcopy(REAL), build()
    if change == "question":
        p["question"] += " altered"
    elif change == "source":
        p["sources"]["chunks"].pop(p["evidence"][0]["chunk_id"])
    elif change == "blocker":
        p["blocking_reasons"].append("changed")
    else:
        result["requirements"][0]["state"] = "scientifically_confirmed"
    with pytest.raises(ValueError):
        validate_requirements(result, p)


@pytest.mark.parametrize("question", ["Conductivity?", "Состав и циклирование?", "", "What is the maximum swelling?"])
def test_other_query_scopes_are_explicitly_not_applicable(question):
    p = copy.deepcopy(REAL)
    p["question"] = question
    result = build(p)
    assert result["status"] == "not_applicable" and not result["requirements"]


def test_diagnostic_actions_do_not_fetch_or_enable_methods_policy():
    from app.core.config import Settings

    before = Settings(_env_file=None).rag_methods_identity_policy
    with patch("app.generation.service.search_chunks", side_effect=AssertionError("No retrieval from diagnostic map")), \
            patch("app.generation.service.build_answer_provider", side_effect=AssertionError("No model from diagnostic map")):
        result = build()
    assert before == Settings(_env_file=None).rag_methods_identity_policy == "disabled"
    assert all(not r["next_action"]["executed"] and r["next_action"]["new_source_budget"] == 0 for r in result["requirements"])


def test_conflicting_values_are_alternatives_and_redundant_bindings_are_not_independent_support():
    conflict = build(next(c["parent"] for c in CASES if c["id"] == "conflicting_value"))
    ce = next(r for r in conflict["requirements"] if r["id"] == "coulombic")
    assert ce["state"] == "ambiguous_source_candidates" and len(ce["alternative_groups"]) == 2
    repeated = build(next(c["parent"] for c in CASES if c["id"] == "duplicate_parent"))
    ce = next(r for r in repeated["requirements"] if r["id"] == "coulombic")
    assert ce["state"] == "recognized_source_pattern" and len(ce["alternative_groups"]) == 1
    assert not repeated["scan_scope"]["independent_source_count_established"]


@pytest.mark.parametrize("flag", ["source_registry_unproven", "baseline_insufficient_evidence", "query_qualifier_check_failed",
                                 "complete_source_pages_retained", "evidence_bundle_over_budget"])
def test_map_never_removes_or_overrides_original_preparation_blocker(flag):
    p = copy.deepcopy(REAL)
    p["blocking_reasons"] = [flag]
    result = build(p)
    assert result["baseline_blocking_reasons"] == [flag] and result["baseline_status"] == "blocked"
    assert not result["admission_changed"] and not result["network_ready"]


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.generation import requirements_routes as routes
    from app.main import app

    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = lambda: object()
    stub = Mock(return_value=copy.deepcopy(REAL))
    monkeypatch.setattr(routes, "prepare_api", stub)
    try:
        with TestClient(app) as client:
            yield client, stub
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_api_retains_parent_and_validated_request_options(client):
    client, stub = client
    request = {"question": REAL["question"], "library_source_id": str(UUID(int=17)), "top_k": 2,
               "collection": "selected", "method": "exact", "answer_language": "ru"}
    response = client.post("/answer/prepare/requirements", json=request)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["preparation"] == REAL
    assert data["requirements"]["request_scope"]["library_source_id"] == request["library_source_id"]
    assert stub.call_args.args[1].library_source_id == UUID(int=17)
    assert stub.call_args.args[1].top_k == 2 and stub.call_args.args[1].collection == "selected"
    assert not data["generation_performed"] and not data["network_ready"]


@pytest.mark.parametrize("extra", [{"generate": True}, {"sources": []}, {"top_k": 0}, {"method": "unknown"},
                                   {"library_source_id": "bad"}])
def test_invalid_request_options_do_not_run_preparation(client, extra):
    client, stub = client
    response = client.post("/answer/prepare/requirements", json={"question": REAL["question"], **extra})
    assert response.status_code == 422
    stub.assert_not_called()


@pytest.mark.parametrize("error,status", [(ValueError("source mismatch"), 400)])
def test_map_integrity_error_keeps_http_error_semantics(client, error, status):
    from app.generation import requirements_routes as routes

    client, _ = client
    with patch.object(routes, "build_requirements", side_effect=error):
        result = client.post("/answer/prepare/requirements", json={"question": REAL["question"]})
    assert result.status_code == status


def test_ui_has_readable_states_exact_quotes_and_escaped_content(client):
    from app.generation import requirements_routes as routes

    client, _ = client
    p = copy.deepcopy(REAL)
    p["query_qualifiers"] = {"articles": []}
    p["source_links"] = [{"citation_id": e["citation_id"], "pdf_url": "/articles/" + e["article_id"] + "/pdf",
                          "context_url": None} for e in p["evidence"]]
    with patch.object(routes, "prepare_api", return_value=p):
        response = client.post("/ui/answer/prepare/requirements", data={"question": REAL["question"]})
    assert response.status_code == 200
    assert response.text.count("data-answer-requirement=") == 4
    assert "Научная поддержка не оценена" in response.text
    assert "Что проверить дальше" in response.text and "Точный фрагмент" in response.text
    page = client.get("/ui/answer/prepare/requirements", params={"question": "<script>bad</script>",
        "library_source_id": str(UUID(int=18))})
    assert "<script>bad</script>" not in page.text and "&lt;script&gt;bad&lt;/script&gt;" in page.text
    assert 'action="/ui/answer/prepare/requirements"' in page.text and str(UUID(int=18)) in page.text


def test_actual_preparation_boundary_produces_map_without_provider_factory(monkeypatch):
    from app.generation import preparation, service
    from app.generation.answer_requirements import build_requirements
    from app.retrieval.search import SearchResponse
    from tests.unit.test_answer_preparation import setup_service
    from tests.unit.test_generation import _search_result, _settings

    session, e, sources = setup_service(monkeypatch, text=REAL["evidence"][0]["text"],
        authors=[{"name": "Lin"}, {"name": "Zhao"}], year=2020)
    sources["chunks"][e.chunk_id] = {"text": e.text, "article_id": e.article_id, "source_type": e.source_type,
        "page_start": e.page_start, "page_end": e.page_end, "text_layer": sources["chunk_layers"][e.chunk_id]}
    monkeypatch.setattr(preparation, "answer_question", service.answer_question)
    row = replace(_search_result(), article_id=e.article_id, chunk_id=e.chunk_id, page_start=e.page_start,
        page_end=e.page_end, full_text=e.text, snippet=e.text, title=e.title)
    reference = copy.deepcopy(REAL["baseline_metadata"]["retrieval"]["explicit_source_reference"])
    reference["article_id"] = e.article_id
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: SearchResponse(REAL["question"], [row],
        {"explicit_source_reference": reference}))
    forbidden = Mock(side_effect=AssertionError("No provider factory in requirement preparation"))
    monkeypatch.setattr(service, "build_answer_provider", forbidden)
    p = preparation.prepare_answer(session, _settings(), REAL["question"], answer_language="ru")
    before = copy.deepcopy(p)
    mapped = build_requirements(p)
    assert mapped["status"] == "mapped" and p == before
    assert mapped["scan_scope"]["restored_derived_parents"] == 1
    assert not p["generation_performed"] and not p["external_request_constructed"]
    forbidden.assert_not_called()
