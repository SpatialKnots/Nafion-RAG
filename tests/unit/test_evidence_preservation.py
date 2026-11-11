"""Information-loss controls for already-refused preparation, not scientific answers."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.generation import service
from app.generation.evidence_preservation import recover
from app.generation.providers import Evidence, ProviderResult
from app.retrieval.search import SearchResponse, SearchResult
from scripts.gigachat_answer_smoke import configure

QUESTION = 'По статье Taylor (2023): Как определяли пороговый диапазон эффекта?'
RAW = 'Taylor 2023. Chemical potential of graphite is discussed in this source.'


def item(text=RAW, **changes):
    return replace(Evidence('E1', 'work', 'one', 'Constructed work', None, 1, 1, 'main_text', text, 1.0,
                            'synthetic', {}, {}), **changes)


def reference():
    return {'resolved': True, 'article_id': 'work', 'matching_article_ids': ['work'], 'surname': 'Taylor', 'year': '2023'}


def call(pool, kept=None, layers=None, metadata=None):
    kept = pool[:1] if kept is None else kept
    return recover(QUESTION, pool, pool, kept, kept, layers=layers or {e.chunk_id: 'original' for e in pool},
                   reference_metadata=reference() if metadata is None else metadata)


def test_overlapping_chunk_keeps_the_new_page_and_original_raw_data():
    one = item()
    two = item(RAW + '\nThe next page reports a new observation: 47 specimens.', chunk_id='two', page_end=2)
    assert service._find_duplicate_evidence_index(two, [one]) == 0
    recovered, display, diagnostics = call([one, two])
    assert [e.chunk_id for e in recovered] == ['one', 'two'] and recovered[1].text == two.text
    assert [e.citation_id for e in recovered] == [e.citation_id for e in display] == ['E1', 'E2']
    assert diagnostics['admission_changed'] is False and diagnostics['automatic_reassessment'] is False
    assert diagnostics['final_kept_chars'] <= diagnostics['original_pool_chars']


@pytest.mark.parametrize('new', [RAW + ' A value is 9.8.', RAW.replace('discussed', 'not discussed')])
def test_different_number_or_negation_on_same_page_is_not_redundant(new):
    assert call([item(), item(new, chunk_id='two')]) is not None


@pytest.mark.parametrize('new', [RAW, ' \n' + RAW.replace(' ', '  ') + '\n'])
def test_proven_contained_text_can_remain_omitted(new):
    assert call([item(), item(new, chunk_id='two')]) is None


def test_containment_across_existing_pages_is_proven_without_adding_a_source():
    first, second = item('First page.'), item('Second page.', chunk_id='two', page_start=2, page_end=2)
    combined = item('First page.\nSecond page.', chunk_id='both', page_end=2)
    assert call([first, second, combined], [first, second]) is None


@pytest.mark.parametrize('change', [{'source_type': 'method'}, {'page_start': 2, 'page_end': 2}])
def test_different_provenance_is_preserved(change):
    assert call([item(), item(chunk_id='two', **change)]) is not None


def test_layer_difference_is_not_silently_deduplicated():
    assert call([item(), item(chunk_id='two')], layers={'one': 'original', 'two': 'ocr'}) is not None
    assert call([item(), item(chunk_id='two')], layers={'one': 'original'}) is None


@pytest.mark.parametrize('change', [{'resolved': False}, {'surname': 'Other'}, {'year': '2022'},
                                  {'matching_article_ids': ['work', 'other']}])
def test_unresolved_or_inconsistent_reference_does_not_restore(change):
    assert call([item(), item(RAW + ' New text.', chunk_id='two')], metadata={**reference(), **change}) is None


def test_foreign_work_with_same_title_and_invalid_parent_are_not_merged():
    assert call([item(), item(RAW + ' New.', chunk_id='two', article_id='other')]) is None
    assert call([item(), item(RAW + ' New.', chunk_id='two')], kept=[item('Invented parent.')]) is None


def test_broken_display_pairing_raises_a_diagnostic():
    with pytest.raises(ValueError, match='pairing'):
        recover(QUESTION, [item()], [], [item()], [item()], layers={'one': 'original'}, reference_metadata=reference())


def service_case(monkeypatch, question, provider):
    one = SearchResult('work', 'one', 'Constructed work', None, 1, 1, 'main_text', RAW, 1.0, 'synthetic', full_text=RAW)
    two = replace(one, chunk_id='two', page_end=2, full_text=RAW + ' Second page with 47 observations.')
    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: SearchResponse(
        query=question, results=[one, two], metadata={'explicit_source_reference': reference()}))
    traces = []
    response = service.answer_question(object(), configure(), question, provider=provider,
                                      trace_observer=lambda r, e, m: traces.append((e, m)))
    return response, traces


def test_actual_refused_service_restores_context_without_calling_provider(monkeypatch):
    class Forbidden:
        def generate(self, *args, **kwargs):
            pytest.fail('Context recovery must not upgrade admission')
    response, traces = service_case(monkeypatch, QUESTION, Forbidden())
    assert response.status == 'insufficient_evidence'
    assert [e.chunk_id for e in traces[0][0]] == ['one', 'two']
    assert traces[0][1]['retrieved_raw_preservation']['admission_changed'] is False
    assert traces[0][1]['evidence_adequacy']['adequate'] is False


def test_already_admitted_service_uses_identical_old_evidence(monkeypatch):
    class Abstain:
        def __init__(self):
            self.calls = 0
        def generate(self, *args, **kwargs):
            self.calls += 1
            return ProviderResult(False, [], 'synthetic', None)
    provider = Abstain()
    with patch.object(service, 'recover_deduplicated_evidence', side_effect=AssertionError('Ready path must stay unchanged')):
        _, traces = service_case(monkeypatch, 'Taylor (2023): chemical potential graphite', provider)
    assert provider.calls == 1 and len(traces[0][0]) == 1
