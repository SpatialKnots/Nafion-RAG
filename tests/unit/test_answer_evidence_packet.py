"""Canonical diagnostic snapshots and journal replay, never scientific acceptance."""

import copy
import json
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.generation.answer_requirements import build_requirements
from app.records.schema import source_identity, text_hash

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "output/answer_requirements_20261109/controls_v01.json").read_bytes())


def wrapped(parent=None):
    p = copy.deepcopy(parent or CASES[0]["parent"])
    return {"version": "answer_requirements_preparation_v0.1", "preparation": p,
            "requirements": build_requirements(p), "generation_performed": False,
            "external_request_constructed": False, "network_ready": False}


def build(parent=None):
    from app.generation.answer_evidence_packet import build_packet

    return build_packet(parent or wrapped())


def with_page_registry():
    p = copy.deepcopy(CASES[0]["parent"])
    source = p["evidence"][0]
    text = "Prefix Δ.\n" + source["text"] + "\nUnselected suffix."
    region = {"article_id": source["article_id"], "original_pdf_path": "NEVER_OPEN_THIS_DECLARED_PATH.pdf",
        "original_pdf_sha256": "a" * 64, "page_number": source["page_start"], "text_layer_id": str(UUID(int=70)),
        "text_layer": "original", "layer_pdf_path": "NEVER_OPEN_THIS_DECLARED_PATH.pdf", "layer_pdf_sha256": "a" * 64,
        "page_text": text, "page_text_sha256": text_hash(text), "start": 0, "end": len(text),
        "quote": text, "quote_sha256": text_hash(text), "selection_basis": "retrieval",
        "selection_note": "Constructed page registry; not a real PDF hash or file"}
    region["region_id"] = source_identity(region)
    p["sources"]["pages"] = {"declared": region}
    return wrapped(p)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_packet_keeps_every_parent_and_replays_declared_requirement_controls(case):
    from app.generation.answer_evidence_packet import serialize_packet, validate_packet

    parent = wrapped(case["parent"])
    before = copy.deepcopy(parent)
    packet = build(parent)
    assert parent == before and packet["content"]["parent"] == parent
    assert packet["content"]["claims"] == []
    assert packet["scientific_support"] == "not_evaluated" and not packet["network_ready"]
    assert packet["content"]["stop"]["baseline_blocking_reasons"] == parent["preparation"]["blocking_reasons"]
    assert serialize_packet(packet) == serialize_packet(build(parent))
    validate_packet(packet, parent, expected_packet_id=packet["packet_id"])
    assert len(packet["journal"]["events"]) == 3 + len(parent["requirements"]["requirements"])
    assert all(e["actor_kind"] == "deterministic_system" for e in packet["journal"]["events"])
    assert all(e["scientific_support"] == "not_evaluated" for e in packet["journal"]["events"])


def test_indexes_have_exact_raw_anchors_and_fact_arithmetic_references():
    packet = build()
    content = packet["content"]
    sources = {s["id"]: s for s in content["sources"]}
    anchors = {a["id"]: a for a in content["anchors"]}
    facts = {f["id"]: f for f in content["facts"]}
    assert sources and anchors and facts and content["transformations"]
    for item in anchors.values():
        raw = sources[item["source_ref"]]["raw_text"]
        a = item["anchor"]
        assert raw[a["start"]:a["end"]] == a["text"] and text_hash(raw) == a["raw_chunk_sha256"]
        assert item["page_binding"] == "exact_page_mapping_unresolved"
    for fact in facts.values():
        assert fact["support_ref"] in anchors and fact["source_ref"] in sources
        assert fact["fact"]["scientific_ownership_verified"] is False
    for arithmetic in content["transformations"]:
        assert set(arithmetic["input_fact_refs"]) <= set(facts)
        assert arithmetic["arithmetic"]["origin"] == "system_arithmetic"
    assert not content["pages"]


def test_valid_page_registry_maps_exact_unicode_offsets_without_reading_embedded_paths():
    packet = build(with_page_registry())
    content = packet["content"]
    assert len(content["pages"]) == 1
    mapped = [a for a in content["anchors"] if a["page_spans"]]
    assert mapped
    page_text = content["parent"]["preparation"]["sources"]["pages"]["declared"]["page_text"]
    for anchor in mapped:
        assert anchor["page_binding"] == "exact_single_page_mapping"
        span = anchor["page_spans"][0]
        assert page_text[span["start"]:span["end"]] == anchor["anchor"]["text"]
        assert span["page_ref"] == content["pages"][0]["id"]
    assert content["pages"][0]["pdf_integrity"] == "declared_snapshot_not_freshly_read"


def test_cross_page_fact_support_retains_raw_anchor_without_claiming_one_page_mapping():
    parent = with_page_registry()
    p = parent["preparation"]
    e = p["evidence"][0]
    text = e["text"]
    cut = text.index("when charged")
    first = p["sources"]["pages"]["declared"]
    second = copy.deepcopy(first)
    for n, page, body in ((1, first, text[:cut]), (2, second, text[cut:])):
        page.update(page_number=n, text_layer_id=str(UUID(int=70 + n)), page_text=body, page_text_sha256=text_hash(body),
                    start=0, end=len(body), quote=body, quote_sha256=text_hash(body))
        page["region_id"] = source_identity(page)
    p["sources"]["pages"]["second"] = second
    e["page_end"] = p["sources"]["chunks"][e["chunk_id"]]["page_end"] = 2
    parent["requirements"] = build_requirements(p)
    packet = build(parent)
    capacity = next(f for f in packet["content"]["facts"] if f["fact"]["property"] == "capacity_retention")
    support = next(a for a in packet["content"]["anchors"] if a["id"] == capacity["support_ref"])
    assert support["anchor"]["start"] < cut < support["anchor"]["end"]
    assert support["page_spans"] == [] and support["page_binding"] == "exact_page_mapping_unresolved"
    assert any(a["page_spans"] for a in packet["content"]["anchors"])


@pytest.mark.parametrize("change", ["hash", "foreign_page", "wrong_layer", "duplicate_page", "conflicting_pdf"])
def test_invalid_registered_pages_do_not_get_silently_repaired(change):
    parent = with_page_registry()
    region = parent["preparation"]["sources"]["pages"]["declared"]
    if change == "hash":
        region["page_text_sha256"] = "b" * 64
    elif change == "foreign_page":
        region["page_number"] = 99
        region["region_id"] = source_identity(region)
    elif change == "wrong_layer":
        region["text_layer"] = "ocr"
        region["region_id"] = source_identity(region)
    elif change == "duplicate_page":
        parent["preparation"]["sources"]["pages"]["duplicate"] = copy.deepcopy(region)
    else:
        other = copy.deepcopy(region)
        other.update(page_number=3, text_layer_id=str(UUID(int=71)), original_pdf_sha256="b" * 64, layer_pdf_sha256="b" * 64)
        other["region_id"] = source_identity(other)
        parent["preparation"]["sources"]["pages"]["other"] = other
    parent["requirements"] = build_requirements(parent["preparation"])
    with pytest.raises(ValueError):
        build(parent)


@pytest.mark.parametrize("change", ["version", "packet_id", "fact", "arithmetic", "source_ref", "anchor_ref", "missing_anchor",
    "duplicate_source", "missing_event", "reorder_events", "sequence", "event_hash", "event_reason", "previous_event",
    "action_execution", "human_confirmation", "claims", "stop", "root", "extra_field"])
def test_corrupt_packet_or_journal_fails_complete_reconstruction(change):
    from app.generation.answer_evidence_packet import validate_packet

    parent = wrapped()
    packet = build(parent)
    if change == "version":
        packet["version"] = "unknown"
    elif change == "packet_id":
        packet["packet_id"] = "0" * 64
    elif change == "fact":
        packet["content"]["facts"][0]["fact"]["value"]["text"] = "999"
    elif change == "arithmetic":
        packet["content"]["transformations"][0]["arithmetic"]["result"] = "999"
    elif change in {"source_ref", "anchor_ref"}:
        packet["content"]["facts"][0]["source_ref" if change == "source_ref" else "support_ref"] = "foreign"
    elif change == "missing_anchor":
        packet["content"]["anchors"].pop()
    elif change == "duplicate_source":
        packet["content"]["sources"].append(copy.deepcopy(packet["content"]["sources"][0]))
    elif change == "missing_event":
        packet["journal"]["events"].pop()
    elif change == "reorder_events":
        packet["journal"]["events"].reverse()
    elif change == "claims":
        packet["content"]["claims"] = ["invented"]
    elif change == "stop":
        packet["content"]["stop"]["baseline_blocking_reasons"] = []
    elif change == "root":
        packet["journal"]["root_hash"] = "0" * 64
    elif change == "extra_field":
        packet["approval"] = "approved"
    else:
        event = packet["journal"]["events"][2]
        key = {"sequence": "sequence", "event_hash": "event_hash", "event_reason": "reason", "previous_event": "previous_hash",
               "action_execution": "action_executed", "human_confirmation": "actor_kind"}[change]
        event[key] = "invented"
    with pytest.raises(ValueError):
        validate_packet(packet, parent)


@pytest.mark.parametrize("change", ["code", "scope", "blocker", "source", "pinned_id"])
def test_current_context_and_pinned_identity_detect_stale_snapshots(change):
    from app.generation import answer_evidence_packet as module

    parent = wrapped()
    packet = build(parent)
    if change == "code":
        codes = module.code_bindings()
        codes[next(iter(codes))] = "0" * 64
        with patch.object(module, "code_bindings", return_value=codes), pytest.raises(ValueError):
            module.validate_packet(packet, parent)
        return
    if change == "scope":
        parent["requirements"] = build_requirements(parent["preparation"], {"library_source_id": str(UUID(int=15))})
    elif change == "blocker":
        parent["preparation"]["blocking_reasons"].append("new_blocker")
        parent["requirements"] = build_requirements(parent["preparation"])
    elif change == "source":
        e = parent["preparation"]["evidence"][0]
        e["text"] = e["text"].replace("98%", "97%")
        parent["preparation"]["sources"]["chunks"][e["chunk_id"]]["text"] = e["text"]
        parent["requirements"] = build_requirements(parent["preparation"])
    with pytest.raises(ValueError):
        module.validate_packet(packet, parent, expected_packet_id="0" * 64 if change == "pinned_id" else packet["packet_id"])


def test_canonical_export_roundtrip_and_existing_snapshot_never_overwritten(tmp_path):
    from app.generation.answer_evidence_packet import load_packet, save_packet, serialize_packet

    parent, packet = wrapped(), build()
    path = tmp_path / "packet.json"
    save_packet(path, packet, parent)
    original = path.read_bytes()
    assert original == serialize_packet(packet)
    assert load_packet(path, parent, expected_packet_id=packet["packet_id"]) == packet
    with pytest.raises(FileExistsError):
        save_packet(path, packet, parent)
    assert path.read_bytes() == original
    changed = tmp_path / "noncanonical.json"
    changed.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(ValueError):
        load_packet(changed, parent)


def test_builder_never_calls_generation_or_retrieval():
    with patch("app.generation.service.search_chunks", side_effect=AssertionError("No packet retrieval")), \
            patch("app.generation.service.build_answer_provider", side_effect=AssertionError("No packet provider")):
        packet = build()
    assert packet["content"]["stop"]["new_source_actions_executed"] == 0
    assert not packet["content"]["claims"]


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.generation import evidence_packet_routes as routes
    from app.main import app

    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = lambda: object()
    def prepared(session, request):
        result = wrapped()
        result["requirements"] = build_requirements(result["preparation"], request.model_dump(mode="json"))
        return result

    stub = Mock(side_effect=prepared)
    monkeypatch.setattr(routes, "requirements_api", stub)
    try:
        with TestClient(app) as client:
            yield client, stub
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_api_delivers_canonical_download_and_preserves_library_options(client):
    from app.generation.answer_evidence_packet import serialize_packet

    client, stub = client
    request = {"question": CASES[0]["parent"]["question"], "library_source_id": str(UUID(int=16)), "method": "exact", "top_k": 2}
    response = client.post("/answer/prepare/requirements/packet", json=request)
    assert response.status_code == 200, response.text
    assert response.content == serialize_packet(response.json())
    assert "attachment" in response.headers["content-disposition"]
    assert stub.call_args.args[1].library_source_id == UUID(int=16) and stub.call_args.args[1].top_k == 2


@pytest.mark.parametrize("extra", [{"packet": {}}, {"path": "private"}, {"generate": True}, {"top_k": 0}, {"library_source_id": "bad"}])
def test_client_cannot_inject_packet_path_or_execution_request(client, extra):
    client, stub = client
    response = client.post("/answer/prepare/requirements/packet", json={"question": CASES[0]["parent"]["question"], **extra})
    assert response.status_code == 422
    stub.assert_not_called()


def test_ui_exposes_diagnostic_history_and_escapes_untrusted_text(client):
    client, _ = client
    response = client.post("/ui/answer/prepare/requirements/packet", data={"question": CASES[0]["parent"]["question"]})
    assert response.status_code == 200, response.text
    assert "Журнал диагностических наблюдений" in response.text
    assert response.text.count("data-packet-event=") == 7
    assert "не человеческое подтверждение" in response.text
    page = client.get("/ui/answer/prepare/requirements/packet", params={"question": "<script>bad</script>",
        "library_source_id": str(UUID(int=18))})
    assert "<script>bad</script>" not in page.text and "&lt;script&gt;bad&lt;/script&gt;" in page.text
    assert 'action="/ui/answer/prepare/requirements/packet"' in page.text and str(UUID(int=18)) in page.text


def test_packet_renderer_escapes_source_markup():
    from app.generation.evidence_packet_routes import render_packet

    p = copy.deepcopy(CASES[0]["parent"])
    e = p["evidence"][0]
    e["text"] += "\n<script>untrusted</script>"
    p["sources"]["chunks"][e["chunk_id"]]["text"] = e["text"]
    rendered = render_packet(build(wrapped(p)))
    assert "<script>untrusted</script>" not in rendered and "&lt;script&gt;untrusted&lt;/script&gt;" in rendered


def test_actual_preparation_to_packet_keeps_no_generation_boundary(monkeypatch):
    from dataclasses import replace

    from app.generation import preparation, service
    from app.retrieval.search import SearchResponse
    from tests.unit.test_answer_preparation import setup_service
    from tests.unit.test_generation import _search_result, _settings

    real = CASES[0]["parent"]
    session, e, sources = setup_service(monkeypatch, text=real["evidence"][0]["text"],
        authors=[{"name": "Lin"}, {"name": "Zhao"}], year=2020)
    sources["chunks"][e.chunk_id] = {"text": e.text, "article_id": e.article_id, "source_type": e.source_type,
        "page_start": e.page_start, "page_end": e.page_end, "text_layer": sources["chunk_layers"][e.chunk_id]}
    monkeypatch.setattr(preparation, "answer_question", service.answer_question)
    row = replace(_search_result(), article_id=e.article_id, chunk_id=e.chunk_id, page_start=e.page_start,
        page_end=e.page_end, full_text=e.text, snippet=e.text, title=e.title)
    reference = copy.deepcopy(real["baseline_metadata"]["retrieval"]["explicit_source_reference"])
    reference["article_id"] = e.article_id
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: SearchResponse(real["question"], [row],
        {"explicit_source_reference": reference}))
    forbidden = Mock(side_effect=AssertionError("Packet preparation must not load generation provider"))
    monkeypatch.setattr(service, "build_answer_provider", forbidden)
    p = preparation.prepare_answer(session, _settings(), real["question"], answer_language="ru")
    before = copy.deepcopy(p)
    packet = build(wrapped(p))
    assert p == before and len(packet["content"]["pages"]) == 1
    assert packet["content"]["inspection"]["restored_derived_parents"] == 1
    assert packet["content"]["claims"] == []
    forbidden.assert_not_called()
