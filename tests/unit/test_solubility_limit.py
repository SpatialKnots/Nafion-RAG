"""Source-bound solubility threshold, exact comparison and no zero/failed-attempt inference."""
import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import solubility_limit as c
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.generation.reviewed_glyphs import ReviewedGlyphView
from app.retrieval.search import SearchResult
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/nambu_solubility_limit_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ORIGINAL = Evidence(**SAVED['trace']['evidence'][2])
VIEW = ReviewedGlyphView(ORIGINAL, catalogue_binding=c.GLYPHS)
IDENTITY = c.IDENTITY.search(VIEW.text).group()
COMPARISON = c.PATTERN.search(VIEW.text).group()
RAW = IDENTITY+' '+COMPARISON
QUESTION = PREFIX+'Почему в сравнении проводимости авторы не приводят 1 M раствор LiPF₆ в нефторированном DEE?'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def test_identity_selected_concentration_and_qualitative_limit_have_exact_raw_anchors():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 3 and record['arithmetic'] is None
    identity, methods, limit = record['facts']
    assert identity['value']['text'] == '1,2-diethoxyethane' and identity['sample']['text'] == 'DEE'
    assert methods['sample']['text'] == 'LiPF6' and methods['value']['text'] == '1'
    assert methods['unit']['text'] == 'mol dm−3'
    assert methods['conditions']['concentration_reference_temperature']['text'] == '25'
    assert limit['sample']['text'] == 'DEE' and limit['value']['text'] == 'much less than'
    assert limit['conditions']['comparison_concentration']['text'] == '1'
    assert 'exact_solubility' in limit['unknown_fields'] and 'solubility_measurement_temperature' in limit['unknown_fields']
    assert 'concentration_reference_temperature' not in limit['conditions']
    assert record['source_grammar']['concentration_unit_alias'] == 'M_equals_mol_dm_minus3_same_numeric_value'
    assert 'недостаточная растворимость' in record['allowed_claim']
    assert 'не следует' in record['allowed_claim'] and 'неудачная попытка' in record['allowed_claim']
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for value in (fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values()):
            if value:
                a = value['source']
                assert RAW[a['start']:a['end']] == a['text']


@pytest.mark.parametrize('old,new', [
    ('much less than', 'much greater than'), ('much less than', 'equal to'),
    ('much less than', 'less than'), ('much less than', 'not much less than'),
    ('much less than 1', 'much less than 2'), ('1 mol dm−3 at', '2 mol dm−3 at'),
    ('1 mol dm−3', '1 mmol dm−3'), ('1 mol dm−3', '1 mol kg−1'),
    ('LiPF6 (1 mol', 'LiBF4 (1 mol'), ('solubility of LiPF6', 'solubility of LiBF4'),
    ('LiPF6 in DEE', 'LiPF6 in EME'),
    ('FETFEE, EFEE, and ETFEE', 'FETFEE, EFEE, and DEE'),
    ('FETFEE, EFEE, and ETFEE', 'FETFEE, FETFEE, and ETFEE'),
    ('FETFEE, EFEE, and ETFEE', 'OTHER, EFEE, and ETFEE'),
    ('1,2-diethoxyethane', '1,2-difluoroethane'),
    ('DEE, ethylene glycol', 'EME, ethylene glycol'),
    ('ethylene glycol diethyl ether', 'ethylene glycol difluoroethyl ether'),
    ('as the electrolyte', 'as an additive'),
])
def test_wrong_direction_threshold_salt_solvent_identity_units_and_comparison_refuse(old, new):
    assert old in RAW
    assert not bundle(RAW.replace(old, new)).eligible


@pytest.mark.parametrize('prefix', ['References\n', 'Previously reported ', 'In previous work, ',
                                  'Hypothetical: ', 'Unmeasured: ', 'Not observed: '])
@pytest.mark.parametrize('part', [IDENTITY, COMPARISON])
def test_each_identity_and_method_scope_current(prefix, part):
    assert not bundle(RAW.replace(part, prefix+part)).eligible


@pytest.mark.parametrize('question', [
    QUESTION.replace('1 M', '2 M'), QUESTION.replace('1 M', '0 M'),
    QUESTION.replace('1 M', '1 m'), QUESTION.replace('1 M', '1 mol/kg'),
    QUESTION.replace('LiPF₆', 'LiBF4'), QUESTION.replace('DEE?', 'EME?'),
    QUESTION.replace('нефторированном', 'фторированном'),
    QUESTION[:-1]+' и точная растворимость?', QUESTION[:-1]+' при 25 °C?',
    QUESTION[:-1]+' и нулевая проводимость?', QUESTION[:-1]+' для всех солей?',
    QUESTION.replace('не приводят', 'не смогли приготовить'),
])
def test_exact_question_and_no_extra_numeric_temperature_or_failure_requirements(question):
    result = bundle(question=question)
    assert result is None or not result.eligible


def test_other_why_or_negative_query_not_unlocked():
    assert bundle(question=PREFIX+'Почему соль не растворяется в DEE?') is None


def test_aliases_concentration_and_reference_temperature_not_hardcoded():
    raw = (RAW.replace('DEE', 'BASE').replace('LiPF6', 'NaBF4').replace('1 mol dm−3', '2.5 mol dm−3')
           .replace('25°C', '30°C').replace('Figure 3(a)', 'Figure 7(a)'))
    question = QUESTION.replace('DEE?', 'BASE?').replace('LiPF₆', 'NaBF4').replace('1 M', '2.5 M')
    result = bundle(raw, question)
    assert result.eligible and '2.5 mol dm−3' in result.records[0]['allowed_claim']
    assert '30°C' in result.records[0]['allowed_claim'] and '7(a)' in result.records[0]['allowed_claim']


def test_no_cross_parent_spliced_method_reversed_or_ambiguous_identity():
    assert not prepare(QUESTION, [source(IDENTITY), source(COMPARISON, chunk_id='second')], REF).eligible
    assert not bundle(COMPARISON+' '+IDENTITY).eligible
    assert not bundle(RAW+' '+COMPARISON).eligible
    assert not bundle(RAW+' '+IDENTITY).eligible
    assert not bundle(RAW.replace('The solubility', '3.3. Another system The solubility')).eligible


def test_existing_catalogue_two_unit_operations_and_identity_require_one_complete_parent():
    reference = SAVED['trace']['retrieval']['metadata']['explicit_source_reference']
    result = prepare(SAVED['api']['question'], [ORIGINAL], reference)
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['source_grammar']['glyph_decoding']['operations']) == 2
    assert record['facts'][1]['unit']['source']['text'] == 'mol dm¹3'
    assert record['facts'][2]['unit']['source']['text'] == 'mol dm¹3'
    for changed in (replace(ORIGINAL, chunk_id='copy'), replace(ORIGINAL, text=ORIGINAL.text+' '),
                    replace(ORIGINAL, source_type='main_text')):
        assert not prepare(SAVED['api']['question'], [changed], reference).eligible
    short = Evidence(**SAVED['trace']['evidence'][1])
    assert not prepare(SAVED['api']['question'], [short], reference).eligible
    answer_facts.verify_raw_binding(result.evidence[0].text, ORIGINAL.text, article_id=ORIGINAL.article_id,
        chunk_id=ORIGINAL.chunk_id, citation_id=ORIGINAL.citation_id, page_start=1, page_end=2, source_type=ORIGINAL.source_type)


def test_existing_catalogue_required_even_for_source_with_repaired_text(monkeypatch, tmp_path):
    monkeypatch.setattr(c, 'GLYPHS', (tmp_path/'absent.json', c.GLYPHS[1]))
    assert not bundle().eligible


@pytest.mark.parametrize('field', ['raw', 'identity', 'concentration', 'comparison', 'threshold', 'claim'])
def test_record_raw_identity_threshold_and_text_recompute(field):
    result = bundle()
    payload = json.loads(result.evidence[0].text)
    facts = payload['records'][0]['facts']
    if field == 'raw':
        payload['raw_source'] = RAW.replace('much less than', 'equal to')
    elif field == 'identity':
        facts[0]['sample']['text'] = 'EME'
    elif field == 'concentration':
        facts[1]['value']['text'] = '2'
    elif field == 'comparison':
        facts[2]['value']['text'] = 'zero'
    elif field == 'threshold':
        facts[2]['conditions']['comparison_concentration']['text'] = '2'
    else:
        payload['records'][0]['allowed_claim'] = 'Zero conductivity measured; preparation failed'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0], text=json.dumps(payload))])


@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('prose', 502), ('wrong_citation', 502)])
def test_actual_api_synthetic_complete_selection_abstention_and_prose(monkeypatch, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse
    from scripts.gigachat_answer_smoke import configure

    saved = deepcopy(SAVED)
    data = deepcopy(SAVED['trace']['retrieval'])
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
            native = json.loads(body)
            prompt = '\n'.join(m['content'] for m in native['messages'])
            citations = set(re.findall(r'"citation_id"\s*:\s*"(E[1-9][0-9]*)"', prompt))
            assert len(citations) == 1
            citation = next(iter(citations))
            if mode == 'wrong_citation':
                citation = 'E1' if citation != 'E1' else 'E99'
            content = {'answerable': mode != 'abstain', 'claims': [] if mode == 'abstain' else [
                {'text': 'F1' if mode in ('select', 'wrong_citation') else 'unbound prose', 'citation_ids': [citation]}]}
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
            response = client.post('/answer/experimental/required-fields', json=saved['api'])
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == status and calls == ['synthetic_oauth', 'synthetic_model']
    assert 'READ ONLY' in transactions[0] and transactions[-1] == 'rollback'
    if mode == 'select':
        body = response.json()
        assert body['answer']['status'] == 'answered' and body['delivery_status'] == 'not_evaluated'
        assert 'недостаточная растворимость' in routes.render(body) and 'значительно меньше 1 mol dm−3' in routes.render(body)

