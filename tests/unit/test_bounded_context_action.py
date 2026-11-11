"""One explicit raw CE completion; constructed gains, no automatic answer admission."""

import copy
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from app.generation.answer_evidence_packet import build_packet, serialize_packet
from app.retrieval.search import SearchFilters, SearchResult
from scripts.bounded_context_controls_20261110 import packet, registry

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "output/bounded_context_action_20261110/controls_v01.json").read_bytes())


def run(case=None, *, input_packet=None, register=None):
    from app.generation.bounded_context_action import run_context_action

    case = case or CASES[0]
    original = input_packet or packet(case)
    loader = Mock(return_value=[SearchResult(**r) for r in case["rows"]])
    registrar = Mock(side_effect=register or registry)
    return run_context_action(original, loader, registrar), original, loader, registrar


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_declared_candidate_pool_controls_and_recorded_replay(case):
    from app.generation.bounded_context_action import validate_context_result

    p = packet(case)
    before = copy.deepcopy(p)
    result, _, loader, registrar = run(case, input_packet=p)
    assert p == before and result["input_packet"] == before
    assert (result["added_evidence"] is not None) == case["expected_added"], result["stop_reason"]
    assert loader.call_count == 1 and registrar.call_count == int(case["expected_added"])
    assert result["consumed"]["model_calls"] == 0 and not result["generation_performed"]
    assert not result["admission_changed"] and not result["automatic_continuation"]
    validate_context_result(result, p, expected_result_id=result["result_id"])
    if result["added_evidence"]:
        candidate = result["candidate_map_input_adapter"]
        old = p["content"]["parent"]["preparation"]
        assert candidate["evidence"][:-1] == old["evidence"]
        assert candidate["status"] == old["status"] and candidate["blocking_reasons"] == old["blocking_reasons"]
        assert candidate["baseline_metadata"] == old["baseline_metadata"]
        assert candidate["scope"]["baseline_scope"] == old["scope"]
        assert result["after_requirements"]["requirements"][-1]["state"] == "textual_contract_available"
        assert result["input_packet"]["content"]["stop"]["new_source_actions_executed"] == 0
        assert result["consumed"]["accepted_raw_chunks"] == 1
        assert result["journal"]["parent_root_hash"] == p["journal"]["root_hash"]


@pytest.mark.parametrize("change", ["empty_scope", "different_labels", "missing_marker", "ref", "wrong_type", "missing_registry",
    "qualifier_block", "page_block", "byte_block", "library_conflict", "unsupported_query"])
def test_preconditions_stop_without_new_lookup_or_registry(change):
    case = copy.deepcopy(CASES[0])
    p = case["parent"]
    if change == "empty_scope":
        case["request_scope"] = {}
    elif change in {"different_labels", "missing_marker"}:
        e = p["evidence"][1]
        e["text"] = e["text"].replace("Electrolyte MIX-A.", "Electrolyte MIX-B." if change == "different_labels" else "")
        p["sources"]["chunks"][e["chunk_id"]]["text"] = e["text"]
    elif change == "ref":
        p["baseline_metadata"]["retrieval"]["explicit_source_reference"]["resolved"] = False
    elif change == "wrong_type":
        e = p["evidence"][1]
        e["source_type"] = p["sources"]["chunks"][e["chunk_id"]]["source_type"] = "figure_caption"
    elif change == "missing_registry":
        p["sources"]["chunks"] = {}
    elif change in {"qualifier_block", "page_block", "byte_block"}:
        p["blocking_reasons"] += [{"qualifier_block": "query_qualifier_check_failed", "page_block": "complete_source_pages_retained",
                                  "byte_block": "evidence_bundle_over_budget"}[change]]
    elif change == "library_conflict":
        p["baseline_metadata"]["retrieval"]["filters"] = {"library_source_id": str(UUID(int=17))}
    else:
        p["question"] += " при температуре 17 градусов"
        case["request_scope"]["question"] = p["question"]
    result, _, loader, registrar = run(case)
    loader.assert_not_called()
    registrar.assert_not_called()
    assert result["consumed"]["additional_lookup_calls"] == 0 and result["added_evidence"] is None


def test_real_full_Lin_packet_and_cue_only_refusal_do_not_trigger_completion():
    from app.generation.bounded_context_action import run_context_action
    from tests.unit.test_answer_evidence_packet import wrapped
    from tests.unit.test_answer_requirements import CASES as MAP_CASES

    forbidden = Mock(side_effect=AssertionError("Existing CE/cue-only grammar gap must not trigger I/O"))
    for case in (MAP_CASES[0], next(c for c in MAP_CASES if c["id"] == "cue_only")):
        current = build_packet(wrapped(case["parent"]))
        result = run_context_action(current, forbidden, forbidden)
        assert result["stop_reason"] == "target_role_present_or_not_missing"
    forbidden.assert_not_called()


@pytest.mark.parametrize("change", [None, "report", "qualifier"])
def test_inherited_empty_qualifier_rejection_is_recomputed_and_original_blocker_preserved(change):
    from app.generation.providers import Evidence
    from app.generation.query_qualifiers import assess_query_qualifiers

    case = copy.deepcopy(CASES[0])
    p = case["parent"]
    p["blocking_reasons"].append("query_qualifier_check_failed")
    p["query_qualifiers"] = assess_query_qualifiers(p["question"], [Evidence(**e) for e in p["evidence"]], baseline_allowed=False)
    if change == "report":
        p["query_qualifiers"]["reason"] = "changed"
    elif change == "qualifier":
        p["query_qualifiers"]["qualifiers"] = [{"kind": "unmet_constraint"}]
    result, _, loader, _ = run(case)
    assert loader.call_count == int(change is None)
    if change is None:
        assert result["plan"]["inherited_empty_qualifier_rejection_preserved"]
        assert "query_qualifier_check_failed" in result["candidate_map_input_adapter"]["blocking_reasons"]
    else:
        assert result["stop_reason"] == "blocking_reason_prevents_context_action"


def test_actual_preparation_packet_action_pipeline_keeps_original_rejection(tmp_path):
    from scripts.probe_context_pipeline_20261110 import run as probe

    observed = probe(tmp_path / "actual_pipeline")
    assert observed["added"] and observed["lookup_calls"] == 1
    assert "query_qualifier_check_failed" in observed["baseline_blockers"]
    assert observed["generation_provider_calls"] == 0


@pytest.mark.parametrize("kind", ["pool", "accepted", "bundle"])
def test_text_and_existing_bundle_ceilings_refuse_without_clipping_or_registration(kind):
    from app.generation import bounded_context_action as action

    case = copy.deepcopy(CASES[0])
    row = case["rows"][0]
    if kind == "pool":
        case["rows"] = [{**row, "chunk_id": "large-" + str(i), "full_text": row["full_text"] + "\n\n" + "z" * 10000}
                        for i in range(7)]
    elif kind == "accepted":
        row["full_text"] += "\n\n" + "z" * action.MAX_ADDED_CHARS
    else:
        p = case["parent"]
        e = p["evidence"][0]
        size = action._bundle_bytes(p["question"], p["evidence"])
        e["text"] += "\n\n" + "z" * (action.MAX_BYTES - size - 50)
        p["sources"]["chunks"][e["chunk_id"]]["text"] = e["text"]
    result, _, loader, registrar = run(case)
    assert result["stop_reason"] == {"pool": "candidate_text_budget_exceeded", "accepted": "accepted_text_budget_exceeded",
                                     "bundle": "candidate_bundle_over_budget"}[kind]
    assert loader.call_count == 1 and registrar.call_count == 0
    assert result["added_evidence"] is None


@pytest.mark.parametrize("kind", ["text", "foreign", "diagnostic", "layer"])
def test_registry_integrity_errors_are_not_missing_science(kind):
    def altered(source):
        result = registry(source)
        if kind == "text":
            result["chunks"][source.chunk_id]["text"] += " changed"
        elif kind == "foreign":
            result["chunks"]["foreign"] = copy.deepcopy(result["chunks"][source.chunk_id])
        elif kind == "diagnostic":
            result["diagnostics"] = [{"state": "unresolved"}]
        else:
            result["chunks"][source.chunk_id]["text_layer"] = result["chunk_layers"][source.chunk_id] = "ocr"
        return result

    with pytest.raises(ValueError):
        run(register=altered)


@pytest.mark.parametrize("stage", ["loader", "registrar"])
def test_callback_errors_propagate_without_retry_or_false_context_absence(stage):
    from app.generation.bounded_context_action import run_context_action

    loader = Mock(side_effect=RuntimeError("declared failure")) if stage == "loader" else Mock(
        return_value=[SearchResult(**r) for r in CASES[0]["rows"]])
    registrar = Mock(side_effect=RuntimeError("declared failure"))
    with pytest.raises(RuntimeError, match="declared failure"):
        run_context_action(packet(CASES[0]), loader, registrar)
    assert loader.call_count == 1 and registrar.call_count == int(stage == "registrar")


@pytest.mark.parametrize("change", ["row", "registry", "budget", "count", "input", "after_map", "adapter", "reason",
    "event", "root", "code", "result_id", "extra_field"])
def test_capsule_and_journal_replay_rejects_tampering(change):
    from app.generation.bounded_context_action import validate_context_result

    result, original, _, _ = run()
    if change == "row":
        result["observations"]["candidate_rows"][0]["full_text"] += " altered"
    elif change == "registry":
        result["observations"]["added_registry"]["chunks"].clear()
    elif change == "budget":
        result["budgets"]["accepted_raw_chunks"] = 2
    elif change == "count":
        result["consumed"]["additional_lookup_calls"] = 0
    elif change == "input":
        result["input_packet"]["content"]["claims"] = ["invented"]
    elif change == "after_map":
        result["after_requirements"]["requirements"][-1]["state"] = "scientifically_confirmed"
    elif change == "adapter":
        result["candidate_map_input_adapter"]["blocking_reasons"] = []
    elif change == "reason":
        result["stop_reason"] = "approved"
    elif change == "event":
        result["journal"]["events"].reverse()
    elif change == "root":
        result["journal"]["parent_root_hash"] = "0" * 64
    elif change == "code":
        result["code_bindings"][next(iter(result["code_bindings"]))] = "0" * 64
    elif change == "result_id":
        result["result_id"] = "0" * 64
    else:
        result["approved"] = True
    with pytest.raises(ValueError):
        validate_context_result(result, original)


def test_no_implicit_second_step_and_no_mutation_of_module_budgets():
    from app.generation import bounded_context_action as action

    result, _, loader, registrar = run()
    result["budgets"]["accepted_raw_chunks"] = 99
    assert action.BUDGETS["accepted_raw_chunks"] == 1
    with pytest.raises(ValueError, match="implicit continuation"):
        action.run_context_action(result, loader, registrar)
    assert loader.call_count == 1 and registrar.call_count == 1


def test_sql_preserves_all_recorded_filters_collection_work_type_layer_window_and_sentinel():
    from app.generation.bounded_context_action import load_context_rows

    statements = []

    class Session:
        def execute(self, statement):
            statements.append(statement)
            return []

    article, library = UUID(int=1), UUID(int=2)
    filters = SearchFilters.normalize(article_id=article, library_source_id=library, doi="10/declared", year_from=2000,
        year_to=2026, journal="Journal", source_type="main_text", text_layer="original", tag_type="topic", tag_value="electrolytes")
    load_context_rows(Session(), {"question": "query", "collection": "restricted", "article_id": str(article),
        "source_type": "main_text", "text_layer": "original", "page_start_min": 2, "page_end_max": 3, "filters": filters.as_metadata()})
    sql = str(statements[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    for value in ("restricted", str(article), str(library), "10/declared", "2000", "2026", "journal", "main_text", "original",
                  "topic", "electrolytes", "LIMIT 13", "chunks.page_start >= 2", "chunks.page_end <= 3"):
        assert value in sql


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.generation import context_action_routes as routes
    from app.main import app

    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = lambda: object()
    case = copy.deepcopy(CASES[0])

    def prepared(session, request):
        case["request_scope"] = request.model_dump(mode="json")
        return packet(case)

    monkeypatch.setattr(routes, "prepare_packet", prepared)
    loader = Mock(return_value=[SearchResult(**r) for r in case["rows"]])
    registrar = Mock(side_effect=lambda session, settings, sources: registry(sources[0]))
    monkeypatch.setattr(routes, "load_context_rows", loader)
    monkeypatch.setattr(routes, "collect_sources", registrar)
    try:
        with TestClient(app) as client:
            yield client, loader, registrar
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_actual_API_UI_one_lookup_registration_and_readable_before_after(client):
    client, loader, registrar = client
    request = {"question": CASES[0]["parent"]["question"], "library_source_id": str(UUID(int=17)),
               "collection": "selected", "method": "exact"}
    response = client.post("/answer/prepare/requirements/packet/context", json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["stop_reason"] == "bounded_raw_context_added"
    assert response.content == serialize_packet(result)
    assert loader.call_count == 1 and registrar.call_count == 1
    assert loader.call_args.args[1]["collection"] == "selected"
    assert loader.call_args.args[1]["filters"]["library_source_id"] == str(UUID(int=17))
    page = client.post("/ui/answer/prepare/requirements/packet/context", data=request)
    assert page.status_code == 200 and "Один raw-контекст добавлен" in page.text
    assert "Научная поддержка не оценена" in page.text and "Автоматического продолжения нет" in page.text
    assert "Полный raw-текст без переписывания" in page.text
    assert loader.call_count == 2 and registrar.call_count == 2


@pytest.mark.parametrize("extra", [{"packet": {}}, {"rows": []}, {"generate": True}, {"action": "other"}, {"library_source_id": "bad"}])
def test_client_cannot_inject_sources_packet_or_other_action(client, extra):
    client, loader, registrar = client
    result = client.post("/answer/prepare/requirements/packet/context", json={"question": CASES[0]["parent"]["question"], **extra})
    assert result.status_code == 422
    loader.assert_not_called()
    registrar.assert_not_called()


def test_UI_explicit_step_and_library_cookie_are_preserved(client):
    client, loader, _ = client
    selected = str(UUID(int=18))
    client.cookies.set("ariadne_library_id", selected)
    page = client.get("/ui/answer/prepare/requirements/packet/context", params={"question": "<script>bad</script>"})
    assert page.status_code == 200 and selected in page.text
    assert "<script>bad</script>" not in page.text and "&lt;script&gt;bad&lt;/script&gt;" in page.text
    assert "Выполнить один ограниченный шаг" in page.text
    loader.assert_not_called()
