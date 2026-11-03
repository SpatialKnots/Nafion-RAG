"""Product quote-only scope, field isolation and strict provider validation."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.generation import service
from app.generation.gigachat import AUTH_URL, GigaChatAnswerProvider
from app.generation.lithiation_overview import allowed_claims, prepare, validate_claims
from app.generation.presentation import capture_sources
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.retrieval.search import SearchResponse, SearchResult

QUESTION = "Какие существуют методики литирования Nafion?"
TEXT = ("2.1. Подготовка мембран Nafion\n\nДополнительно использовали дисперсию Nafion.\n\n"
        "Мембраны очищали 2 ч при 80 °C.\n\n"
        "Рисунок 2.1 — Схема подготовки мембран Nafion: очистка мембран (а); литирование мембраны (б)\n\n"
        "На втором этапе (см. рисунок 2.1б) проводили литирование ионным обменом в 2.0 М LiOH "
        "при 60 °C в течение 120 мин; для завершения обмена выполняли второй этап в 1.0 М LiOH,")


def evidence(text=TEXT, citation_id="E1", chunk="00000000-0000-0000-0000-000000000002"):
    return Evidence(citation_id, "00000000-0000-0000-0000-000000000001", chunk, "Method source", None,
                    2, 3, "method", text, 1.0, "exact", {}, {})


def search(text=TEXT):
    item = evidence(text)
    return SearchResponse(query=QUESTION, results=[SearchResult(
        article_id=item.article_id, chunk_id=item.chunk_id, title=item.title, doi=None, page_start=2, page_end=3,
        source_type="method", snippet=text, full_text=text, score=1, retrieval_method="exact")])


def settings():
    return SimpleNamespace(default_collection="literature", rag_top_k=5, rag_retrieval_method="exact", rag_provider="gigachat",
                           rag_model="GigaChat-2-Max", rag_max_claims=5)


def provider():
    return GigaChatAnswerProvider(credentials="synthetic", scope="GIGACHAT_API_PERS", model="GigaChat-2-Max",
                                 max_tokens=1200, timeout_seconds=120)


def response(text, ids=None, answerable=True):
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps({
        "answerable": answerable, "claims": [{"text": text, "citation_ids": ids or ["E1"]}] if answerable else []},
        ensure_ascii=False)}}]}, ensure_ascii=False).encode()


def fake_transport(monkeypatch, *, corrupt=False, abstain=False):
    observed = []

    def post(self, url, body, authorization, *, oauth=False):
        observed.append((url, body))
        if url == AUTH_URL:
            assert oauth and authorization == "Basic synthetic"
            return b'{"access_token":"synthetic-token"}'
        request = json.loads(body)
        choices = request["response_format"]["schema"]["$defs"]["_Claim"]["properties"]["text"]["enum"]
        assert request["max_tokens"] == 1200
        assert "2 ч" not in choices[0] and "120 мин" in choices[0]
        return response("Полный протокол: держать 2 ч." if corrupt else choices[0], answerable=not abstain)

    monkeypatch.setattr(GigaChatAnswerProvider, "_post", post)
    return observed


def test_atomic_record_keeps_original_fields_and_incomplete_protocol():
    packet = prepare(QUESTION, [evidence()])
    assert packet is not None and packet.eligible
    record, = packet.records
    assert record["binding_kind"] == "explicit_figure_subpanel_reference"
    assert record["material"]["form_cue"] == "membrane" and record["material"]["grade"] == "not_established"
    assert record["fields"]["duration"]["spans"][0]["text"] == "120 мин"
    assert record["fields"]["concentration"]["spans"][0]["text"] == "2.0 М"
    assert not record["fields"]["duration"]["owner_established"]
    assert record["source_excerpt_incomplete"] and "не полный протокол" in record["allowed_claim"]
    assert "2 ч" not in record["allowed_claim"] and "1.0 М" not in record["allowed_claim"]
    for key in ("material_context", "operation", "method"):
        span = record[key]
        assert TEXT[span["start"]:span["end"]] == span["text"]


@pytest.mark.parametrize("text", [
    "Методики литирования Nafion: литирования не проводили.",
    "2.1. Подготовка мембран Nafion\n\nВ будущем планируется литирование ионным обменом в LiOH.",
    "Nafion. Проводили литирование полиэтилена ионным обменом в LiOH.",
    "2.1. Подготовка мембран Nafion\n\nПроводили литирование полипропилена ионным обменом в LiOH.",
    "Проводили литирование мембран Nafion.",
    "Проводили литирование мембран Nafion ионным обменом.",
    "Проводили литирование мембран Nafion в LiOH.",
    "Для литирования Nafion не использовали LiOH.",
    "Литирование Nafion.",
])
def test_related_or_negative_text_cannot_create_quote_permission(text):
    packet = prepare(QUESTION, [evidence(text)])
    assert packet is not None and not packet.eligible and not packet.evidence


@pytest.mark.parametrize("suffix", [" в DMF", " за сколько минут", " лучший способ", " при 25°C", " с PBI"])
def test_unsupported_constraint_does_not_use_overview_shortcut(suffix):
    packet = prepare(QUESTION + suffix, [evidence()])
    assert packet is not None and not packet.eligible
    assert packet.reason == "unsupported_lithiation_overview_constraint"


def test_unrelated_question_has_no_behavior_change():
    assert prepare("Какая смесь даёт лучшую проводимость Li-Nafion?", [evidence()]) is None
    assert prepare("Li-Nafion membrane lithiation protocol", [evidence()]) is None


def test_quote_cannot_be_paraphrased_or_cited_to_another_record():
    packet = prepare(QUESTION, [evidence()])
    allowed = allowed_claims(packet.evidence)
    text = allowed["E1"][0]
    validate_claims([GeneratedClaim(text, ["E1"])], allowed)
    for claims in ([GeneratedClaim(text + " 2 ч", ["E1"])], [GeneratedClaim(text, ["E2"])],
                   [GeneratedClaim(text, ["E1"])] * 2):
        with pytest.raises(GenerationOutputError, match="exact source-backed"):
            validate_claims(claims, allowed)


@pytest.mark.parametrize("raw", ["not json", "[]", "null", '{"version":"wrong"}'])
def test_malformed_quote_contract_is_explicit_error(raw):
    with pytest.raises(GenerationOutputError):
        allowed_claims([replace(evidence(), source_type="procedure_derived", text=raw)])


def test_quote_contract_never_mixes_with_unrestricted_evidence():
    packet = prepare(QUESTION, [evidence()])
    with pytest.raises(GenerationOutputError, match="must not mix"):
        allowed_claims([*packet.evidence, evidence()])


@pytest.mark.parametrize("style", ["claims", "mini_review"])
def test_service_and_real_gigachat_parser_select_exact_quote_offline(monkeypatch, style):
    observed = fake_transport(monkeypatch)
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: search())
    captured = []
    answer = service.answer_question(object(), settings(), QUESTION, provider=provider(), answer_style=style,
                                     trace_observer=lambda *args: captured.append(args))
    assert answer.status == "answered" and len(observed) == 2
    assert answer.metadata["evidence_adequacy"]["lexical_baseline"]["adequate"] is False
    assert "120 мин" in answer.answer and "2 ч" not in answer.answer
    assert answer.citations[0].source_type == "procedure_derived"
    sources = capture_sources(captured[0][0], captured[0][1])
    assert sources["E1"].source_text == TEXT and sources["E1"].generation_is_derived


def test_invalid_generated_conditions_rejected_by_real_parser(monkeypatch):
    fake_transport(monkeypatch, corrupt=True)
    packet = prepare(QUESTION, [evidence()])
    with pytest.raises(GenerationOutputError, match="exact source-backed"):
        provider().generate(QUESTION, packet.evidence)


def test_provider_can_still_abstain(monkeypatch):
    fake_transport(monkeypatch, abstain=True)
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: search())
    result = service.answer_question(object(), settings(), QUESTION, provider=provider())
    assert result.status == "insufficient_evidence" and not result.claims


def test_negative_exact_surface_blocks_provider_even_if_old_lexical_gate_passes(monkeypatch):
    monkeypatch.setattr(service, "search_chunks", lambda *a, **kw: search("Методики литирования Nafion: литирования не проводили."))

    class Forbidden:
        def generate(self, *a, **kw):
            pytest.fail("No provider call for nonperformance")

    result = service.answer_question(object(), settings(), QUESTION, provider=Forbidden())
    assert result.status == "insufficient_evidence"
    assert result.metadata["evidence_adequacy"]["lexical_baseline"]["adequate"] is True


def test_derived_ui_shows_readable_statement_and_original_raw_source():
    from app.ui import _claim_source_fragment
    packet = prepare(QUESTION, [evidence()])
    citation = packet.evidence[0]
    source = capture_sources(search(), packet.evidence)["E1"]
    html = _claim_source_fragment({"citation_id": "E1", "article_id": citation.article_id, "chunk_id": citation.chunk_id,
                                   "page_start": 2, "page_end": 3, "title": citation.title}, source)
    assert "Найденное описание" in html and "Исходный фрагмент" in html
    assert "allowed_claim" not in html and "Подготовленные системой цитаты" in html
