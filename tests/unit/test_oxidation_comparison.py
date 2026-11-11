"""Bound paired observations; exposed development source, not independent accuracy."""
import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import oxidation_comparison as c
from app.generation.fact_types import FactPatternError
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/peng_oxidation_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ORIGINAL = Evidence(**SAVED['trace']['evidence'][2])
VIEW = c.view(ORIGINAL)
BASE = c.BASE.search(VIEW.text).group()
FORMULATION = next(m.group() for m in c.FORMULATION.finditer(VIEW.text) if m['label'] == 'FFT')
METHOD = c.METHOD.search(VIEW.text).group()
HEAD = c.HEAD.search(VIEW.text).group()
RESULT = c.RESULT.search(VIEW.text).group()
RAW = ' '.join([BASE, FORMULATION, METHOD, HEAD, RESULT])
QUESTION = PREFIX + 'Как фторирование повлияло на устойчивость электролита к окислению по данным LSV и float-test?'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def retrieval():
    return deepcopy(SAVED), deepcopy(SAVED['trace']['retrieval'])


def test_separate_methods_and_approximate_limits_keep_all_bindings_and_status():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 7 and record['arithmetic'] is None
    base, mixed, floating, lsv, comparison, first, last = record['facts']
    assert base['conditions']['basis']['text'] == 'by volume'
    assert mixed['conditions']['basis']['text'] == 'by weight'
    assert floating['value']['text'] == '4.6' and floating['conditions']['time']['text'] == '20'
    assert lsv['value']['text'] == '5' and lsv['unit']['text'] == 'mV s−1'
    assert first['value']['text'] == '5.5' and first['conditions']['base_approx']['text'] == '~'
    assert last['value']['text'] == '6.4' and last['conditions']['approx']['text'] == '~'
    assert 'suggesting' in comparison['conditions']['interpretation']['text']
    assert 'can be obtained' in last['conditions']['conclusion']['text']
    claim = record['allowed_claim']
    assert 'примерно с 5.5 V' in claim and 'примерно до 6.4 V' in claim
    assert 'трактуют как признак' in claim and 'не задаёт рабочее напряжение' in claim
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for v in (fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values()):
            if v:
                a = v['source']
                assert RAW[a['start']:a['end']] == a['text']


@pytest.mark.parametrize('old,new', [
    ('marked as EE','marked as OTHER'), ('FFT:','OTHER:'), ('which EE','which OTHER'),
    ('observed in the EE','observed in the OTHER'), ('1 M LiPF6 dissolved in FEC','2 M LiPF6 dissolved in FEC'),
    ('1 M LiPF6 dissolved in FEC','1 M NaPF6 dissolved in FEC'), ('at 4.6 V for','at 4.7 V for'),
    ('(vs. Li+/Li)','(vs. Na+/Na)'), ('and Li metal','and Na metal'), ('LCO/Li cell','LCO/Na cell'),
    ('0.1C','0C'), ('20 h','0 h'), ('5 mV','0 mV'), ('mV s−1','mV s1'), ('mV s−1','V s−1'),
    ('~5.5','5.5'), ('~6.4','6.4'), ('~5.5','~6.5'), ('~5.5','~0'), ('Fig. 1b','Fig. 2b'),
    ('suggesting irreversible','proving irreversible'), ('reduced leakage','increased leakage'),
    ('quite stable until','unstable until'), ('can be obtained','is guaranteed'),
    ('by volume','by weight'), ('3/6/1 ratio','3/0/1 ratio'), ('FEC/FEMC/TFEE','FEC/FEMC/FEC'),
    ('perfluorinated electrolyte','nonfluorinated electrolyte'),
])
def test_inconsistent_labels_dose_reference_units_trends_approximation_or_conditions_refuse(old,new):
    assert old in RAW
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix', ['References\n', 'Previously reported ', 'In previous work, ',
                                  'Not observed: ', 'Hypothetical: ', 'Unmeasured: '])
@pytest.mark.parametrize('part', [BASE, FORMULATION, METHOD, HEAD, RESULT])
def test_each_required_scope_must_be_current_and_observed(prefix,part):
    assert not bundle(RAW.replace(part,prefix+part)).eligible


@pytest.mark.parametrize('extra', [' и механизм', ' при 30°C', ' для всех электролитов', ' без ограничений',
                                   ' и численные токи утечки', ' и HOMO'])
def test_unknown_or_causal_requirements_not_discarded(extra):
    assert not bundle(question=QUESTION[:-1]+extra+'?').eligible


def test_general_why_and_negative_question_cannot_use_observation_contract():
    assert prepare(QUESTION.replace('Как фторирование повлияло','Почему фторирование повлияло'),[source(RAW)],REF) is None
    assert not bundle(question=QUESTION.replace('повлияло','не повлияло')).eligible


def test_values_codes_and_regimes_are_source_driven():
    raw = (RAW.replace('EE','AA').replace('FFT','XYZ').replace('Li','Na').replace('0.1C','0.2C')
           .replace('20 h','12 h').replace('4.6 V','4.8 V').replace('~5.5','~5.1').replace('~6.4','~6.7'))
    result = bundle(raw)
    assert result.eligible
    text = result.records[0]['allowed_claim']
    assert '12 h' in text and 'примерно до 6.7 V' in text and 'Na — электрод сравнения' in text


def test_original_glyph_identity_approximation_and_unit_recompute():
    result = prepare(SAVED['api']['question'], [ORIGINAL], SAVED['trace']['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['source_grammar']['glyph_decoding']['operations']) == 10
    assert record['facts'][3]['unit']['source']['text'] == 'mV s\x011'
    assert record['facts'][-1]['conditions']['approx']['source']['text'] == '\x03'
    assert record['facts'][-1]['conditions']['approx']['normalization'].startswith('reviewed_pdf_glyph')
    for changed in (replace(ORIGINAL,chunk_id='copy'),replace(ORIGINAL,text=ORIGINAL.text+' '),
                    replace(ORIGINAL,source_type='main_text')):
        assert not prepare(SAVED['api']['question'],[changed],SAVED['trace']['retrieval']['metadata']['explicit_source_reference']).eligible


@pytest.mark.parametrize('field',['raw','approx','unit','claim','interpretation'])
def test_tampering_rejected_by_raw_recomputation(field):
    result=bundle()
    payload=json.loads(result.evidence[0].text)
    if field=='raw':
        payload['raw_source']=RAW.replace('~6.4','~6.8')
    elif field=='claim':
        payload['records'][0]['allowed_claim']='safe operating voltage 6.4 V'
    elif field=='unit':
        payload['records'][0]['facts'][3]['unit']['text']='V s−1'
    elif field=='interpretation':
        payload['records'][0]['facts'][4]['conditions']['interpretation']['text']='proven decomposition'
    else:
        payload['records'][0]['facts'][-1]['conditions']['approx']['text']='exact'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0],text=json.dumps(payload))])


def test_no_cross_fragment_assembly_and_no_duplicate_result_or_formulation():
    assert not prepare(QUESTION,[source(BASE+' '+FORMULATION+' '+METHOD),source(HEAD+' '+RESULT,chunk_id='second')],REF).eligible
    assert not bundle(RAW+' '+RESULT).eligible
    assert not bundle(RAW+' '+FORMULATION).eligible


def test_missing_or_changed_catalogue_refuses(monkeypatch,tmp_path):
    monkeypatch.setattr(c,'GLYPHS',(tmp_path/'absent.json',c.GLYPHS[1]))
    assert not bundle().eligible
    with pytest.raises(FactPatternError):
        c.view(ORIGINAL)


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

    saved, data = retrieval()
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
        assert 'примерно с 5.5 V' in routes.render(body) and 'примерно до 6.4 V' in routes.render(body)
