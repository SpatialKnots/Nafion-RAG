"""Source definition and direction controls; not independent chemistry labels."""
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.quantitative_facts import prepare
from tests.unit.test_quantitative_facts import PREFIX, REF, source

QUESTION = PREFIX + ('Какой параметр авторы предложили в качестве количественного дескриптора '
                     'интеркаляции Na⁺ в графит и каков его термодинамический смысл?')
RAW = ('Herein, we report the Na+ chemical potential (μNa+) in electrolytes as a quantitative factor '
       'that strongly correlates with the Na+ intercalation behavior of graphite negative electrodes. '
       'By definition, μNa+ is the partial molar Gibbs free energy of Na+, which quantitatively describes '
       'the thermodynamic stability of Na+ in the electrolyte. Specifically, higher (lower) μNa+ means '
       'unstable (stable) Na+ in the solvation environment.')
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/kondo_descriptor_source_v01.json'


def bundle(raw=RAW, question=QUESTION, metadata=REF):
    return prepare(question, [source(raw)], metadata, answer_language='ru')


def test_complete_definition_correlated_role_and_stability_direction_are_raw_bound():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 3
    assert record['facts'][0]['value']['text'] == 'chemical potential'
    assert record['facts'][1]['value']['text'] == 'partial molar Gibbs free energy of Na+'
    trend = record['facts'][2]
    assert trend['conditions']['higher_state']['text'] == 'unstable'
    assert trend['conditions']['lower_state']['text'] == 'stable'
    for fact in record['facts']:
        assert fact['unit'] is None and fact['value']['numeric_value'] is None
        assert fact['epistemic_status'] == 'source_reported_definition'
        assert not fact['scientific_ownership_verified'] and 'measurement' not in fact['operation']
        for value in (fact['sample'], fact['value'], *fact['conditions'].values()):
            a = value['source']
            assert RAW[a['start']:a['end']] == a['text']
    text = answer_facts.resolve_selections([GeneratedClaim('F1', ['E1'])], result.evidence)[0].text
    assert 'сильная корреляция' in text and 'парциальная молярная энергия Гиббса Na+' in text
    assert 'при более низком — как устойчивый' in text
    assert not any(s in text for s in ('порог', 'SEI', 'доказано'))


@pytest.mark.parametrize('old,new', [
    ('Na+ chemical', 'Li+ chemical'), ('μNa+', 'μLi+'),
    ('Na+ intercalation behavior', 'Li+ intercalation behavior'),
    ('free energy of Na+', 'free energy of Li+'), ('stability of Na+', 'stability of Li+'),
    ('(stable) Na+', '(stable) Li+'), ('Gibbs free energy', 'Helmholtz free energy'),
    ('partial molar', 'total'), ('strongly correlates with', 'causes'),
    ('unstable (stable)', 'stable (unstable)'), ('higher (lower)', 'lower (higher)'),
    ('solvation environment', 'SEI environment'), ('graphite negative electrodes', 'positive electrodes'),
])
def test_wrong_quantity_ion_definition_role_or_reversed_direction_refuses(old, new):
    assert not bundle(RAW.replace(old, new)).eligible


@pytest.mark.parametrize('prefix', ['In previous work, ', 'Previously reported ', 'We hypothesize: ',
                                  'Not observed: ', 'References\n'])
def test_prior_negative_hypothetical_or_bibliographic_scope_cannot_supply_definition(prefix):
    assert not bundle(prefix + RAW).eligible


@pytest.mark.parametrize('suffix', [' при 25 °C', ' и порог', ' для всех солей', ' без ограничений',
                                  ' и механизм образования SEI', ' относительно LiFSI'])
def test_additional_query_constraints_cannot_be_discarded(suffix):
    result = bundle(question=QUESTION[:-1] + suffix + '?')
    assert result is None or not result.eligible


def test_ion_selectors_metadata_and_source_scope_are_required():
    assert bundle(RAW.replace('Na+', 'K+'), QUESTION.replace('Na⁺', 'K⁺')).eligible
    for question in (QUESTION.replace('Na⁺', 'Li⁺'), QUESTION.replace('Na⁺', ''), QUESTION.replace('Na⁺', 'Na⁺ и Li⁺')):
        assert not bundle(question=question).eligible
    assert not bundle(metadata={**REF, 'year': '2023'}).eligible
    assert not prepare(QUESTION, [source(RAW, article_id='other')], REF).eligible


def test_line_breaks_micro_sign_and_soft_hyphen_preserve_raw_spans():
    raw = RAW.replace('μNa+', 'µNa\n+').replace('definition', 'def-\ninition').replace('stable)', 'sta-\nble)')
    result = bundle(raw)
    assert result.eligible and 'μNa+' in result.records[0]['allowed_claim']
    for fact in result.records[0]['facts']:
        for value in (fact['sample'], fact['value'], *fact['conditions'].values()):
            a = value['source']
            assert raw[a['start']:a['end']] == a['text']


@pytest.mark.parametrize('field', ['definition', 'trend', 'symbol', 'text', 'claim_kind', 'raw'])
def test_mutated_definition_direction_and_rendering_are_recomputed(field):
    result = bundle()
    payload = json.loads(result.evidence[0].text)
    record = payload['records'][0]
    if field == 'definition':
        record['facts'][1]['value']['text'] = 'total energy'
    elif field == 'trend':
        record['facts'][2]['conditions']['higher_state']['text'] = 'stable'
    elif field == 'symbol':
        record['facts'][0]['sample']['text'] = 'μLi+'
    elif field == 'text':
        record['allowed_claim'] = 'Proven universal mechanism'
    elif field == 'claim_kind':
        record['source_grammar']['claim_kind'] = 'measurement'
    else:
        payload['raw_source'] = RAW.replace('Gibbs', 'Helmholtz')
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0], text=json.dumps(payload))])


def test_exposed_original_pdf_source_recomputes_three_definition_fields():
    j = json.loads(FIXTURE.read_bytes())
    inputs = [Evidence(**e) for e in j['trace']['evidence']]
    before = deepcopy(inputs)
    result = prepare(j['api']['question'], inputs, j['trace']['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible and inputs == before
    assert len(answer_facts.selection_records(result.evidence)['F1']['facts']) == 3
    raw = result.display[0]
    answer_facts.verify_raw_binding(result.evidence[0].text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
        citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end, source_type=raw.source_type)


@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('prose', 502)])
def test_actual_api_synthetic_complete_selection_abstention_and_unbound_prose(monkeypatch, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult
    from scripts.gigachat_answer_smoke import configure

    j = json.loads(FIXTURE.read_bytes())
    data = j['trace']['retrieval']
    raw = SearchResponse(**{**data, 'results': [SearchResult(**r) for r in data['results']]})
    calls, transactions, settings = [], [], configure()

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
            content = {'answerable': mode != 'abstain', 'claims': [] if mode == 'abstain' else [
                {'text': 'F1' if mode == 'select' else 'unbound prose', 'citation_ids': ['E1']}]}
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
                'role': 'assistant', 'content': json.dumps(content)}}]}).encode()

        provider._post = post
        return provider

    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: deepcopy(raw))
    monkeypatch.setattr(routes, 'make_provider', factory)
    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post('/answer/experimental/required-fields', json=j['api'])
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == status and calls == ['synthetic_oauth', 'synthetic_model']
    assert 'READ ONLY' in transactions[0] and transactions[-1] == 'rollback'
    if mode == 'select':
        body = response.json()
        assert body['answer']['status'] == 'answered' and body['delivery_status'] == 'not_evaluated'
        assert 'сильная корреляция' in routes.render(body)
