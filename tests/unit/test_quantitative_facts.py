"""Constructed quantitative binding controls, not independent scientific labels."""

import json
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.generation import answer_facts, service
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError, ProviderResult
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResponse, SearchResult
from scripts.gigachat_answer_smoke import configure

REF = {'resolved': True, 'article_id': 'work', 'matching_article_ids': ['work'], 'surname': 'Rivera', 'year': '2024'}
PREFIX = 'По статье Rivera (2024): '
RANGE_Q = PREFIX + 'Каков пороговый диапазон μNa⁺ для подавления совместной интеркаляции Na⁺ с растворителем?'
RANGE = ('We identified a threshold of μNa+ at 2–8 J mol−1 that dominantly determined whether '
         'Na+ intercalation or Na+–solvent cointercalation occurred.')
RATIO_Q = (PREFIX + 'Как изменяется реакция графита в NaABC/SOLV при переходе от соотношения '
           '1/8 к 1/3 и 1/2 (соль/растворитель)?')
RATIO = ('In dilute NaABC/SOLV (1/8 by mol) with low μNa+ (1 J mol−1), Na+–solvent cointercalation occurred at 0.6–1.1 V. '
         'At an intermediate concentration (1/3 by mol) with intermediate μNa+ (7 J mol−1), we observed both Na+ intercalation '
         '(0.1–0.3 V) and Na+–solvent cointercalation (sloping curve in 0.6–1.1 V). In contrast, at a high concentration '
         '(1/2 by mol) with high μNa+ (11 J mol−1), we observed Na+ intercalation.')
COUNT_Q = PREFIX + ('Сколько электролитных составов исследовали авторы для проверки общей корреляции '
                    'и что использовали как показатель нормальной интеркаляции Na⁺?')
COUNT = ('We studied 17 electrolyte formulations with different solvents and salt concentrations (Figure S1). '
         'To judge which reaction (Na+ intercalation or Na+–solvent cointercalation) predominantly occurred, '
         'we extracted the reversible capacities in a voltage range of 0.1–0.3 V for graphite|Na cells, '
         'which are fully attributed to Na+ intercalation.')
INITIAL_Q = PREFIX + ('Какие начальная разрядная ёмкость и кулоновская эффективность получены '
                      'для полуячейки POS/Na с ABC?')
INITIAL = ('The electrochemical behavior of POS/Na half cell is discussed. A initial discharge capacity of '
           '178.2 mA h g−1 with a initial CE of 88.5% is obtained in the ABC cell.')
FULL_Q = PREFIX + ('Каковы начальная удельная ёмкость и сохранность ёмкости полной POS/NEG-ячейки с ABC '
                   'при повышенном верхнем напряжении?')
FULL = ('This was evaluated by a POS/NEG full cell. At the upper voltage of 4.1 V. The cell in ABC favors '
        'a initial capacity of about 178.2 mA h g−1 and capacity retention of 82% after 60 cycles.')


def source(text=RANGE, **kwargs):
    return replace(Evidence('E1', 'work', 'chunk', 'Constructed work', None, 2, 2, 'figure_caption', text, 1.0,
                            'synthetic', {}, {}), **kwargs)


@pytest.mark.parametrize('question,text', [(RANGE_Q, RANGE), (RATIO_Q, RATIO), (COUNT_Q, COUNT),
                                         (INITIAL_Q, INITIAL), (FULL_Q, FULL)])
def test_complete_constructed_source_contracts_keep_all_fields_and_exact_quotes(question, text):
    items, metadata = [source(text)], deepcopy(REF)
    before = deepcopy((items, metadata))
    bundle = prepare(question, items, metadata, answer_language='ru')
    assert bundle.eligible and (items, metadata) == before
    records = answer_facts.selection_records(bundle.evidence)
    assert list(records) == ['F1'] and records['F1'] == bundle.records[0]
    for fact in records['F1']['facts']:
        for value in (fact['sample'], fact['value'], fact['unit'], *fact['conditions'].values()):
            if value:
                hit = value['source']
                assert text[hit['start']:hit['end']] == hit['text']
        hit = fact['support']
        assert text[hit['start']:hit['end']] == hit['text']
    resolved = answer_facts.resolve_selections([GeneratedClaim('F1', ['E1'])], bundle.evidence)
    assert resolved[0].text == records['F1']['allowed_claim']
    assert answer_facts.prompt_records(bundle.evidence)[0]['source_bound_facts']


def test_source_hyphenation_and_ligatures_retain_raw_addresses():
    raw = COUNT.replace('formulations', 'formula-\ntions').replace('fully', 'fully')
    assert prepare(COUNT_Q, [source(raw)], REF).eligible


def test_additional_ion_selector_cannot_be_ignored():
    assert not prepare(RANGE_Q.replace('Na⁺ с', 'Li⁺ с'), [source()], REF).eligible


def test_reference_metadata_order_does_not_change_raw_bound_payload():
    reordered = dict(reversed(list(REF.items())))
    assert prepare(RANGE_Q, [source()], REF).evidence == prepare(RANGE_Q, [source()], reordered).evidence


def test_previous_work_cell_frame_cannot_own_current_capacity():
    assert not prepare(INITIAL_Q, [source('In previous work, ' + INITIAL)], REF).eligible


@pytest.mark.parametrize('change', [None, {'resolved': False}, {'year': '2023'}, {'surname': 'Other'},
                                  {'matching_article_ids': ['work', 'other']}])
def test_reference_mismatch_cannot_upgrade_numeric_overlap(change):
    metadata = None if change is None else {**REF, **change}
    assert not prepare(RANGE_Q, [source()], metadata).eligible


@pytest.mark.parametrize('suffix', [' при 25 °C', ' методом DSC', ' и плотность', ' не универсальный', ' для всех солей'])
def test_unrecognized_conditions_or_scientific_claims_are_not_removed(suffix):
    assert not prepare(RANGE_Q.rstrip('?') + suffix + '?', [source()], REF).eligible


def test_cross_article_and_additional_named_author_are_unresolved():
    assert not prepare(RANGE_Q, [source(), source(article_id='other', chunk_id='other', citation_id='E2')], REF).eligible
    assert not prepare(RANGE_Q.replace('Rivera (2024)', 'Rivera and Jones (2024)'), [source()], REF).eligible


@pytest.mark.parametrize('prefix', ['Previous work: ', 'We hypothesize: ', 'Not observed: ', 'References\n'])
def test_noncurrent_or_negative_source_prefix_cannot_supply_records(prefix):
    assert not prepare(RANGE_Q, [source(prefix + RANGE)], REF).eligible


def test_conflicting_complete_candidates_refuse_without_first_match_selection():
    second = source(RANGE.replace('2–8', '3–9'), citation_id='E2', chunk_id='other')
    bundle = prepare(RANGE_Q, [source(), second], REF)
    assert not bundle.eligible and bundle.reason == 'conflicting_quantitative_values_or_conditions'


@pytest.mark.parametrize('raw', [RANGE.replace('2–8', '8–2'), RANGE.replace('μNa+', 'μLi+'),
                                RANGE.replace('Na+–solvent', 'Li+–solvent'), RANGE.replace('J mol−1', 'J mol1')])
def test_wrong_quantity_owner_or_ambiguous_units_refuse(raw):
    assert not prepare(RANGE_Q, [source(raw)], REF).eligible


@pytest.mark.parametrize('raw', [RATIO.replace('NaABC/SOLV', 'NaABC/OTHER'), RATIO.replace('1/3 by mol', '1/4 by mol'),
                                RATIO.replace('both Na+', 'only Na+'), RATIO.replace('7 J mol−1', '7 kJ mol−1'),
                                RATIO.replace('11 J mol−1', '5 J mol−1')])
def test_every_ratio_role_and_ordered_condition_is_required(raw):
    assert not prepare(RATIO_Q, [source(raw)], REF).eligible


@pytest.mark.parametrize('raw', [COUNT.replace('17', '0'), COUNT.replace('reversible capacities', 'other measurements'),
                                COUNT.replace('graphite|Na', 'graphite|Li'), COUNT.replace('fully attributed', 'possibly attributed')])
def test_count_cannot_substitute_for_missing_measurement_criterion(raw):
    assert not prepare(COUNT_Q, [source(raw)], REF).eligible


@pytest.mark.parametrize('raw', [INITIAL.replace('POS/Na', 'NEG/Na'), INITIAL.replace('half cell', 'full cell'),
                                INITIAL.replace('ABC cell', 'XYZ cell'), INITIAL.replace('88.5%', 'not measured'),
                                INITIAL.replace('g−1', 'g\x011')])
def test_half_cell_electrolyte_percent_and_unit_bindings(raw):
    assert not prepare(INITIAL_Q, [source(raw)], REF).eligible


@pytest.mark.parametrize('raw', [FULL.replace('4.1 V', '4.1 mV'), FULL.replace('full cell', 'half cell'),
                                FULL.replace('ABC favors', 'XYZ favors'), FULL.replace('60 cycles', '0 cycles'),
                                FULL.replace('g−1', 'g\x011')])
def test_full_cell_condition_and_capacity_pair_cannot_be_mixed(raw):
    assert not prepare(FULL_Q, [source(raw)], REF).eligible


def test_approximation_is_retained_and_not_repaired_from_unknown_glyph():
    bundle = prepare(FULL_Q, [source(FULL)], REF)
    assert 'приблизительно' in bundle.records[0]['allowed_claim']
    assert not prepare(FULL_Q, [source(FULL.replace('about ', '\x03'))], REF).eligible


@pytest.mark.parametrize('field', ['raw_source', 'record_value', 'record_text', 'citation_id', 'policy', 'source_type'])
def test_derived_contract_recomputes_and_rejects_mutation(field):
    bundle = prepare(RANGE_Q, [source()], REF)
    payload = json.loads(bundle.evidence[0].text)
    if field == 'raw_source':
        payload['raw_source'] = payload['raw_source'].replace('2–8', '3–9')
    elif field == 'record_value':
        payload['records'][0]['facts'][0]['value']['text'] = '999'
    elif field == 'record_text':
        payload['records'][0]['allowed_claim'] = 'Invented result.'
    elif field == 'citation_id':
        payload['records'][0]['citation_id'] = 'E9'
    elif field == 'policy':
        payload['quantitative_policy'] = 'unknown'
    else:
        payload['raw_source_type'] = 'header'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(bundle.evidence[0], text=json.dumps(payload))])


@pytest.mark.parametrize('claims', [[], [GeneratedClaim('F2', ['E1'])], [GeneratedClaim('F1', ['E9'])],
                                  [GeneratedClaim('2–8 J mol−1', ['E1'])],
                                  [GeneratedClaim('F1', ['E1']), GeneratedClaim('F1', ['E1'])]])
def test_partial_duplicate_prose_and_wrong_selection_are_rejected(claims):
    bundle = prepare(RANGE_Q, [source()], REF)
    with pytest.raises(GenerationOutputError):
        answer_facts.resolve_selections(claims, bundle.evidence)


def test_registered_raw_source_type_is_verified():
    bundle = prepare(RANGE_Q, [source()], REF)
    args = dict(article_id='work', chunk_id='chunk', citation_id='E1', page_start=2, page_end=2)
    answer_facts.verify_raw_binding(bundle.evidence[0].text, RANGE, source_type='figure_caption', **args)
    with pytest.raises(ValueError):
        answer_facts.verify_raw_binding(bundle.evidence[0].text, RANGE, source_type='main_text', **args)


class Select:
    def __init__(self, claims=None, answerable=True):
        self.claims = [GeneratedClaim('F1', ['E1'])] if claims is None else claims
        self.answerable, self.calls = answerable, 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return ProviderResult(self.answerable, self.claims, 'synthetic', None)


def run_service(monkeypatch, provider, raw=RANGE):
    row = SearchResult('work', 'chunk', 'Constructed work', None, 2, 2, 'figure_caption', raw, 1.0, 'synthetic', full_text=raw)
    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: SearchResponse(
        query=RANGE_Q, results=[row], metadata={'explicit_source_reference': REF}))
    return service.answer_question(object(), configure(), RANGE_Q, provider=provider, answer_language='ru')


def test_actual_service_resolves_selected_id_to_server_facts(monkeypatch):
    provider = Select()
    result = run_service(monkeypatch, provider)
    assert result.status == 'answered' and provider.calls == 1
    assert '2–8 J mol−1' in result.claims[0].text and result.claims[0].text != 'F1'
    assert result.citations[0].text == RANGE and result.citations[0].source_type == 'figure_caption'
    assert result.metadata['evidence_adequacy']['lexical_baseline']['adequate'] is False


def test_actual_service_retains_provider_abstention(monkeypatch):
    provider = Select([], False)
    result = run_service(monkeypatch, provider)
    assert result.status == 'insufficient_evidence' and provider.calls == 1


def test_actual_service_rejects_numeric_free_prose(monkeypatch):
    with pytest.raises(GenerationOutputError):
        run_service(monkeypatch, Select([GeneratedClaim('The answer is 2–8.', ['E1'])]))


def test_specialized_scope_veto_still_wins(monkeypatch):
    with patch.object(service, 'conductivity_superlative', return_value={'reason': 'constructed_scope_veto'}):
        provider = Select()
        result = run_service(monkeypatch, provider)
    assert result.status == 'insufficient_evidence' and provider.calls == 0


def test_actual_gigachat_schema_and_prompt_use_only_complete_f_ids():
    from app.generation.gigachat import GigaChatAnswerProvider
    bundle = prepare(RANGE_Q, [source()], REF)
    provider = GigaChatAnswerProvider(credentials='synthetic', scope='GIGACHAT_API_PERS', model='GigaChat-2-Max',
                                      timeout_seconds=1, max_tokens=100)
    native = []
    def post(url, body, auth, *, oauth=False):
        if oauth:
            return b'{"access_token":"synthetic"}'
        native.append(json.loads(body))
        return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
            'content': json.dumps({'answerable': True, 'claims': [{'text': 'F1', 'citation_ids': ['E1']}]})}}]}).encode()
    provider._post = post
    result = provider.generate(RANGE_Q, bundle.evidence, answer_language='ru')
    assert result.claims[0].text == 'F1' and len(native) == 1
    assert native[0]['response_format']['schema']['$defs']['_Claim']['properties']['text']['enum'] == ['F1']
    assert 'Source-bound records' in native[0]['messages'][1]['content']


def test_signed_potential_and_reported_percentage_are_not_silently_clamped():
    bundle = prepare(RANGE_Q, [source(RANGE.replace('2–8', '−8–−2'))], REF)
    assert bundle.eligible and '−8–−2' in bundle.records[0]['allowed_claim']
    assert prepare(INITIAL_Q, [source(INITIAL.replace('88.5%', '101%'))], REF).eligible
    assert prepare(FULL_Q, [source(FULL.replace('82%', '104%'))], REF).eligible


@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('free_prose', 502)])
def test_actual_experimental_api_uses_fact_selection_and_readonly_boundary(monkeypatch, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.main import app
    settings = configure()
    calls, transactions = [], []
    class Session:
        def execute(self, sql):
            transactions.append(str(sql))
        def rollback(self):
            transactions.append('rollback')
    def dependency():
        yield Session()
    original_factory = routes.make_provider
    def factory(value):
        provider = original_factory(value)
        def post(url, body, auth, *, oauth=False):
            calls.append('synthetic_oauth' if oauth else 'synthetic_model')
            if oauth:
                return b'{"access_token":"synthetic"}'
            content = {'answerable': mode != 'abstain', 'claims': [] if mode == 'abstain' else [
                {'text': 'F1' if mode == 'select' else 'The numerical answer is 999.', 'citation_ids': ['E1']}]}
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
                                            'content': json.dumps(content)}}]}).encode()
        provider._post = post
        return provider
    row = SearchResult('work', 'chunk', 'Constructed work', None, 2, 2, 'figure_caption', RANGE, 1.0,
                       'synthetic', full_text=RANGE)
    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: SearchResponse(
        query=RANGE_Q, results=[row], metadata={'explicit_source_reference': REF}))
    monkeypatch.setattr(routes, 'make_provider', factory)
    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post('/answer/experimental/required-fields', json={'question': RANGE_Q, 'answer_language': 'ru'})
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == status
    assert calls == ['synthetic_oauth', 'synthetic_model']
    assert 'READ ONLY' in transactions[0] and transactions[-1] == 'rollback'
    if mode == 'select':
        body = response.json()
        assert body['answer']['status'] == 'answered' and '2–8 J mol−1' in body['answer']['claims'][0]['text']
        assert body['delivery_status'] == 'not_evaluated'
        assert '2–8 J mol−1' in routes.render(body)
    elif mode == 'abstain':
        assert response.json()['answer']['status'] == 'insufficient_evidence'
