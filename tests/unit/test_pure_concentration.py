"""Pure-state, quantity/unit/temperature and possible-contraction controls; exposed source."""
import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import pure_concentration as c
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/nambu_pure_concentration_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ORIGINAL = Evidence(**SAVED['trace']['evidence'][1])
VIEW = c.view(ORIGINAL)
FRAME = c.FRAME.search(VIEW.text).group()
COMPARISON = c.PATTERN.search(VIEW.text).group()
RAW = FRAME+' '+COMPARISON
QUESTION = (PREFIX+'Почему молярная концентрация чистого FETFEE при 25 °C выше, '
            'чем ETFEE, несмотря на большую молярную массу?')


def bundle(raw=RAW,question=QUESTION):
    return prepare(question,[source(raw)],REF,answer_language='ru')


def retrieval():
    return deepcopy(SAVED),deepcopy(SAVED['trace']['retrieval'])


def test_quantities_masses_temperature_pure_state_and_modal_explanation_bound():
    result=bundle()
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts'])==3 and record['arithmetic'] is None
    higher,lower,hypothesis=record['facts']
    assert [(f['sample']['text'],f['value']['text'],f['conditions']['molar_mass']['text']) for f in (higher,lower)]==[
        ('FETFEE','6.50','190.14'),('ETFEE','6.38','172.15')]
    assert all(f['unit']['text']=='mol dm−3' and f['conditions']['molar_mass_unit']['text']=='g mol−1' for f in (higher,lower))
    assert higher['conditions']['temperature']['text']=='25' and higher['conditions']['specimen_state']['text']=='single solvents'
    assert hypothesis['value']['text']=='may contract to some extent'
    assert 'numerical_mass_density' in hypothesis['unknown_fields']
    claim=record['allowed_claim']
    assert 'возможным сжатием' in claim and 'может в некоторой степени сжиматься' in claim
    assert 'численная плотность и степень сжатия' in claim and 'LiPF6' not in claim
    assert record['source_grammar']['density_calculation']=='not_performed'
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for v in (fact['sample'],fact['value'],fact['unit'],fact['method'],*fact['conditions'].values()):
            if v:
                a=v['source']
                assert RAW[a['start']:a['end']]==a['text']


@pytest.mark.parametrize('old,new',[
    ('6.50','6.38'),('6.50','6.20'),('6.38','0'),('190.14','172.15'),('190.14','170.0'),('172.15','0'),
    ('mol dm−3','mol dm13'),('mol dm−3','mmol dm−3'),('g mol−1','g mol11'),('g mol−1','kg mol−1'),
    ('at 25°C) was','at 30°C) was'),('at 25°C) in','at 30°C) in'),
    ('may contract to some extent','does contract to some extent'),('may contract to some extent','cannot contract'),
    ('strong attractive forces','strong repulsive forces'),('between FETFEE molecules','between ETFEE molecules'),
    ('concentration of FETFEE increased','concentration of ETFEE increased'),
    ('190.14 g mol−1 for FETFEE','190.14 g mol−1 for ETFEE'),
    ('single solvents','electrolyte solutions'),('FETFEE, EFEE','OTHER, EFEE'),
])
def test_wrong_relation_quantities_units_pair_temperature_state_or_strength_refuse(old,new):
    assert old in RAW
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix',['References\n','Previously reported ','In previous work, ',
                                  'Hypothetical: ','Unmeasured: ','Not observed: '])
@pytest.mark.parametrize('part',[FRAME,COMPARISON])
def test_each_scientific_scope_must_be_current(prefix,part):
    assert not bundle(RAW.replace(part,prefix+part)).eligible


@pytest.mark.parametrize('question',[
    QUESTION.replace('25 °C','30 °C'),QUESTION.replace('FETFEE','EFEE'),
    QUESTION.replace('чистого','раствора'),QUESTION.replace('выше','ниже'),
    QUESTION[:-1]+' в 1 M LiPF6?',QUESTION[:-1]+' и точная плотность?',
    QUESTION[:-1]+' и численная степень сжатия?',QUESTION[:-1]+' для всех растворителей?',
    QUESTION.replace('несмотря','без учёта'),
])
def test_exact_pair_pure_state_and_temperature_query_no_additional_requirements(question):
    result=prepare(question,[source(RAW)],REF)
    assert result is None or not result.eligible


def test_other_why_questions_not_unlocked():
    assert prepare(PREFIX+'Почему FETFEE обладает высокой проводимостью?',[source(RAW)],REF) is None


def test_names_numbers_and_temperature_are_not_hardcoded():
    raw=(RAW.replace('FETFEE','SOL1').replace('ETFEE','SOL2').replace('25°C','30°C')
         .replace('6.50','7.40').replace('6.38','6.90').replace('190.14','210.4').replace('172.15','185.6'))
    question=QUESTION.replace('FETFEE','SOL1').replace('ETFEE','SOL2').replace('25 °C','30 °C')
    result=bundle(raw,question)
    assert result.eligible and '7.40 mol dm−3' in result.records[0]['allowed_claim']
    assert '210.4 g mol−1' in result.records[0]['allowed_claim']


def test_no_cross_parent_cross_subsection_ambiguous_or_reversed_scope():
    assert not prepare(QUESTION,[source(FRAME),source(COMPARISON,chunk_id='second')],REF).eligible
    assert not bundle(COMPARISON+' '+FRAME).eligible
    assert not bundle(RAW+' '+COMPARISON).eligible
    assert not bundle(FRAME+'\n3.2 Another system\n'+COMPARISON).eligible
    assert not bundle(FRAME+' 3.2. Another system '+COMPARISON).eligible


def test_original_glyph_identity_and_raw_quantity_units_recompute():
    result=prepare(SAVED['api']['question'],[ORIGINAL],SAVED['trace']['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['source_grammar']['glyph_decoding']['operations'])==4
    for fact in record['facts'][:2]:
        assert fact['unit']['source']['text']=='mol dm¹3'
        assert fact['conditions']['molar_mass_unit']['source']['text']=='g mol¹1'
        assert fact['unit']['normalization'].startswith('reviewed_pdf_glyph')
    for changed in (replace(ORIGINAL,chunk_id='copy'),replace(ORIGINAL,text=ORIGINAL.text+' '),
                    replace(ORIGINAL,source_type='main_text')):
        ref=SAVED['trace']['retrieval']['metadata']['explicit_source_reference']
        assert not prepare(SAVED['api']['question'],[changed],ref).eligible
    answer_facts.verify_raw_binding(result.evidence[0].text,ORIGINAL.text,article_id=ORIGINAL.article_id,
        chunk_id=ORIGINAL.chunk_id,citation_id=ORIGINAL.citation_id,page_start=2,page_end=2,source_type=ORIGINAL.source_type)


def test_missing_catalogue_cannot_guess_the_unit_sign(monkeypatch,tmp_path):
    monkeypatch.setattr(c,'GLYPHS',(tmp_path/'absent.json',c.GLYPHS[1]))
    assert not bundle().eligible


@pytest.mark.parametrize('field',['raw','concentration','mass','temperature','state','modal','claim'])
def test_record_scientific_bindings_recompute(field):
    result=bundle()
    payload=json.loads(result.evidence[0].text)
    facts=payload['records'][0]['facts']
    if field=='raw':
        payload['raw_source']=RAW.replace('6.50','9.50')
    elif field=='concentration':
        facts[0]['value']['text']='9.50'
    elif field in ('mass','temperature','state'):
        facts[0]['conditions'][{'mass':'molar_mass','temperature':'temperature','state':'specimen_state'}[field]]['text']='changed'
    elif field=='modal':
        facts[2]['value']['text']='measured volume contraction'
    else:
        payload['records'][0]['allowed_claim']='density and structure independently proven'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0],text=json.dumps(payload))])


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
        assert '6.50 mol dm−3' in routes.render(body) and 'может в некоторой степени сжиматься' in routes.render(body)
