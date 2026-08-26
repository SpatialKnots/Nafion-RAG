from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.generation.providers import (
    DeepSeekAnswerProvider,
    ExtractiveAnswerProvider,
    GeneratedClaim,
    GenerationOutputError,
    GenerationUnavailableError,
    OllamaAnswerProvider,
    OpenAIAnswerProvider,
    ProviderResult,
)
from app.generation.service import answer_question, answer_response_to_dict, build_answer_provider
from app.retrieval.search import SearchResponse, SearchResult


def test_answer_question_returns_source_linked_extractive_claims(monkeypatch) -> None:
    search_result = _search_result()
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="How was conductivity measured?",
            results=[search_result],
            metadata={"fusion": "reciprocal_rank_fusion"},
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "How was conductivity measured?",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )
    payload = answer_response_to_dict(response)

    assert response.status == "answered"
    assert response.answer == "Conductivity was measured by impedance spectroscopy. [E1]"
    assert payload["citations"][0]["chunk_id"] == search_result.chunk_id  # type: ignore[index]
    assert payload["citations"][0]["page_start"] == 2  # type: ignore[index]
    assert payload["citations"][0]["method_ranks"] == {"exact_ilike": 1, "semantic_cosine": 2}  # type: ignore[index]


def test_answer_question_refuses_when_retrieval_returns_no_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="unknown", results=[]),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "unknown",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.answer is None
    assert response.citations == []


def test_answer_question_refuses_when_evidence_lacks_distinctive_terms(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="zirconium cerium extraterrestrial regolith perchlorate electrolyte",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="Unrelated paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="Nafion conductivity in polymer membranes.",
                    score=1.0,
                    retrieval_method="exact_ilike",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "zirconium cerium extraterrestrial regolith perchlorate electrolyte",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.claims == []
    assert response.metadata["evidence_adequacy"]["adequate"] is False  # type: ignore[index]


def test_answer_question_refuses_when_short_scientific_term_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Nafion conductivity in DMF",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="Water-cast Nafion paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="body",
                    snippet="Recast Nafion-117 thin film from water solution shows thermogravimetric decomposition.",
                    score=1.0,
                    retrieval_method="hybrid_rrf",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity in DMF",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.claims == []
    assert response.metadata["evidence_adequacy"]["distinctive_terms"] == ["nafion", "conductivity", "dmf"]  # type: ignore[index]
    assert response.metadata["evidence_adequacy"]["matched_terms"] == ["nafion"]  # type: ignore[index]


def test_answer_question_refuses_when_only_solvent_matches(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(
            query="Nafion conductivity in DMF",
            results=[
                SearchResult(
                    article_id=str(uuid.UUID(int=1)),
                    chunk_id=str(uuid.UUID(int=2)),
                    title="DMF morphology paper",
                    doi=None,
                    page_start=1,
                    page_end=1,
                    source_type="table",
                    snippet="Aggregation radii were measured for membranes prepared from DMAc, DMF, and NMF solvents.",
                    score=1.0,
                    retrieval_method="hybrid_rrf",
                )
            ],
        ),
    )

    response = answer_question(
        object(),  # type: ignore[arg-type]
        _settings(),  # type: ignore[arg-type]
        "Nafion conductivity in DMF",
        provider=ExtractiveAnswerProvider(max_claims=3),
    )

    assert response.status == "insufficient_evidence"
    assert response.metadata["evidence_adequacy"]["distinctive_terms"] == ["nafion", "conductivity", "dmf"]  # type: ignore[index]
    assert response.metadata["evidence_adequacy"]["matched_terms"] == ["dmf"]  # type: ignore[index]


def test_answer_question_rejects_unknown_generated_citation(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="conductivity measured", results=[_search_result()]),
    )
    provider = StaticProvider(
        ProviderResult(
            answerable=True,
            claims=[GeneratedClaim(text="Unsupported claim", citation_ids=["E99"])],
            provider="test",
            model="test-model",
        )
    )

    with pytest.raises(GenerationOutputError, match="unknown citations"):
        answer_question(object(), _settings(), "conductivity measured", provider=provider)  # type: ignore[arg-type]


def test_answer_question_rejects_answerable_output_without_claims(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.generation.service.search_chunks",
        lambda *args, **kwargs: SearchResponse(query="conductivity measured", results=[_search_result()]),
    )
    provider = StaticProvider(ProviderResult(answerable=True, claims=[], provider="test", model=None))

    with pytest.raises(GenerationOutputError, match="at least one claim"):
        answer_question(object(), _settings(), "conductivity measured", provider=provider)  # type: ignore[arg-type]


def test_build_answer_provider_rejects_unknown_provider() -> None:
    settings = _settings()
    settings.rag_provider = "unknown"

    with pytest.raises(ValueError, match="Unsupported RAG provider"):
        build_answer_provider(settings)  # type: ignore[arg-type]


def test_ollama_provider_requires_configured_model() -> None:
    with pytest.raises(GenerationUnavailableError, match="RAG_MODEL"):
        OllamaAnswerProvider(base_url="http://127.0.0.1:11434", model="", timeout_seconds=10)


def test_ollama_provider_parses_structured_claims() -> None:
    provider = OllamaAnswerProvider(base_url="http://127.0.0.1:11434", model="test-model", timeout_seconds=10)

    result = provider._parse_response(  # noqa: SLF001 - direct parser unit test
        {"message": {"content": '{"answerable":true,"claims":[{"text":"Supported","citation_ids":["E1"]}]}'}}
    )

    assert result.answerable is True
    assert result.claims == [GeneratedClaim(text="Supported", citation_ids=["E1"])]
    assert result.model == "test-model"


def test_openai_provider_requires_api_key() -> None:
    with pytest.raises(GenerationUnavailableError, match="RAG_OPENAI_API_KEY"):
        OpenAIAnswerProvider(
            base_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4.1-mini",
            timeout_seconds=10,
            max_tokens=100,
        )


def test_openai_provider_parses_structured_claims() -> None:
    provider = OpenAIAnswerProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model="gpt-4.1-mini",
        timeout_seconds=10,
        max_tokens=100,
    )

    result = provider._parse_response(  # noqa: SLF001 - direct parser unit test
        {"choices": [{"message": {"content": '{"answerable":true,"claims":[{"text":"Supported","citation_ids":["E1"]}]}'}}]}
    )

    assert result.answerable is True
    assert result.claims == [GeneratedClaim(text="Supported", citation_ids=["E1"])]
    assert result.provider == "openai"
    assert result.model == "gpt-4.1-mini"


def test_build_answer_provider_accepts_openai() -> None:
    settings = _settings()
    settings.rag_provider = "openai"
    settings.rag_openai_api_key = "test-key"

    provider = build_answer_provider(settings)  # type: ignore[arg-type]

    assert isinstance(provider, OpenAIAnswerProvider)


def test_deepseek_provider_requires_api_key() -> None:
    with pytest.raises(GenerationUnavailableError, match="DEEPSEEK_API_KEY"):
        DeepSeekAnswerProvider(
            base_url="https://api.deepseek.com",
            api_key="",
            model="deepseek-v4-flash",
            timeout_seconds=10,
            max_tokens=100,
        )


def test_deepseek_provider_parses_structured_claims() -> None:
    provider = DeepSeekAnswerProvider(
        base_url="https://api.deepseek.com",
        api_key="test-key",
        model="deepseek-v4-flash",
        timeout_seconds=10,
        max_tokens=100,
    )

    result = provider._parse_response(  # noqa: SLF001 - direct parser unit test
        {"choices": [{"message": {"content": '{"answerable":true,"claims":[{"text":"Supported","citation_ids":["E1"]}]}'}}]}
    )

    assert result.answerable is True
    assert result.claims == [GeneratedClaim(text="Supported", citation_ids=["E1"])]
    assert result.provider == "deepseek"
    assert result.model == "deepseek-v4-flash"


class StaticProvider:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result

    def generate(self, question: str, evidence: list[object]) -> ProviderResult:
        return self.result


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        default_collection="literature",
        rag_top_k=5,
        rag_retrieval_method="hybrid",
        rag_provider="extractive",
        rag_max_claims=5,
        rag_ollama_url="http://127.0.0.1:11434",
        rag_openai_base_url="https://api.openai.com/v1",
        rag_openai_api_key="",
        rag_openai_model="gpt-4.1-mini",
        rag_openai_max_tokens=1200,
        rag_deepseek_url="https://api.deepseek.com",
        rag_deepseek_api_key="",
        rag_deepseek_model="deepseek-v4-flash",
        rag_deepseek_max_tokens=1200,
        rag_model="",
        rag_timeout_seconds=120,
    )


def _search_result() -> SearchResult:
    return SearchResult(
        article_id=str(uuid.UUID(int=1)),
        chunk_id=str(uuid.UUID(int=2)),
        title="Evidence paper",
        doi="10.1000/evidence",
        page_start=2,
        page_end=3,
        source_type="method",
        snippet="Conductivity was measured by impedance spectroscopy.",
        score=0.03,
        retrieval_method="hybrid_rrf",
        method_scores={"exact_ilike": 100.0, "semantic_cosine": 0.8},
        method_ranks={"exact_ilike": 1, "semantic_cosine": 2},
    )
