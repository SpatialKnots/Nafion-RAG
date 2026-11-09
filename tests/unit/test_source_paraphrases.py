"""Bounded constructed paraphrases, exact raw binding and rejection controls."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from app.generation.answer_facts import prepare, resolve_selections, selection_records, verify_raw_binding
from app.generation.answer_fidelity import prepare as fidelity
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = json.loads((ROOT / "output/source_paraphrases_20261109/controls_v01.json").read_bytes())


def evaluate(case):
    sources = [Evidence(**e) for e in case["sources"]]
    contract = fidelity(case["question"], sources)
    bundle = prepare(case["question"], sources, None, contract, answer_language="ru")
    return contract, bundle


@pytest.mark.parametrize("case", CONTROLS, ids=lambda case: case["id"])
def test_real_anchor_paraphrase_and_negative_controls(case):
    contract, bundle = evaluate(case)
    assert bool(contract and contract.eligible and bundle and bundle.eligible) == case["expected_eligible"], (
        case["id"], contract.metadata() if contract else None, bundle.metadata() if bundle else None)
    if not case["expected_eligible"]:
        return
    records = selection_records(bundle.evidence)
    rendered = resolve_selections([GeneratedClaim(k, [v["citation_id"]]) for k, v in records.items()], bundle.evidence)
    assert [c.text for c in rendered] == [r["allowed_claim"] for r in records.values()]
    for derived in bundle.evidence:
        raw = next(e for e in bundle.display if e.citation_id == derived.citation_id)
        verify_raw_binding(derived.text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
                           citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end)
    for record in records.values():
        for fact in record["facts"]:
            assert fact["scientific_ownership_verified"] is False
    if case["role"] == "hold_observation":
        assert "необратимость не доказана" in " ".join(c.text for c in rendered)


@pytest.mark.parametrize("role", ["gas_synthesis", "eis_medium", "hold_observation"])
@pytest.mark.parametrize("mutation", ["value", "condition", "summary", "citation", "partial"])
def test_paraphrases_do_not_bypass_recomputation_or_complete_id_selection(role, mutation):
    case = next(c for c in CONTROLS if c["id"] == role + ":positive")
    _, bundle = evaluate(case)
    assert bundle.eligible, bundle.diagnostics
    derived = list(bundle.evidence)
    records = selection_records(derived)
    if mutation in {"partial", "citation"}:
        chosen = [GeneratedClaim(k, [v["citation_id"]]) for k, v in records.items()]
        if mutation == "partial":
            chosen.pop()
        else:
            chosen[0] = replace(chosen[0], citation_ids=["E999"])
        with pytest.raises(GenerationOutputError):
            resolve_selections(chosen, derived)
        return
    payload = json.loads(derived[0].text)
    record = payload["records"][0]
    if mutation == "summary":
        record["allowed_claim"] += " доказано"
    elif mutation == "condition":
        record["facts"][0]["operation"] = "different_operation"
    else:
        record["facts"][0]["value"] = None if record["facts"][0]["value"] else {"text": "999"}
    derived[0] = replace(derived[0], text=json.dumps(payload, ensure_ascii=False))
    with pytest.raises(GenerationOutputError):
        selection_records(derived)


@pytest.mark.parametrize("role", ["gas_synthesis", "eis_medium", "hold_observation"])
def test_equivalent_source_fields_and_summary_are_preserved(role):
    original = next(c for c in CONTROLS if c["id"] == role + ":original")
    changed = next(c for c in CONTROLS if c["id"] == role + ":positive")
    old_contract, old = evaluate(original)
    contract, new = evaluate(changed)
    assert old.eligible and new.eligible
    assert "source_paraphrases" not in old_contract.metadata()
    assert contract.metadata()["source_paraphrases"] == {"version": "source_paraphrases_v0.2", "roles": [role]}
    assert [r["allowed_claim"] for r in new.records] == [r["allowed_claim"] for r in old.records]

    def fields(value):
        if isinstance(value, list):
            return [fields(v) for v in value]
        if isinstance(value, dict):
            return {k: fields(v) for k, v in value.items() if k not in {"source", "support"}}
        return "v/v" if value == "by volume" else value

    assert fields([r["facts"] for r in new.records]) == fields([r["facts"] for r in old.records])
    assert [r["arithmetic"] for r in new.records] == [r["arithmetic"] for r in old.records]


@pytest.mark.parametrize("role", ["gas_synthesis", "eis_medium", "hold_observation"])
@pytest.mark.parametrize("change", ["prior_work", "other_sample", "formula_case"])
def test_new_alternatives_preserve_formula_case_and_do_not_borrow_foreign_statements(role, change):
    case = next(c for c in CONTROLS if c["id"] == role + ":positive")
    replacement = case["replacement"]
    if change == "prior_work":
        replacement = "Previous work reported that " + replacement
    elif change == "other_sample":
        replacement = "For another sample, " + replacement
    else:
        before, after = {"gas_synthesis": ("Li foils", "li foils"), "eis_medium": ("LiPF6", "LIPF6"),
                         "hold_observation": (" W ", " w ")}[role]
        replacement = replacement.replace(before, after)
    case = {**case, "sources": [{**e, "text": e["text"].replace(case["replacement"], replacement)} for e in case["sources"]]}
    contract, bundle = evaluate(case)
    assert not contract.eligible and not bundle.eligible


@pytest.mark.parametrize("role", ["gas_synthesis", "eis_medium", "hold_observation"])
@pytest.mark.parametrize("kind", ["conflicting", "other_work", "varied_numbers"])
def test_conflicts_and_other_work_refuse_while_new_values_come_from_source(role, kind):
    case = next(c for c in CONTROLS if c["id"] == role + ":positive")
    case = {**case, "sources": [dict(e) for e in case["sources"]]}
    anchor = case["original_anchor"]
    target = next(e for e in case["sources"] if e["chunk_id"] == anchor["chunk_id"])
    groups = anchor["groups"]
    key = {"gas_synthesis": "hours", "eis_medium": "concentration", "hold_observation": "days"}[role]
    unit = {"gas_synthesis": " hour", "eis_medium": " M", "hold_observation": " days"}[role]
    changed = case["replacement"].replace(groups[key] + unit, "17" + unit)
    if kind == "varied_numbers":
        target["text"] = target["text"].replace(case["replacement"], changed)
        contract, bundle = evaluate(case)
        assert contract.eligible and bundle.eligible
        assert "17" in " ".join(r["allowed_claim"] for r in bundle.records)
        facts = [f for r in bundle.records for f in r["facts"]]
        field = (next(f for f in facts if f["property"] == "layer_synthesis")["conditions"]["duration"]
                 if role == "gas_synthesis" else
                 next(f for f in facts if f["property"] == ("eis_electrolyte_concentration" if role == "eis_medium"
                                                           else "isothermal_hold_duration"))["value"])
        assert field["numeric_value"] == "17"
    elif kind == "conflicting":
        target["text"] += "\n" + changed
        contract, bundle = evaluate(case)
        assert not contract.eligible and not bundle.eligible
    else:
        target["text"] = target["text"].replace(case["replacement"], "")
        foreign = {**target, "text": case["replacement"], "article_id": "other-work", "chunk_id": "foreign", "citation_id": "E999"}
        case["sources"].append(foreign)
        contract, bundle = evaluate(case)
        assert not contract.eligible and not bundle.eligible


@pytest.mark.parametrize("role", ["gas_synthesis", "hold_observation"])
@pytest.mark.parametrize("abstain", [False, True])
@pytest.mark.parametrize("http", [False, True])
def test_actual_service_and_asgi_complete_ids_or_abstention(role, abstain, http):
    from sqlalchemy.engine import Engine

    from app.generation import service
    from app.generation.providers import ProviderResult
    from app.retrieval.search import SearchResponse, SearchResult, make_snippet
    from scripts import gigachat_answer_smoke as files

    case = next(c for c in CONTROLS if c["id"] == role + ":positive")
    cid = "Q02" if role == "gas_synthesis" else "Q04"
    saved = json.loads((ROOT / f"output/source_paraphrases_20261109/freeze_v01/{cid}_current.json").read_bytes())
    baseline = saved["trace"]["retrieval"]
    texts = {e["chunk_id"]: e["text"] for e in case["sources"]}
    rows = [SearchResult(**{**r, "full_text": texts.get(r["chunk_id"], r["full_text"]),
                            "snippet": make_snippet(texts.get(r["chunk_id"], r["full_text"]), case["question"])})
            for r in baseline["results"]]
    retrieval = SearchResponse(query=case["question"], results=rows, metadata=baseline["metadata"])
    settings, observed = files.configure(), []

    class Synthetic:
        def generate(self, question, evidence, **kwargs):
            observed.extend(evidence)
            records = selection_records(evidence)
            assert records
            return ProviderResult(not abstain, [] if abstain else [GeneratedClaim(k, [r["citation_id"]]) for k, r in records.items()],
                                  "SYNTHETIC_PARAPHRASE_SELECTION", None)

    with patch.object(service, "search_chunks", return_value=retrieval), \
            patch.object(service, "build_answer_provider", return_value=Synthetic()), \
            patch.object(Engine, "connect", side_effect=AssertionError("Offline controls forbid DB")):
        if http:
            from fastapi.testclient import TestClient

            from app.core.config import get_settings
            from app.db.session import get_session
            from app.main import app

            previous = dict(app.dependency_overrides)

            def no_session():
                yield None

            app.dependency_overrides[get_session] = no_session
            app.dependency_overrides[get_settings] = lambda: settings
            try:
                with TestClient(app) as client:
                    response = client.post("/answer", json={"question": case["question"], "answer_language": "ru"})
                assert response.status_code == 200, response.text
                body = response.json()
            finally:
                app.dependency_overrides.clear()
                app.dependency_overrides.update(previous)
        else:
            result = service.answer_question(None, settings, case["question"], answer_language="ru")
            body = service.answer_response_to_dict(result)
    assert observed
    assert body["status"] == ("insufficient_evidence" if abstain else "answered")
    assert body["metadata"]["answer_fidelity"]["source_paraphrases"]["roles"] == [role]
    assert body["metadata"]["source_facts"]["active"]
    assert body["claims"] == ([] if abstain else [{"text": r["allowed_claim"], "citation_ids": [r["citation_id"]]}
                                                for r in selection_records(observed).values()])
