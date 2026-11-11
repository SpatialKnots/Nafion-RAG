"""Opt-in finite source graph; exposed real source and declared synthetic controls."""

import copy
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
CASES = json.loads((ROOT / "output/methods_identity_bridge_20261109/controls_v02.json").read_bytes())


def assemble(case=None, **kwargs):
    from app.generation.methods_identity import POLICY, prepare

    case = case or CASES[0]
    return prepare(case["question"], [Evidence(**e) for e in case["sources"]], case["reference"], case["layers"],
                   policy=POLICY, **kwargs)


def retrieval(case):
    return SearchResponse(case["question"], [SearchResult(
        e["article_id"], e["chunk_id"], e["title"], e["doi"], e["page_start"], e["page_end"], e["source_type"],
        e["text"], 0.8, "offline_packet", full_text=e["text"], text_layer=case["layers"][e["chunk_id"]])
        for e in case["sources"]], {"explicit_source_reference": case["reference"]})


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_audit_controls_under_explicit_runtime_policy(case):
    bundle = assemble(case)
    assert bundle.eligible == case["expected_candidate"], bundle.metadata()
    if bundle.eligible:
        assert [e.source_type for e in bundle.display] == [s["source_type"] for s in case["sources"]]
        assert len(bundle.evidence) == 3
        records = answer_facts.selection_records(bundle.evidence)
        assert list(records) == ["F1", "F2", "F3"]
        assert bundle.assembly["scientific_ownership_verified"] is False
        assert bundle.assembly["conditions_propagated"] is False
        assert bundle.assembly["explicit_assumption"] == "ordered_parallel_dose_product_lists_not_general_semantic_entailment"
        for raw, derived in zip(bundle.display, bundle.evidence, strict=True):
            answer_facts.verify_raw_binding(derived.text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
                citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)


@pytest.mark.parametrize("change", ["work", "layer", "missing_layer", "duplicate_id", "duplicate_citation", "derived", "caption_result",
    "extra_parent", "missing_parent", "page", "unresolved_reference", "other_reference", "author", "constraint",
    "caption_inside_methods", "alias_outside_methods", "ambiguous_alias", "foreign_capacity", "future_composition",
    "foreign_section", "future_target", "unbounded_abstract"])
def test_new_scope_and_internal_region_controls_abstain(change):
    case = copy.deepcopy(CASES[0])
    a, m, c = case["sources"]
    if change == "work":
        m["article_id"] = "other"
    elif change == "layer":
        case["layers"][m["chunk_id"]] = "ocr"
    elif change == "missing_layer":
        case["layers"].pop(m["chunk_id"])
    elif change == "duplicate_id":
        m["chunk_id"] = a["chunk_id"]
    elif change == "duplicate_citation":
        m["citation_id"] = a["citation_id"]
    elif change in {"derived", "caption_result"}:
        a["source_type"] = "source_fact_derived" if change == "derived" else "figure_caption"
    elif change == "extra_parent":
        case["sources"].append({**m, "chunk_id": "extra", "citation_id": "E99"})
        case["layers"]["extra"] = "original"
    elif change == "missing_parent":
        case["sources"].pop(1)
    elif change == "page":
        m["page_end"] = 0
    elif change == "unresolved_reference":
        case["reference"]["resolved"] = False
    elif change == "other_reference":
        case["reference"]["article_id"] = "other"
    elif change == "author":
        case["question"] = case["question"].replace("Lin", "Smith")
    elif change == "constraint":
        case["question"] += " при температуре 17 градусов"
    elif change == "caption_inside_methods":
        m["text"] = m["text"].replace("In addition,", "Figure 99.\nIn addition,")
    elif change == "alias_outside_methods":
        m["text"] = m["text"].replace("dimethyl carbonate (DMC)", "dimethyl carbonate") + "\ndimethyl carbonate (DMC)"
    elif change == "ambiguous_alias":
        m["text"] = m["text"].replace("In addition,", "dimethyl carbonate (XYZ). In addition,")
    elif change == "foreign_capacity":
        a["text"] = a["text"].replace("Li||LiCoO2 batteries", "Previous work reported that Li||LiCoO2 batteries")
    elif change == "future_composition":
        a["text"] = a["text"].replace("1.2 M LiPF6 in", "We plan to use 1.2 M LiPF6 in")
    elif change == "foreign_section":
        m["text"] = m["text"].replace("2.1. Material Preparation.", "Previous work reported that 2.1. Material Preparation.")
    elif change == "future_target":
        c["text"] = c["text"].replace("we have designed", "we would say we have designed")
    else:
        a["text"] = a["text"].replace("ABSTRACT:", "OVERVIEW:")
    assert case != CASES[0], "Declared mutation did not change its input: " + change
    assert not assemble(case).eligible, change


@pytest.mark.parametrize("source_type", ["main_text", "formula_block", "figure_caption"])
def test_internal_methods_role_does_not_reclassify_registered_parent(source_type):
    case = copy.deepcopy(CASES[0])
    case["sources"][1]["source_type"] = source_type
    assert assemble(case).eligible
    assert case["sources"][1]["source_type"] == source_type


@pytest.mark.parametrize("change", ["drop_parent", "raw", "fact", "source_type", "layer", "policy", "graph", "quote", "question",
    "reference", "missing_graph", "bad_json", "context_type"])
def test_complete_graph_is_recomputed_before_any_fact_selection(change):
    bundle = assemble()
    assert bundle.eligible
    selected = list(bundle.evidence)
    if change == "drop_parent":
        selected.pop(1)
    else:
        payload = json.loads(selected[1].text)
        if change == "raw":
            payload["raw_source"] = payload["raw_source"].replace("LiDFOB", "LiBOB")
        elif change == "fact":
            payload = json.loads(selected[0].text)
            payload["records"][0]["allowed_claim"] = "invented"
            selected[0] = replace(selected[0], text=json.dumps(payload))
        elif change == "source_type":
            payload["raw_source_type"] = "main_text"
        elif change == "layer":
            payload["assembly"]["layers"][CASES[0]["sources"][1]["chunk_id"]] = "ocr"
        elif change == "policy":
            payload["assembly"]["version"] = "unsupported"
        elif change == "graph":
            payload["assembly"]["base_code"] = "invented"
        elif change == "quote":
            payload["assembly"]["witnesses"][0]["text"] = "invented"
        elif change == "question":
            payload["assembly"]["question"] += " при температуре 17 градусов"
        elif change == "reference":
            payload["assembly"]["reference"]["resolved"] = False
        elif change == "missing_graph":
            payload.pop("assembly")
        elif change == "context_type":
            payload["assembly"] = []
        if change != "fact":
            selected[1] = replace(selected[1], text="invalid" if change == "bad_json" else json.dumps(payload))
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records(selected)


@pytest.mark.parametrize("mode", ["complete", "abstain", "invalid"])
@pytest.mark.parametrize("http", [False, True])
def test_actual_service_and_asgi_keep_selection_contract(mode, http):
    from sqlalchemy.engine import Engine

    from app.generation.methods_identity import POLICY

    settings = files.configure().model_copy(update={"rag_methods_identity_policy": POLICY})
    observed = []

    class Synthetic:
        def generate(self, question, evidence, **kwargs):
            observed.extend(evidence)
            records = answer_facts.selection_records(evidence)
            assert len(records) == 3
            claims = [GeneratedClaim(k, [r["citation_id"]]) for k, r in records.items()]
            if mode == "invalid":
                claims.pop()
            return ProviderResult(mode != "abstain", claims if mode != "abstain" else [], "SYNTHETIC_METHODS_POLICY", None)

    with patch.object(service, "search_chunks", return_value=retrieval(CASES[0])), \
            patch.object(service, "build_answer_provider", return_value=Synthetic()), \
            patch("app.main.get_settings", return_value=settings), \
            patch.object(Engine, "connect", side_effect=AssertionError("Offline Methods controls forbid DB")):
        if http:
            from fastapi.testclient import TestClient

            from app.core.config import get_settings
            from app.db.session import get_session
            from app.main import app

            previous = dict(app.dependency_overrides)

            def no_session():
                yield None

            app.dependency_overrides[get_settings] = lambda: settings
            app.dependency_overrides[get_session] = no_session
            try:
                with TestClient(app) as client:
                    response = client.post("/answer", json={"question": CASES[0]["question"], "answer_language": "ru"})
                assert response.status_code == (502 if mode == "invalid" else 200), response.text
                result = response.json()
            finally:
                app.dependency_overrides.clear()
                app.dependency_overrides.update(previous)
        elif mode == "invalid":
            with pytest.raises(GenerationOutputError):
                service.answer_question(None, settings, CASES[0]["question"], answer_language="ru")
            return
        else:
            result = service.answer_response_to_dict(service.answer_question(None, settings, CASES[0]["question"], answer_language="ru"))
    assert len(observed) == 3
    if mode != "invalid":
        assert result["status"] == ("answered" if mode == "complete" else "insufficient_evidence")
        assert result["metadata"]["source_facts"]["active"]
    if mode == "complete":
        assert {c["citation_id"] for c in result["citations"]} == {s["citation_id"] for s in CASES[0]["sources"]}
        assert all("порядку" in c["text"] for c in result["claims"])


@pytest.mark.parametrize("guard", ["required_concept", "required_relation"])
def test_new_policy_keeps_required_coverage_vetoes(guard):
    from app.generation.methods_identity import POLICY

    original = service.assess_evidence_adequacy

    def assess(*args, **kwargs):
        value = original(*args, **kwargs)
        if guard == "required_concept":
            return replace(value, required_concepts=replace(value.required_concepts, missing=["synthetic_missing"]))
        return replace(value, relation_requirements={**value.relation_requirements, "missing": ["synthetic_missing"]})

    class Forbidden:
        def generate(self, *args, **kwargs):
            pytest.fail("Coverage veto must precede generation")

    settings = files.configure().model_copy(update={"rag_methods_identity_policy": POLICY})
    with patch.object(service, "search_chunks", return_value=retrieval(CASES[0])), \
            patch.object(service, "assess_evidence_adequacy", assess):
        result = service.answer_question(None, settings, CASES[0]["question"], answer_language="ru", provider=Forbidden())
    assert result.status == "insufficient_evidence"
    assert not result.metadata["source_facts"]["active"]


def test_disabled_default_requires_explicit_policy_and_valid_configuration():
    from pydantic import ValidationError

    from app.core.config import Settings
    from app.generation.methods_identity import prepare

    case = CASES[0]
    assert Settings(_env_file=None).rag_methods_identity_policy == "disabled"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rag_methods_identity_policy="unknown")
    assert not prepare(case["question"], [Evidence(**e) for e in case["sources"]], case["reference"], case["layers"]).eligible


def test_actual_native_and_ui_show_exact_definitions_with_raw_bindings():
    from app.generation.gigachat import GigaChatAnswerProvider
    from app.generation.methods_identity import POLICY
    from app.ui import _prepared_statement_text

    bundle = assemble()
    provider = GigaChatAnswerProvider(credentials="offline", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                      timeout_seconds=120, max_tokens=1200)
    observed = []

    def post(url, raw, authorization, *, oauth=False):
        if oauth:
            return b'{"access_token":"offline"}'
        rows = json.loads(json.loads(raw)["messages"][-1]["content"].split("Source-bound records:\n", 1)[1])
        observed.extend(rows)
        for row in rows:
            graph = row["source_role_assembly"]
            assert graph["version"] == POLICY and graph["explicit_assumption"]
            assert {w["chunk_id"] for w in graph["witnesses"]} == {s["chunk_id"] for s in CASES[0]["sources"]}
            for anchor in graph["witnesses"]:
                parent = next(s for s in CASES[0]["sources"] if s["chunk_id"] == anchor["chunk_id"])
                assert parent["text"][anchor["start"]:anchor["end"]] == anchor["text"]
            parent = next(s for s in CASES[0]["sources"] if s["citation_id"] == row["citation_id"])
            assert all(f["source_quote"] in parent["text"] for f in row["source_bound_facts"])
        records = answer_facts.selection_records(bundle.evidence)
        content = {"answerable": True, "claims": [{"text": k, "citation_ids": [r["citation_id"]]} for k, r in records.items()]}
        return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
            "content": json.dumps(content)}}]}).encode()

    provider._post = post
    assert provider.generate(CASES[0]["question"], bundle.evidence).answerable
    assert len(observed) == 3
    for raw, derived in zip(bundle.display, bundle.evidence, strict=True):
        text = _prepared_statement_text(derived.text, answer_facts.SOURCE_TYPE)
        assert "порядку" in text
        for anchor in bundle.assembly["witnesses"]:
            if anchor["chunk_id"] == raw.chunk_id:
                assert anchor["text"] in text


@pytest.mark.parametrize("replacement", ["a different electrolyte makes", "another electrolyte makes",
    "a different cell system makes", "it would make", "it does not make"])
def test_adverse_probe_does_not_attach_another_or_nonasserted_CE_to_target(replacement):
    case = copy.deepcopy(CASES[0])
    before = case["sources"][2]["text"]
    case["sources"][2]["text"] = before.replace("it also makes", replacement)
    assert before != case["sources"][2]["text"]
    assert not assemble(case).eligible


@pytest.mark.parametrize("language,enabled,extractive", [("ru", False, False), ("en", True, False), ("ru", True, True)])
def test_service_does_not_enter_new_policy_for_disabled_english_or_extractive(language, enabled, extractive):
    from app.generation.methods_identity import POLICY
    from app.generation.providers import ExtractiveAnswerProvider

    settings = files.configure().model_copy(update={"rag_methods_identity_policy": POLICY if enabled else "disabled"})
    class Synthetic:
        def generate(self, *args, **kwargs):
            return ProviderResult(False, [], "SYNTHETIC_LEGACY_ABSTENTION", None)

    class ExtractiveStub(ExtractiveAnswerProvider):
        def generate(self, *args, **kwargs):
            return ProviderResult(False, [], "SYNTHETIC_EXTRACTIVE_ABSTENTION", None)

    provider = ExtractiveStub(max_claims=5) if extractive else Synthetic()
    with patch.object(service, "search_chunks", return_value=retrieval(CASES[0])), \
            patch.object(service, "prepare_methods_identity", side_effect=AssertionError("New policy must not run")):
        result = service.answer_question(None, settings, CASES[0]["question"], answer_language=language, provider=provider)
    assert result.status == "insufficient_evidence"


def test_opt_in_keeps_unrelated_complete_legacy_bundle():
    from app.generation.methods_identity import POLICY

    case = copy.deepcopy(CASES[0])
    case["sources"] = case["sources"][:1]

    class Synthetic:
        def generate(self, question, evidence, **kwargs):
            records = answer_facts.selection_records(evidence)
            assert len(evidence) == 1 and len(records) == 3
            return ProviderResult(True, [GeneratedClaim(k, [r["citation_id"]]) for k, r in records.items()], "SYNTHETIC_LEGACY", None)

    settings = files.configure().model_copy(update={"rag_methods_identity_policy": POLICY})
    with patch.object(service, "search_chunks", return_value=retrieval(case)), \
            patch.object(service, "prepare_methods_identity", side_effect=AssertionError("Unrelated complete path must remain")):
        result = service.answer_question(None, settings, case["question"], answer_language="ru", provider=Synthetic())
    assert result.status == "answered"
    assert "assembly" not in result.metadata["source_facts"]


def test_selected_policy_failure_abstains_before_provider():
    from app.generation.methods_identity import POLICY

    case = copy.deepcopy(CASES[0])
    case["sources"][1]["text"] = case["sources"][1]["text"].replace("LiDFOB", "LiBOB")

    class Forbidden:
        def generate(self, *args, **kwargs):
            pytest.fail("Selected graph failure must not fall back to the legacy provider")

    settings = files.configure().model_copy(update={"rag_methods_identity_policy": POLICY})
    with patch.object(service, "search_chunks", return_value=retrieval(case)):
        result = service.answer_question(None, settings, case["question"], answer_language="ru", provider=Forbidden())
    assert result.status == "insufficient_evidence"
    assert result.metadata["source_facts"]["reason"] == "methods_composition_fields_do_not_match_abstract"
