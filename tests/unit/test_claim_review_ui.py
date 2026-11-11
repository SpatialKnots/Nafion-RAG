"""Explicit inspection must preserve provenance, unknowns, scope and stale-snapshot errors."""

import json
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.generation.answer_evidence_packet import build_packet, serialize_packet
from app.generation.answer_requirements import build_requirements
from app.generation.claim_checks import fact_assertion
from app.generation.claim_review import build_review, render_catalog, render_review, validate_review
from app.generation.claim_review_routes import PATH, UI_PATH
from app.generation.preparation_routes import PreparationRequest
from tests.unit.test_answer_evidence_packet import CASES, with_page_registry, wrapped
from tests.unit.test_claim_checks import inputs


def claim(packet, property="capacity_retention"):
    row = next(f for f in packet["content"]["facts"] if f["fact"]["property"] == property)
    return {"id": "explicit_assertion", "kind": "fact", "fact_ref": row["id"], "assertion": fact_assertion(row["fact"])}


def form_scope(**extra):
    return {"question": CASES[0]["parent"]["question"], "method": "exact", "collection": "offline",
            "top_k": 2, "answer_style": "mini_review", "answer_language": "ru", "library_source_id": str(UUID(int=16)), **extra}


def test_renderer_pairs_readable_assertion_with_exact_quote_diff_unknowns_and_baseline():
    parent, packet = inputs("exposed_real_full_packet")
    row = next(f for f in packet["content"]["facts"] if f["fact"]["unknown_fields"])
    assertion = {"id": "explicit_assertion", "kind": "fact", "fact_ref": row["id"], "assertion": fact_assertion(row["fact"])}
    assertion["assertion"]["sample"]["text"] = "WRONG_CELL"
    review = build_review(packet, [assertion], expected_packet_id=packet["packet_id"])
    html = render_review(review, packet, expected_review_id=review["review_id"])
    assert "WRONG_CELL" in html and "Расхождения полей" in html
    assert "Температура измерения" in html and "Неизвестные поля источника" in html
    assert "Источник и точные цитаты" in html and "<mark>" in html
    assert "Поля отличаются от записи источника" in html and "Научная достоверность" in html
    assert "Точная страница цитаты не установлена" in html
    assert review["report"]["stop"]["baseline"]["baseline_blocking_reasons"] == parent["preparation"]["blocking_reasons"]
    assert review["human_reviews"] == []


@pytest.mark.parametrize("case,expected", [("conflicting_value", "Варианты источников конфликтуют"),
                                          ("missing_identity", "Связь ролей не установлена")])
def test_renderer_keeps_ambiguity_and_unresolved_role_identity(case, expected):
    _, packet = inputs(case)
    assertion = claim(packet, "coulombic_efficiency" if case == "conflicting_value" else "capacity_retention")
    review = build_review(packet, [assertion], expected_packet_id=packet["packet_id"])
    assert expected in render_review(review, packet, expected_review_id=review["review_id"])


def test_empty_input_is_no_claims_and_catalog_is_not_an_answer_or_automatic_assertion():
    _, packet = inputs()
    review = build_review(packet, [], expected_packet_id=packet["packet_id"])
    html = render_review(review, packet, expected_review_id=review["review_id"])
    assert "Утверждения не переданы" in html and "data-claim-card" not in html
    catalog = render_catalog(packet)
    assert "а не проверенные утверждения ответа" in catalog
    assert review["report"]["claims"] == [] and review["report"]["stop"]["reason"] == "no_claims"


def test_canonical_capsule_roundtrip_preserves_rendered_fields_and_technical_details():
    _, packet = inputs()
    review = build_review(packet, [claim(packet)], expected_packet_id=packet["packet_id"])
    restored = json.loads(serialize_packet(review))
    assert render_review(restored, packet, expected_review_id=review["review_id"]) == render_review(
        review, packet, expected_review_id=review["review_id"])
    assert render_catalog(json.loads(serialize_packet(packet))) == render_catalog(packet)


@pytest.mark.parametrize("change", ["claims", "source", "result", "code", "human", "review_pin", "packet_pin"])
def test_capsule_reconstruction_rejects_forgery_and_staleness(change):
    from app.generation import claim_review as module

    _, packet = inputs()
    claims = [claim(packet)]
    review = build_review(packet, claims, expected_packet_id=packet["packet_id"])
    packet_id, review_id = packet["packet_id"], review["review_id"]
    if change == "claims":
        claims[0]["assertion"]["epistemic_status"] = "approved"
    elif change == "source":
        review["packet"]["content"]["sources"][0]["raw_text"] += "changed"
    elif change == "result":
        review["report"]["results"][0]["scientific_validity"]["status"] = "approved"
    elif change == "human":
        review["human_reviews"] = [{"status": "approved"}]
    elif change == "review_pin":
        review_id = "0" * 64
    elif change == "packet_pin":
        packet_id = "0" * 64
    else:
        with patch.object(module, "code_bindings", return_value={"changed": "0" * 64}), pytest.raises(ValueError):
            validate_review(review, packet, claims, expected_packet_id=packet_id, expected_review_id=review_id)
        return
    with pytest.raises(ValueError):
        validate_review(review, packet, claims, expected_packet_id=packet_id, expected_review_id=review_id)


def test_exact_registered_page_maps_to_page_link_without_reading_embedded_paths():
    parent = with_page_registry()
    packet = build_packet(parent)
    fact = packet["content"]["facts"][0]
    assertion = {"id": "x", "kind": "fact", "fact_ref": fact["id"], "assertion": fact_assertion(fact["fact"])}
    review = build_review(packet, [assertion], expected_packet_id=packet["packet_id"])
    html = render_review(review, packet, expected_review_id=review["review_id"])
    assert "Цитата точно сопоставлена одной странице" in html
    assert "#page=1" in html and "NEVER_OPEN_THIS_DECLARED_PATH.pdf" not in html


def test_ocr_source_links_do_not_claim_original_text_mapping():
    parent = with_page_registry()
    p = parent["preparation"]
    from app.records.schema import source_identity

    for chunk in p["sources"]["chunks"].values():
        chunk["text_layer"] = "ocr"
    p["sources"]["chunk_layers"] = {k: "ocr" for k in p["sources"]["chunk_layers"]}
    for page in p["sources"]["pages"].values():
        page["text_layer"] = "ocr"
        page["region_id"] = source_identity(page)
    parent["requirements"] = build_requirements(p)
    packet = build_packet(parent)
    html = render_catalog(packet)
    assert "layer=ocr#page=1" in html and "layer=original#page=1" in html
    assert "Совпадение OCR-текста с текстом оригинального PDF отдельно не проверялось" in html


def test_source_and_assertion_markup_is_escaped_in_text_and_attributes():
    parent, _ = inputs()
    source = parent["preparation"]["evidence"][0]
    source["title"] = '<img src=x onerror="bad()">'
    source["text"] += "\n<script>bad()</script>"
    parent["preparation"]["sources"]["chunks"][source["chunk_id"]]["text"] = source["text"]
    parent["requirements"] = build_requirements(parent["preparation"])
    packet = build_packet(parent)
    assertion = claim(packet)
    assertion["id"] = '<script>claim()</script>'
    assertion["assertion"]["sample"]["text"] = '<img src=x onerror="claim()">'
    review = build_review(packet, [assertion], expected_packet_id=packet["packet_id"])
    html = render_review(review, packet, expected_review_id=review["review_id"])
    assert "<img src=x" not in html and "<script>" not in html
    assert "&lt;img" in html and "&lt;script&gt;" in html


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.generation import claim_review_routes as routes
    from app.main import app

    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = lambda: object()
    def prepared(session, request):
        parent = wrapped()
        parent["requirements"] = build_requirements(parent["preparation"], request.model_dump(mode="json"))
        return build_packet(parent)

    prepare = Mock(side_effect=prepared)
    monkeypatch.setattr(routes, "prepare_packet", prepare)
    forbidden = Mock(side_effect=AssertionError("No provider or context action"))
    monkeypatch.setattr("app.generation.service.build_answer_provider", forbidden)
    monkeypatch.setattr("app.generation.context_action_routes.prepare_context_action", forbidden)
    try:
        with TestClient(app) as c:
            yield c, prepare, forbidden
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def request_data(prepare, **extra):
    scope = form_scope()
    packet = prepare(object(), PreparationRequest.model_validate(scope))
    prepare.reset_mock()
    return {**scope, "expected_packet_id": packet["packet_id"], "claims": [claim(packet)], **extra}


def test_explicit_api_reprepares_once_keeps_all_options_and_returns_canonical_download(client):
    c, prepare, forbidden = client
    data = request_data(prepare)
    response = c.post(PATH, json=data)
    assert response.status_code == 200, response.text
    review = response.json()
    assert response.content == serialize_packet(review) and "attachment" in response.headers["content-disposition"]
    prepare.assert_called_once()
    sent = prepare.call_args.args[1].model_dump(mode="json")
    assert sent == PreparationRequest.model_validate(form_scope()).model_dump(mode="json")
    validate_review(review, review["packet"], data["claims"], expected_packet_id=data["expected_packet_id"],
                    expected_review_id=review["review_id"])
    forbidden.assert_not_called()


@pytest.mark.parametrize("extra", [{"packet": {}}, {"parent": {}}, {"report": {}}, {"sources": []}, {"path": "private"},
                                   {"generate": True}, {"expected_packet_id": "bad"}, {"claims": [{"kind": "prose"}]},
                                   {"library_source_id": "bad"}])
def test_injected_or_invalid_api_requests_never_prepare_sources(client, extra):
    c, prepare, _ = client
    data = request_data(prepare, **extra)
    response = c.post(PATH, json=data)
    assert response.status_code == 422, response.text
    prepare.assert_not_called()


def test_duplicate_claim_ids_rejected_before_preparation(client):
    c, prepare, _ = client
    data = request_data(prepare)
    data["claims"] *= 2
    assert c.post(PATH, json=data).status_code == 422
    prepare.assert_not_called()


@pytest.mark.parametrize("raw,status", [('\u007b"claims":[],"claims":[]}', 400),
                                       ('{"question":"x","top_k":NaN}', 400), ('{bad', 400), ('x' * 300001, 413)],
                         ids=["duplicate_key", "nonfinite", "malformed", "request_budget"])
def test_duplicate_keys_nonfinite_malformed_and_large_body_fail_before_prepare(client, raw, status):
    c, prepare, _ = client
    assert c.post(PATH, content=raw, headers={"Content-Type": "application/json"}).status_code == status
    prepare.assert_not_called()


def test_stale_packet_returns_conflict_without_retry_or_result(client):
    c, prepare, forbidden = client
    data = request_data(prepare, expected_packet_id="0" * 64)
    response = c.post(PATH, json=data)
    assert response.status_code == 409 and "Evidence packet changed" in response.text
    prepare.assert_called_once()
    forbidden.assert_not_called()


def test_ui_catalog_does_not_automatically_check_assertions_and_preserves_scope(client):
    c, prepare, forbidden = client
    response = c.post(UI_PATH, data={**form_scope(), "intent": "prepare"})
    assert response.status_code == 200, response.text
    assert "data-claim-catalog" in response.text and "data-claim-review" not in response.text
    assert 'name="claims_json"' in response.text and ">[]</textarea>" in response.text
    assert 'value="mini_review" selected' in response.text and 'value="ru" selected' in response.text
    assert 'name="collection" value="offline"' in response.text and str(UUID(int=16)) in response.text
    prepare.assert_called_once()
    forbidden.assert_not_called()


def test_ui_check_download_and_error_preserve_explicit_input(client):
    c, prepare, forbidden = client
    data = request_data(prepare)
    form = {**form_scope(), "expected_packet_id": data["expected_packet_id"], "claims_json": json.dumps(data["claims"]), "intent": "check"}
    result = c.post(UI_PATH, data=form)
    assert result.status_code == 200, result.text
    assert "data-claim-review" in result.text and "Утверждение explicit_assertion" in result.text
    downloaded = c.post(UI_PATH, data={**form, "intent": "download"})
    assert downloaded.status_code == 200 and downloaded.content == serialize_packet(downloaded.json())
    stale = c.post(UI_PATH, data={**form, "expected_packet_id": "0" * 64})
    assert stale.status_code == 409 and "data-claim-review" not in stale.text
    assert "explicit_assertion" in stale.text and "Evidence packet changed" in stale.text
    forbidden.assert_not_called()


@pytest.mark.parametrize("bad", ['[{"id":"x","id":"y"}]', '<script>bad()</script>', '[NaN]'])
def test_invalid_ui_claim_json_retained_escaped_without_preparing(client, bad):
    c, prepare, _ = client
    response = c.post(UI_PATH, data={**form_scope(), "intent": "check", "expected_packet_id": "0" * 64, "claims_json": bad})
    assert response.status_code == 400 and "data-claim-review" not in response.text
    assert "<script>bad()</script>" not in response.text
    assert 'name="claims_json"' in response.text
    prepare.assert_not_called()


def test_ui_get_and_navigation_use_library_cookie_and_escape_question(client):
    c, prepare, _ = client
    c.cookies.set("ariadne_library_id", str(UUID(int=99)))
    page = c.get(UI_PATH, params={"question": "<script>bad()</script>"})
    assert page.status_code == 200 and str(UUID(int=99)) in page.text
    assert "<script>bad()</script>" not in page.text and "&lt;script&gt;" in page.text
    original = c.get("/ui/answer/prepare", params={"library_source_id": str(UUID(int=99))})
    assert UI_PATH + "?library_source_id=" + str(UUID(int=99)) in original.text
    c.cookies.set("ariadne_library_id", "invalid")
    assert c.get(UI_PATH).status_code == 200
    prepare.assert_not_called()


def test_ui_rejects_duplicate_or_foreign_form_fields_and_wrong_media_type(client):
    c, prepare, _ = client
    duplicate = c.post(UI_PATH, content="question=x&question=y", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert duplicate.status_code == 400
    assert c.post(UI_PATH, data={**form_scope(), "packet": "forged"}).status_code == 400
    assert c.post(UI_PATH, json=form_scope()).status_code == 415
    assert c.post(PATH, data=form_scope()).status_code == 415
    prepare.assert_not_called()


def test_bad_server_scope_is_not_used_as_current_packet(client, monkeypatch):
    c, prepare, _ = client
    from app.generation import claim_review_routes as routes

    data = request_data(prepare)
    packet = prepare(object(), PreparationRequest.model_validate(form_scope()))
    prepare.reset_mock()
    packet["content"]["request_scope"]["collection"] = "other"
    monkeypatch.setattr(routes, "prepare_packet", Mock(return_value=packet))
    response = c.post(PATH, json=data)
    assert response.status_code == 400 and "scope differs" in response.text
