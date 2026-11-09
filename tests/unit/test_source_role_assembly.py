"""Finite labelled-role assembly, source integrity and actual service controls."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from app.generation import answer_facts, service
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError, ProviderResult
from app.retrieval.search import SearchResponse, SearchResult
from scripts import gigachat_answer_smoke as files

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "output/source_role_assembly_20261109/controls_v01.json").read_bytes())


def assemble(case):
    from app.generation.source_role_assembly import prepare
    return prepare(case["question"], [Evidence(**e) for e in case["sources"]], case["reference"], case["layers"])


@pytest.mark.parametrize("case", DATA["constructed"] + [DATA["real"]], ids=lambda c: c["id"])
def test_declared_source_scope_label_identity_and_ambiguity(case):
    result = assemble(case)
    assert result.eligible == case["expected_complete"], result.metadata()
    if result.eligible:
        records = answer_facts.selection_records(result.evidence)
        assert list(records) == ["F1", "F2", "F3"]
        assert result.assembly["label"] == "MIX-A"
        for raw, derived in zip(result.display, result.evidence, strict=True):
            answer_facts.verify_raw_binding(derived.text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
                                           citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)
        assert [r["recipe"] for r in records.values()] == ["composition", "capacity", "coulombic"]


@pytest.mark.parametrize("mode", ["complete", "abstain", "invalid"])
@pytest.mark.parametrize("http", [False, True])
def test_actual_service_and_http_selects_all_ids_or_abstains(mode, http):
    from sqlalchemy.engine import Engine

    case = DATA["constructed"][0]
    settings, observed = files.configure(), []
    retrieval = SearchResponse(query=case["question"], metadata={"explicit_source_reference": case["reference"]},
        results=[SearchResult(e["article_id"], e["chunk_id"], e["title"], e["doi"], e["page_start"], e["page_end"],
            e["source_type"], e["text"], 0.8, "constructed", full_text=e["text"], text_layer="original") for e in case["sources"]])

    class Synthetic:
        def generate(self, question, evidence, **kwargs):
            observed.extend(evidence)
            records = answer_facts.selection_records(evidence)
            chosen = [GeneratedClaim(k, [r["citation_id"]]) for k, r in records.items()]
            if mode == "invalid":
                chosen[-1] = replace(chosen[-1], text="F999")
            return ProviderResult(mode != "abstain", chosen if mode != "abstain" else [], "SYNTHETIC_ASSEMBLY", None)

    with patch.object(service, "search_chunks", return_value=retrieval), \
            patch.object(service, "build_answer_provider", return_value=Synthetic()), \
            patch.object(Engine, "connect", side_effect=AssertionError("Offline assembly controls forbid DB")):
        if http:
            from fastapi.testclient import TestClient

            from app.core.config import get_settings
            from app.db.session import get_session
            from app.main import app

            old = dict(app.dependency_overrides)

            def no_session():
                yield None

            app.dependency_overrides[get_settings] = lambda: settings
            app.dependency_overrides[get_session] = no_session
            try:
                with TestClient(app) as client:
                    response = client.post("/answer", json={"question": case["question"], "answer_language": "ru"})
                assert response.status_code == (502 if mode == "invalid" else 200), response.text
                body = response.json()
            finally:
                app.dependency_overrides.clear()
                app.dependency_overrides.update(old)
        elif mode == "invalid":
            with pytest.raises(GenerationOutputError):
                service.answer_question(None, settings, case["question"], answer_language="ru")
            return
        else:
            body = service.answer_response_to_dict(service.answer_question(None, settings, case["question"], answer_language="ru"))
    assert observed
    if mode != "invalid":
        assert body["status"] == ("answered" if mode == "complete" else "insufficient_evidence")
        assert body["metadata"]["source_facts"]["assembly"]["version"] == "source_role_assembly_v0.1"
        assert body["metadata"]["source_facts"]["active"]


@pytest.mark.parametrize("mode", ["label", "marker", "question", "layer", "reference", "record", "drop_manifest", "drop_parent"])
def test_assembly_contract_is_recomputed_as_a_complete_graph(mode):
    result = assemble(DATA["constructed"][0])
    assert result.eligible
    selected = list(result.evidence)
    if mode == "drop_parent":
        selected.pop()
    else:
        p = json.loads(selected[-1].text)
        if mode == "label":
            p["assembly"]["label"] = "MIX-B"
        elif mode == "marker":
            p["assembly"]["bindings"][0]["marker"]["start"] += 1
        elif mode == "question":
            p["assembly"]["question"] += " при температуре 17 градусов"
        elif mode == "layer":
            p["assembly"]["layers"]["constructed-3"] = "ocr"
        elif mode == "reference":
            p["assembly"]["reference"]["resolved"] = False
        elif mode == "record":
            p["records"][0]["facts"][0]["value"]["text"] = "99"
        else:
            p.pop("assembly")
        selected[-1] = replace(selected[-1], text=json.dumps(p))
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records(selected)


def test_actual_native_includes_exact_marker_quotes_and_unknowns():
    from app.generation.gigachat import GigaChatAnswerProvider

    result = assemble(DATA["constructed"][0])
    records = answer_facts.selection_records(result.evidence)
    client = GigaChatAnswerProvider(credentials="offline", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                   timeout_seconds=120, max_tokens=1200)
    observed = []

    def post(url, raw, authorization, *, oauth=False):
        if oauth:
            return b'{"access_token":"offline"}'
        body = json.loads(raw)
        rows = json.loads(body["messages"][-1]["content"].split("Source-bound records:\n", 1)[1])
        observed.extend(rows)
        assert len(rows) == 3
        for row in rows:
            parent = next(e for e in result.display if e.citation_id == row["citation_id"])
            assert row["source_role_assembly"]["label"] == "MIX-A"
            assert row["source_role_assembly"]["source_marker_quote"] in parent.text
            assert all(f["source_quote"] in parent.text for f in row["source_bound_facts"])
        content = {"answerable": True, "claims": [{"text": k, "citation_ids": [r["citation_id"]]} for k, r in records.items()]}
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
                          "content": json.dumps(content)}}]}).encode()

    client._post = post
    reply = client.generate(DATA["constructed"][0]["question"], result.evidence)
    assert len(observed) == 3
    assert len(answer_facts.resolve_selections(reply.claims, result.evidence)) == 3


@pytest.mark.parametrize("guard", ["required_concept", "required_relation"])
def test_complete_assembly_does_not_bypass_required_concepts_or_relations(guard):
    case = DATA["constructed"][0]
    retrieval = SearchResponse(query=case["question"], metadata={"explicit_source_reference": case["reference"]},
        results=[SearchResult(e["article_id"], e["chunk_id"], e["title"], e["doi"], e["page_start"], e["page_end"],
            e["source_type"], e["text"], 0.8, "constructed", full_text=e["text"], text_layer="original") for e in case["sources"]])
    original = service.assess_evidence_adequacy

    def assess(*args, **kwargs):
        value = original(*args, **kwargs)
        if guard == "required_concept":
            return replace(value, required_concepts=replace(value.required_concepts, missing=["constructed_missing"]),
                           adequate=False, reason="missing_required_concepts")
        return replace(value, relation_requirements={**value.relation_requirements, "missing": ["constructed_missing"]},
                       adequate=False, reason="missing_required_relation")

    class Forbidden:
        def generate(self, *args, **kwargs):
            pytest.fail("Incomplete required coverage must refuse before provider")

    with patch.object(service, "search_chunks", return_value=retrieval), patch.object(service, "assess_evidence_adequacy", assess):
        result = service.answer_question(None, files.configure(), case["question"], answer_language="ru", provider=Forbidden())
    assert result.status == "insufficient_evidence"
    assert not result.metadata["source_facts"]["active"]


@pytest.mark.parametrize("change", ["non_dict_layers", "non_string_question", "bad_json", "missing_context", "mixed_type"])
def test_malformed_payloads_fail_with_explicit_generation_error(change):
    result = assemble(DATA["constructed"][0])
    selected = list(result.evidence)
    p = json.loads(selected[0].text)
    if change == "non_dict_layers":
        p["assembly"]["layers"] = []
    elif change == "non_string_question":
        p["assembly"]["question"] = []
    elif change == "missing_context":
        p.pop("assembly")
    elif change == "mixed_type":
        selected[0] = replace(selected[0], source_type="main_text")
    if change != "mixed_type":
        selected[0] = replace(selected[0], text="invalid" if change == "bad_json" else json.dumps(p))
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records(selected)


@pytest.mark.parametrize("language", ["ru", "en"])
def test_existing_complete_path_and_english_requests_do_not_enter_assembly(language):
    case = DATA["constructed"][0]
    src = case["sources"][0]
    text = src["text"].split("\n\nKEYWORDS:")[0] + " " + " ".join(
        e["text"].split("Electrolyte MIX-A.\n")[1].strip() for e in case["sources"][1:]) + "\nKEYWORDS: control.\n"
    row = SearchResult(src["article_id"], src["chunk_id"], src["title"], None, 1, 1, "main_text", text, 0.8,
                       "constructed", full_text=text, text_layer="original")

    class Synthetic:
        def generate(self, question, evidence, **kwargs):
            if language == "en":
                return ProviderResult(False, [], "SYNTHETIC_LEGACY_ABSTENTION", None)
            return ProviderResult(True, [GeneratedClaim(k, [r["citation_id"]])
                for k, r in answer_facts.selection_records(evidence).items()], "SYNTHETIC_LEGACY_FACTS", None)

    with patch.object(service, "search_chunks", return_value=SearchResponse(case["question"], [row],
                      {"explicit_source_reference": case["reference"]})), \
            patch.object(service, "prepare_source_assembly", side_effect=AssertionError("Legacy/English must not enter assembly")):
        result = service.answer_question(None, files.configure(), case["question"], answer_language=language, provider=Synthetic())
    assert "assembly" not in result.metadata["source_facts"]
    assert result.status == ("answered" if language == "ru" else "insufficient_evidence")


def test_ui_displays_literal_cross_section_marker_with_exact_source_quotes():
    from app.ui import _prepared_statement_text

    bundle = assemble(DATA["constructed"][0])
    for derived in bundle.evidence:
        text = _prepared_statement_text(derived.text, answer_facts.SOURCE_TYPE)
        assert "Текстовая связь разделов" in text and "MIX-A" in text
        assert "Electrolyte MIX-A." in text
        assert "Условия и значения между операциями не переносятся" in text
        assert "source_role_assembly_v0.1" not in text


@pytest.mark.parametrize("include_methods", [False, True])
def test_real_source_type_conflict_and_missing_label_are_distinct(include_methods):
    case = DATA["real"]
    if include_methods:
        assert case["sources"][1]["source_type"] == "figure_caption"
    else:
        sources = [e for i, e in enumerate(case["sources"]) if i != 1]
        case = {**case, "sources": sources, "layers": {e["chunk_id"]: case["layers"][e["chunk_id"]] for e in sources}}
    result = assemble(case)
    assert not result.eligible
    assert result.reason == ("assembly_source_scope_unresolved" if include_methods
                             else "assembly_missing_explicit_role_composition")
