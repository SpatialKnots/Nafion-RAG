"""Constructed coverage/admission controls; not independent scientific answers."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.generation import service
from app.generation.bilingual_lexical import assess
from app.generation.providers import Evidence, ProviderResult
from app.retrieval.search import SearchResponse, SearchResult
from scripts.gigachat_answer_smoke import configure

QUESTION = 'По статье Rivera (2022): Как синтезировали ZETA, каков был выход продукта и его чистота после очистки?'
TEXT = 'We synthesized ZETA in a yield of 41%. ZETA was purified by distillation. The purity of ZETA was 98%.'
ORDER_Q = ('По статье Rivera (2022): В каком порядке расположены четыре эфира по вязкости '
           'и каковы их энергии активации вязкого течения?')
ORDER_TEXT = ('The viscosities of these ethers follow the order ALFA > BETA > GAMMA > DELTA. '
              'The apparent activation energy for viscosity follows this order.')


def scope():
    return {'resolved': True, 'article_id': 'work', 'matching_article_ids': ['work'], 'surname': 'Rivera', 'year': '2022'}


def evidence(text=TEXT, **kwargs):
    return replace(Evidence('E1', 'work', 'chunk', 'Constructed work', None, 1, 1, 'main_text', text, 1.0, 'synthetic', {}, {}),
                   **kwargs)


@pytest.mark.parametrize('kind', ['main_text', 'method', 'figure_caption'])
def test_direct_fields_and_source_classifications_keep_exact_raw_witnesses(kind):
    items, metadata = [evidence(source_type=kind)], scope()
    before = deepcopy((items, metadata))
    result = assess(QUESTION, items, metadata)
    assert result['eligible'] and result['scientific_support'] == 'not_evaluated'
    assert (items, metadata) == before
    witness = result['witnesses'][0]
    for hit in (*witness['concept_matches'].values(), *witness['identifier_matches'].values()):
        assert TEXT[hit['start']:hit['end']] == hit['text']
        assert TEXT[hit['context_start']:hit['context_end']] == hit['context_text']


def test_source_ligature_and_query_inflection():
    assert assess('Rivera (2022): Каковы выход и чистота ZETA?', [evidence(TEXT.replace('purified', 'puriﬁed'))], scope())['eligible']


@pytest.mark.parametrize('original,replacement', [('synthesized', 'prepared'), ('yield', 'amount'),
                                                ('purity', 'quality'), ('purified', 'distilled')])
def test_missing_each_requested_field_is_not_rescued_by_other_matches(original, replacement):
    result = assess(QUESTION, [evidence(TEXT.replace(original, replacement))], scope())
    assert not result['eligible'] and result['reason'] == 'source_field_mentions_unresolved'


@pytest.mark.parametrize('replacement', ['OTHER', 'ZETA2', 'AZETA'])
def test_missing_or_substring_identifier(replacement):
    assert not assess(QUESTION, [evidence(TEXT.replace('ZETA', replacement))], scope())['eligible']


def test_fields_of_a_different_named_product_are_not_owned_by_query_product():
    raw = 'ZETA was synthesized. OMEGA had a yield of 41%. OMEGA was purified. The purity of OMEGA was 98%.'
    assert not assess(QUESTION, [evidence(raw)], scope())['eligible']


def test_fields_and_phrase_halves_cannot_be_joined_across_chunks():
    items = [evidence('We synthesized ZETA in a yield of 41%.'),
             evidence('ZETA was purified. The purity of ZETA was 98%.', citation_id='E2', chunk_id='other')]
    assert not assess(QUESTION, items, scope())['eligible']
    assert not assess(ORDER_Q, [evidence('The viscosity of ethers has an activation.'),
                               evidence('Energy. Order ALFA > BETA > GAMMA > DELTA.', citation_id='E2')], scope())['eligible']


@pytest.mark.parametrize('change', [None, {'resolved': False}, {'matching_article_ids': ['work', 'other']},
                                  {'year': '2021'}, {'surname': 'Other'}, {'article_id': 'other'}])
def test_unresolved_or_mismatched_reference(change):
    metadata = None if change is None else {**scope(), **change}
    assert not assess(QUESTION, [evidence()], metadata)['eligible']


def test_mixed_articles_and_empty_evidence():
    assert not assess(QUESTION, [evidence(), evidence(article_id='other', citation_id='E2')], scope())['eligible']
    assert not assess(QUESTION, [], scope())['eligible']


@pytest.mark.parametrize('suffix', [' при 25 C', ' методом DSC', ' после сублимации', ' не измеряли',
                                  ' почему', ' подтверждён ли результат', ' для любых веществ'])
def test_unknown_conditions_and_epistemic_requests_are_not_dropped(suffix):
    assert not assess(QUESTION.rstrip('?') + suffix + '?', [evidence()], scope())['eligible']


@pytest.mark.parametrize('raw', [TEXT.replace('We synthesized', 'We may have synthesized'),
                                TEXT.replace('purity of ZETA was 98%', 'purity of ZETA was not measured'),
                                'References\n' + TEXT, 'Previous work: ' + TEXT,
                                'Keywords: synthesis, yield, purity, purification, ZETA.'])
def test_excluded_source_regions_cannot_supply_field_matches(raw):
    assert not assess(QUESTION, [evidence(raw)], scope())['eligible']


def test_previous_work_sentence_does_not_hide_current_experiment():
    raw = 'Synthesis of ANOTHER was described in a previous paper.3 ' + TEXT
    assert assess(QUESTION, [evidence(raw)], scope())['eligible']


def test_four_item_order_uses_literal_chain_and_keeps_count_mismatch_unresolved():
    result = assess(ORDER_Q, [evidence(ORDER_TEXT)], scope())
    assert result['eligible']
    assert result['witnesses'][0]['item_count_match']['text'] == 'ALFA > BETA > GAMMA > DELTA'
    assert not assess(ORDER_Q.replace('четыре', 'три'), [evidence(ORDER_TEXT)], scope())['eligible']
    assert not assess(ORDER_Q, [evidence(ORDER_TEXT.replace(' > DELTA', ''))], scope())['eligible']


@pytest.mark.parametrize('kind', ['references', 'formula_block', 'header'])
def test_unsupported_source_types_remain_unresolved(kind):
    assert not assess(QUESTION, [evidence(source_type=kind)], scope())['eligible']


def test_outside_vocabulary_has_no_effect():
    assert assess('Rivera (2022): Какова проводимость ZETA?', [evidence()], scope()) is None
    assert assess('What are synthesis yield and purity?', [evidence()], scope()) is None


def test_bibliographic_names_are_not_query_concepts():
    metadata = {**scope(), 'surname': 'Yield'}
    assert assess('По статье Yield and Purity (2022): Какова ZETA?', [evidence()], metadata) is None


def test_additional_coauthor_is_not_proven_by_first_surname_metadata():
    assert assess(QUESTION.replace('Rivera (2022)', 'Rivera and Jones (2022)'), [evidence()], scope()) is None


@pytest.mark.parametrize('phrase', ['never measured', 'not provided', 'not reported'])
def test_explicit_nonobservations_cannot_supply_purity(phrase):
    raw = TEXT.replace('purity of ZETA was 98%', 'purity of ZETA was ' + phrase)
    assert not assess(QUESTION, [evidence(raw)], scope())['eligible']


class AbstainingProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return ProviderResult(False, [], 'synthetic', None)


def run_service(monkeypatch, raw, question=QUESTION, metadata=None):
    row = SearchResult(article_id='work', chunk_id='chunk', title='Constructed work', doi=None,
                       page_start=1, page_end=1, source_type='main_text', text_layer='original',
                       snippet=raw, full_text=raw, score=1.0, retrieval_method='synthetic')
    retrieval = SearchResponse(query=question, results=[row],
                               metadata={'explicit_source_reference': scope() if metadata is None else metadata})
    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: retrieval)
    provider = AbstainingProvider()
    result = service.answer_question(object(), configure(), question, provider=provider, answer_language='ru')
    return result, provider


def test_actual_service_admits_fields_but_provider_abstention_still_wins(monkeypatch):
    result, provider = run_service(monkeypatch, TEXT)
    assert provider.calls == 1 and result.status == 'insufficient_evidence' and not result.claims
    diagnostics = result.metadata['evidence_adequacy']
    assert diagnostics['reason'] == 'sufficient_bilingual_field_mentions'
    assert diagnostics['lexical_baseline']['adequate'] is False


def test_actual_service_blocks_missing_field_before_provider(monkeypatch):
    result, provider = run_service(monkeypatch, TEXT.replace('purity', 'quality'))
    assert provider.calls == 0 and result.status == 'insufficient_evidence'
    assert result.metadata['evidence_adequacy']['reason'] == 'insufficient_distinctive_term_coverage'


def test_actual_service_required_material_veto_cannot_be_upgraded(monkeypatch):
    result, provider = run_service(monkeypatch, TEXT, QUESTION.rstrip('?') + ' в PBI?')
    assert provider.calls == 0 and result.metadata['evidence_adequacy']['reason'] == 'missing_required_concepts'
    assert 'bilingual_lexical_coverage' not in result.metadata['evidence_adequacy']
