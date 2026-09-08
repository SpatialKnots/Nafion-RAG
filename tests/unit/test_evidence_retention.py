"""Synthetic selection regressions; snippets do not represent measured data."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.evidence_selection import select_answer_evidence
from app.generation.providers import GeneratedClaim, ProviderResult
from app.generation.service import answer_question
from app.retrieval.search import SearchResponse, SearchResult

QUERY = "Li-Nafion conductivity plasticizer diglyme"


def chunk(number, text, **overrides):
    base = SearchResult(
        article_id=str(UUID(int=1)),
        chunk_id=str(UUID(int=number)),
        title="Synthetic evidence",
        doi=None,
        page_start=number,
        page_end=number + 1,
        source_type="table",
        text_layer="original",
        snippet=text,
        full_text=text,
        score=1 / number,
        retrieval_method="hybrid_rrf",
    )
    return replace(base, **overrides)


def preferred():
    return chunk(2, "Li-Nafion conductivity in plasticizer. Table 4.6.")


def test_restores_full_text_identity_and_keeps_priority_and_provenance():
    lead = preferred()
    needed = chunk(3, "ДГ — диглим; продолжение таблицы.", snippet="Table continuation", page_start=109, page_end=111)
    unrelated = chunk(4, "Background without the requested solvent.")
    selected = select_answer_evidence(QUERY, [needed, unrelated, lead, needed])
    assert selected.results == [lead, needed]
    assert selected.results[1] is needed
    diagnostics = selected.metadata["required_concept_retention"]
    assert diagnostics["before"]["missing"] == ["diglyme"]
    assert diagnostics["after"]["missing"] == []
    assert diagnostics["restored"] == [{"chunk_id": needed.chunk_id, "article_id": needed.article_id, "concepts": ["diglyme"]}]
    assert select_answer_evidence(QUERY, selected.results).results == selected.results


def test_covered_identity_does_not_restore_other_filtered_candidates():
    lead = replace(preferred(), full_text=preferred().full_text + " Diglyme.")
    duplicate_identity = chunk(3, "diglyme")
    selected = select_answer_evidence(QUERY, [lead, duplicate_identity])
    assert selected.results == [lead]
    assert selected.metadata["required_concept_retention"]["restored"] == []


def test_title_and_snippet_cannot_override_nonempty_full_text():
    lead = preferred()
    misleading = chunk(3, "Water only.", title="Diglyme", snippet="diglyme")
    selected = select_answer_evidence(QUERY, [lead, misleading])
    assert selected.results == [lead]
    assert selected.metadata["required_concept_retention"]["after"]["missing"] == ["diglyme"]


def test_absent_identity_still_refuses_and_expansions_are_not_requirements():
    lead = preferred()
    selected = select_answer_evidence(QUERY, [lead])
    assert not assess_evidence_adequacy(QUERY, [SimpleNamespace(text=lead.full_text)]).adequate
    assert selected.metadata["required_concept_retention"]["restored"] == []
    expanded = select_answer_evidence("Li-Nafion conductivity plasticizer", [lead, chunk(3, "diglyme")], additional_queries=["diglyme"])
    assert expanded.results == [lead]
    assert expanded.metadata["required_concept_retention"]["before"]["required"] == []


def test_separate_required_substances_are_restored_once_with_snippet_fallback():
    lead = preferred()
    ec = chunk(3, "ethylene carbonate", full_text=None)
    sl = chunk(4, "сульфолан")
    selected = select_answer_evidence("Li-Nafion conductivity plasticizer EC/SL", [lead, ec, sl])
    assert selected.results == [lead, ec, sl]
    assert selected.metadata["required_concept_retention"]["after"]["missing"] == []
    assert len(selected.metadata["required_concept_retention"]["restored"]) == 2


def test_answer_service_passes_restored_source_to_provider_and_keeps_citation(monkeypatch):
    lead = preferred()
    needed = chunk(3, "Diglyme appears in this table continuation.", snippet="Table continuation", page_start=109, page_end=111)
    monkeypatch.setattr("app.generation.service.search_chunks", lambda *a, **kw: SearchResponse(query=QUERY, results=[lead, needed]))

    class CapturingProvider:
        def generate(self, question, evidence, **kwargs):
            assert [item.chunk_id for item in evidence] == [lead.chunk_id, needed.chunk_id]
            assert evidence[1].text == needed.full_text
            return ProviderResult(
                answerable=True,
                claims=[GeneratedClaim(text="The source names diglyme.", citation_ids=[evidence[1].citation_id])],
                provider="test",
                model=None,
            )

    settings = SimpleNamespace(
        default_collection="literature", rag_top_k=10, rag_retrieval_method="hybrid", rag_provider="test", rag_model=""
    )
    response = answer_question(object(), settings, QUERY, provider=CapturingProvider())
    assert response.status == "answered"
    assert response.metadata["evidence_adequacy"]["required_concepts"]["missing"] == []
    assert len(response.citations) == 1
    citation = response.citations[0]
    assert (citation.article_id, citation.chunk_id, citation.page_start, citation.page_end) == (
        needed.article_id,
        needed.chunk_id,
        109,
        111,
    )
    assert citation.source_type == needed.source_type
