"""Constructed table ownership/column controls, plus one exposed raw-source replay."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation.providers import GeneratedClaim, GenerationOutputError
from app.generation.quantitative_facts import prepare
from tests.unit.test_quantitative_facts import PREFIX, REF, source

QUESTION = PREFIX + ('Как изменились сопротивления в POS/Na-полуячейках с ABC и XYZ '
                     'после четырёх предварительных циклов?')
HEADER = ('Table 7 Fitted resistance data from the equivalent circuit Electrolyte '
          'Before cycle After 4th cycles R0 Rs + Rct R0 Rs Rct Rs + Rct ')
ROWS = 'ABC 1.10 41.20 1.40 30.00 15.00 45.00 XYZ 2.30 92.10 1.80 10.20 8.70 18.90'
RAW = 'The POS/Na half cells were studied. ' + HEADER + ROWS + ' Fig. 8 Results.'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def test_all_six_columns_each_electrolyte_group_headers_and_unknown_units_are_preserved():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 12
    assert [f['value']['text'] for f in record['facts']] == [
        '1.10', '41.20', '1.40', '30.00', '15.00', '45.00', '2.30', '92.10', '1.80', '10.20', '8.70', '18.90']
    for f in record['facts']:
        assert f['unit'] is None and 'unit' in f['unknown_fields']
        assert not f['scientific_ownership_verified']
        state = 'Before cycle' if '_before_' in f['property'] else 'After 4th cycles'
        assert f['conditions']['cycle_state']['text'] == state
        for value in [f['sample'], f['value'], *f['conditions'].values()]:
            anchor = value['source']
            assert RAW[anchor['start']:anchor['end']] == anchor['text']
    text = answer_facts.resolve_selections([GeneratedClaim('F1', ['E1'])], result.evidence)[0].text
    assert '41.20 → 45.00 (увеличилась)' in text and '92.10 → 18.90 (уменьшилась)' in text
    assert 'Единица в самой таблице не указана' in text and 'по отдельности' in text
    assert 'Ω' not in text and 'Ом' not in text


@pytest.mark.parametrize('old,new', [
    ('After 4th', 'After 3rd'), ('Before cycle After', 'After cycle Before'),
    ('R0 Rs + Rct R0 Rs Rct', 'R0 Rs + Rct R0 Rct Rs'),
    ('R0 Rs + Rct R0', 'R0 (ohm) Rs + Rct R0'),
    ('ABC 1.10', 'ABC 1.10 99.9'), ('ABC 1.10', 'ABC'),
    ('XYZ 2.30', 'ABC 2.30'), ('XYZ 2.30', 'OTHER 2.30'),
    ('30.00 15.00 45.00', '30.00 15.00 44.99'),
    ('POS/Na half', 'NEG/Na half'), ('POS/Na half', 'POS/Na full'),
    ('were studied.', 'were studied. The NEG/Na cell was measured.'),
    ('Table 7', 'The previously reported Table 7'),
    ('The POS', 'In previous work, the POS'),
    ('After 4th', 'A\ue09der 4th'),
])
def test_wrong_condition_column_row_owner_status_or_unreviewed_glyph_refuses(old, new):
    assert not bundle(RAW.replace(old, new)).eligible


@pytest.mark.parametrize('suffix', [' при 25 °C', ' в омах', ' и электролитом ZZZ', ' и механизм', ' без изменения состава'])
def test_extra_question_conditions_cannot_be_silently_ignored(suffix):
    assert not bundle(question=QUESTION[:-1] + suffix + '?').eligible


def test_query_cycles_and_labels_are_parsed_instead_of_hardcoded():
    assert bundle(RAW.replace('4th', '2nd'), QUESTION.replace('четырёх', 'двух')).eligible
    assert not bundle(question=QUESTION.replace('XYZ', 'ABC')).eligible
    changed = RAW.replace('ABC', 'NEW').replace('XYZ', 'ALT').replace('45.00', '41.20').replace('30.00', '26.20')
    result = bundle(changed, QUESTION.replace('ABC', 'NEW').replace('XYZ', 'ALT'))
    assert result.eligible and 'не изменилась' in result.records[0]['allowed_claim']


def test_row_order_is_not_used_as_electrolyte_identity():
    a, b = ROWS.split(' XYZ ')
    result = bundle(RAW.replace(ROWS, 'XYZ ' + b + ' ' + a))
    assert result.eligible and result.records[0]['allowed_claim'] == bundle().records[0]['allowed_claim']


def test_conflicting_tables_cannot_select_first_matching_row():
    other = source(RAW.replace('41.20', '42.20'), citation_id='E2', chunk_id='other')
    result = prepare(QUESTION, [source(RAW), other], REF)
    assert not result.eligible and result.reason == 'conflicting_quantitative_values_or_conditions'


@pytest.mark.parametrize('field', ['column', 'cycle_state', 'unit_status', 'value', 'allowed_claim'])
def test_derived_column_condition_unit_and_rendering_drift_rejected(field):
    result = bundle()
    payload = json.loads(result.evidence[0].text)
    record = payload['records'][0]
    if field in ('column', 'cycle_state'):
        record['facts'][0]['conditions'][field]['text'] = 'unbound'
    elif field == 'unit_status':
        record['source_grammar']['unit_status'] = 'ohm'
    elif field == 'value':
        record['facts'][0]['value']['text'] = '999'
    else:
        record['allowed_claim'] = '999 ohm'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0], text=json.dumps(payload))])


def test_exposed_peng_source_keeps_raw_glyphs_and_recomputes_all_twelve_fields():
    from app.generation.providers import Evidence

    fixture = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/peng_resistance_source_v01.json').read_bytes())
    saved, question = fixture['trace'], fixture['api']['question']
    result = prepare(question, [Evidence(**e) for e in saved['evidence']],
                     saved['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 12 and record['source_grammar']['glyph_decoding']
    assert '\ue09d' in result.display[0].text
    assert '56.39 → 57.56' in record['allowed_claim'] and '109.80 → 24.71' in record['allowed_claim']


@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('prose', 502)])
def test_actual_experimental_api_synthetic_selection_abstention_and_prose(monkeypatch, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult
    from scripts.gigachat_answer_smoke import configure

    fixture = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/peng_resistance_source_v01.json').read_bytes())
    api, raw = fixture['api'], fixture['trace']['retrieval']
    retrieval = SearchResponse(**{**raw, 'results': [SearchResult(**r) for r in raw['results']]})
    settings, calls, transactions = configure(), [], []

    class Session:
        def execute(self, sql):
            transactions.append(str(sql))

        def rollback(self):
            transactions.append('rollback')

    def dependency():
        yield Session()

    original = routes.make_provider

    def factory(value):
        provider = original(value)

        def post(url, body, auth, *, oauth=False):
            calls.append('synthetic_oauth' if oauth else 'synthetic_model')
            if oauth:
                return b'{"access_token":"synthetic"}'
            request = json.loads(body)
            assert request  # Actual provider construction/parsing, transport is synthetic.
            content = {'answerable': mode != 'abstain', 'claims': [] if mode == 'abstain' else [
                {'text': 'F1' if mode == 'select' else '999 ohm', 'citation_ids': ['E2']}]}
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
                'role': 'assistant', 'content': json.dumps(content)}}]}).encode()

        provider._post = post
        return provider

    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: deepcopy(retrieval))
    monkeypatch.setattr(routes, 'make_provider', factory)
    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post('/answer/experimental/required-fields', json=api)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == status and calls == ['synthetic_oauth', 'synthetic_model']
    assert 'READ ONLY' in transactions[0] and transactions[-1] == 'rollback'
    if mode == 'select':
        body = response.json()
        assert body['delivery_status'] == 'not_evaluated' and body['answer']['status'] == 'answered'
        assert 'Единица в самой таблице не указана' in routes.render(body)
        assert '56.39 → 57.56' in body['answer']['claims'][0]['text']
    elif mode == 'abstain':
        assert response.json()['answer']['status'] == 'insufficient_evidence'
