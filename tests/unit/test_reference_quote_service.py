"""Actual service and native schemas with frozen channels/fake transport only."""

from unittest.mock import patch

import pytest

from app.generation.gigachat import GigaChatAnswerProvider
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError, ProviderResult
from app.generation.reference_quotes import selection_choices
from scripts import benchmark_retrieval_replay_20261105 as engine
from scripts import gigachat_answer_smoke as files
from scripts.ascii_quote_selection_checks_20261105 import synthetic_selection
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE, inventory_scope, raw_evidence


@pytest.fixture(autouse=True)
def historical_quote_contract_only():
    # Keep the earlier exact-quotation regression intact. The later F-ID facts
    # path has separate provider/service/UI controls and frozen-source audits.
    with patch("app.generation.service.prepare_answer_facts", return_value=None):
        yield


@pytest.fixture(scope="module")
def inventory():
    return read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")


@pytest.fixture(scope="module")
def settings():
    return files.configure()


@pytest.mark.parametrize("case_id,roles", [("Q01", {"abstract"}), ("Q05", {"method", "table"})])
def test_actual_gate_requires_complete_bounded_source_roles(case_id, roles, settings, inventory):
    corpus, articles = inventory
    source = read(CORPUS_BASE / case_id / "boundaries.json")
    with inventory_scope(corpus, articles):
        result = engine.replay(source, settings, replacement=lambda response: response)
    metadata = result["trace"]["metadata"]
    assert result["boundary"]["generation_reached"] is True
    assert metadata["evidence_adequacy"]["lexical_baseline"]["adequate"] is False
    assert {r["role"] for r in metadata["reference_quote_selection"]["records"]} == roles
    assert metadata["reference_quote_selection"]["diagnostics"]["front_matter_author_citation_ids"]
    assert raw_evidence(result["trace"], corpus)


@pytest.mark.parametrize("case_id", ["Q01", "Q05"])
def test_actual_native_schema_and_synthetic_selection_are_bounded(case_id, settings, inventory, tmp_path):
    corpus, articles = inventory
    source = read(CORPUS_BASE / case_id / "boundaries.json")
    result = synthetic_selection(source, settings, corpus, articles, tmp_path, case_id)
    native = read(tmp_path / f"{case_id}_native_unsent.json")
    answer = read(tmp_path / f"{case_id}_SYNTHETIC_server_answer.json")
    enum = native["response_format"]["schema"]["$defs"]["_Claim"]["properties"]["text"]["enum"]
    assert answer["status"] == "answered" and answer["generation_provider"] == "SYNTHETIC_ASCII_ID_SELECTION"
    assert enum == result["selection_ids"] and all(value.isascii() for value in enum)
    assert not any(c["text"] in enum for c in answer["claims"])
    assert result["real_model_calls"] == result["real_oauth_calls"] == 0
    assert "ASCII IDs" in native["messages"][1]["content"]
    assert native["max_tokens"] == 1200
    frozen = files.ROOT / f"output/reference_quote_runtime_20261105/review_v02/{case_id}_SYNTHETIC_selection.json"
    assert answer["answer"] == read(frozen)["answer"]


@pytest.mark.parametrize("mode", ["partial", "addition", "wrong_citation"])
def test_service_rejects_incomplete_or_free_additions(mode, settings, inventory):
    corpus, articles = inventory
    source = read(CORPUS_BASE / "Q05/boundaries.json")

    class BadSelection:
        def generate(self, question, evidence, **kwargs):
            claims = [GeneratedClaim(text, [citation]) for citation, texts in selection_choices(evidence).items() for text in texts]
            if mode == "partial":
                claims = claims[:1]
            elif mode == "addition":
                claims[0] = GeneratedClaim("Unsupported invented value 999.", claims[0].citation_ids)
            else:
                claims[0] = GeneratedClaim(claims[0].text, ["unknown"])
            return ProviderResult(answerable=True, claims=claims, provider="SYNTHETIC_BAD_SELECTION", model=None)

    with inventory_scope(corpus, articles), patch.object(engine, "NoGeneration", BadSelection):
        with pytest.raises(GenerationOutputError):
            engine.replay(source, settings, replacement=lambda response: response)


def test_abstention_still_allowed(settings, inventory):
    corpus, articles = inventory
    source = read(CORPUS_BASE / "Q05/boundaries.json")

    class Abstain:
        def generate(self, *args, **kwargs):
            return ProviderResult(answerable=False, claims=[], provider="SYNTHETIC_ABSTENTION", model=None)

    with inventory_scope(corpus, articles), patch.object(engine, "NoGeneration", Abstain):
        result = engine.replay(source, settings, replacement=lambda response: response)
    assert result["boundary"]["status"] == "insufficient_evidence"


@pytest.mark.parametrize("case_id", ["Q01", "Q05"])
def test_historical_unicode_failure_is_not_repaired_or_accepted_as_new_id(case_id, settings, inventory):
    # Counterfactual input only: the preserved old model body is not a response
    # to the new prompt and must never be reclassified as a successful live run.
    corpus, articles = inventory
    source = read(CORPUS_BASE / case_id / "boundaries.json")
    with inventory_scope(corpus, articles):
        prepared = engine.replay(source, settings, replacement=lambda response: response)
    evidence = [Evidence(**e) for e in prepared["trace"]["evidence"]]
    raw_path = files.ROOT / f"output/reference_quote_live_20261105/{case_id}/live/response.bin"
    original_bytes = raw_path.read_bytes()
    client = GigaChatAnswerProvider(credentials="offline-placeholder", scope=settings.gigachat_scope,
                                   model=settings.rag_model, timeout_seconds=120, max_tokens=1200)
    client._post = lambda *args, **kwargs: b'{"access_token":"offline"}' if kwargs.get("oauth") else original_bytes
    with pytest.raises(GenerationOutputError):
        client.generate(source["api"]["question"], evidence)
    assert raw_path.read_bytes() == original_bytes
