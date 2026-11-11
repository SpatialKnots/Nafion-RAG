"""Finite nonuniversality witness, shared units and respectively; not a general proof engine."""
import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import concentration_counterexample as c
from app.generation.fact_types import SourceView
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/kondo_concentration_counterexample_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ORIGINAL = Evidence(**SAVED['trace']['evidence'][3])
VIEW = SourceView(ORIGINAL,join_soft_hyphen_lines=True)
BASIS = c.BASIS.search(VIEW.text).group()
EXAMPLE = c.PATTERN.search(VIEW.text).group()
RAW = BASIS+' '+EXAMPLE
QUESTION = (PREFIX+'Почему сама по себе концентрация LiFSI не является универсальным критерием '
            'подавления совместной интеркаляции?')


def bundle(raw=RAW,question=QUESTION):
    return prepare(question,[source(raw)],REF,answer_language='ru')


def retrieval():
    return deepcopy(SAVED),deepcopy(SAVED['trace']['retrieval'])


def test_explicit_counterexample_keeps_ratios_values_shared_unit_reference_and_modal_status():
    result=bundle()
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts'])==4 and record['arithmetic'] is None
    limitation,first,second,descriptor=record['facts']
    assert limitation['value']['text']=='cannot be defined by the salt concentration'
    assert [(f['sample']['text'],f['value']['text'],f['conditions']['mu']['text']) for f in (first,second)]==[
        ('LiFSI/DEE','1/1.6','23.2'),('LiFSI/F3MEE','1/4.4','24.1')]
    for pair in (first,second):
        assert pair['conditions']['mu_unit']['text']=='kJ mol−1'
        assert pair['conditions']['respectively']['text']=='respectively'
        assert pair['conditions']['reference_ratio']['text']=='1/10'
        assert pair['conditions']['reference_status']['text']=='relative value'
    assert descriptor['value']['text']=='can be a descriptor of graphite reactions'
    assert record['source_grammar']['similarity']=='source_reported_not_independent_tolerance'
    claim=record['allowed_claim']
    assert 'не означает отсутствия влияния концентрации' in claim and 'может служить' in claim
    assert 'относительно LiFSI/DME' in claim and 'по молям (соль/растворитель)' in claim
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for v in (fact['sample'],fact['value'],fact['unit'],fact['method'],*fact['conditions'].values()):
            if v:
                a=v['source']
                assert RAW[a['start']:a['end']]==a['text']


@pytest.mark.parametrize('old,new',[
    ('LiFSI/F3MEE','NaFSI/F3MEE'),('LiFSI/DEE','LiFSI/F3MEE'),('1/4.4','1/1.6'),
    ('1/4.4','2/3.2'),('1/1.6','0/1.6'),('1/4.4','1/0'),('1/10','1/0'),
    ('reversible Li+','reversible Na+'),('their μLi','their μNa'),('that μLi','that μNa'),
    ('Herein, μLi','Herein, μNa'),('that in LiFSI','that in NaFSI'),
    ('kJ mol−1','J mol−1'),('kJ mol−1','V'),('respectively','in reverse order'),
    ('remarkably different','equal'),('values are similar','values are identical'),
    ('cannot be defined','can always be defined'),('can be a descriptor','is a universal law'),
    ('relative value','absolute value'),('S9c','S7d'),
])
def test_wrong_salt_ion_ratios_units_mapping_status_or_reference_refuses(old,new):
    assert old in RAW
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix',['References\n','Previously reported ','In previous work, ',
                                  'Hypothetical: ','Unmeasured: ','Not observed: '])
@pytest.mark.parametrize('part',[BASIS,EXAMPLE])
def test_each_source_scope_must_be_current(prefix,part):
    assert not bundle(RAW.replace(part,prefix+part)).eligible


@pytest.mark.parametrize('question',[
    QUESTION.replace('не является','является'),QUESTION.replace('сама по себе','никогда'),
    QUESTION.replace('универсальным','лучшим'),QUESTION.replace('Почему','Докажите, почему'),
    QUESTION[:-1]+' и механизм?',QUESTION[:-1]+' при 25°C?',QUESTION[:-1]+' для всех солей?',
    QUESTION[:-1]+' и толщина SEI?',QUESTION.replace('LiFSI','NaFSI'),
    QUESTION.replace('LiFSI','LiFSI и NaFSI'),
])
def test_only_exact_nonuniversality_question_supported_no_free_negative_masking(question):
    result=prepare(question,[source(RAW)],REF)
    assert result is None or not result.eligible


def test_other_why_and_negative_question_families_remain_unsupported():
    assert prepare(PREFIX+'Почему LiFSI всегда подавляет совместную интеркаляцию?',[source(RAW)],REF) is None
    assert prepare(PREFIX+'Почему концентрация не влияет на μLi⁺?',[source(RAW)],REF) is None


def test_no_hardcoded_reference_numbers_or_author_similarity_tolerance():
    raw=RAW.replace('Li','Na').replace('FSI','TFSI').replace('DEE','SOL').replace('F3MEE','OTHER')
    raw=raw.replace('1/1.6','3/5').replace('1/4.4','2/7').replace('23.2','18.6').replace('24.1','19.7')
    result=bundle(raw,QUESTION.replace('LiFSI','NaTFSI'))
    assert result.eligible and '18.6 и 19.7 kJ mol−1' in result.records[0]['allowed_claim']
    assert '3/5 и 2/7' in result.records[0]['allowed_claim']


def test_source_order_no_cross_parent_assembly_and_ambiguity():
    assert not bundle(EXAMPLE+' '+BASIS).eligible
    assert not bundle(RAW+' '+EXAMPLE).eligible
    assert not bundle(RAW+' '+BASIS).eligible
    assert not prepare(QUESTION,[source(BASIS),source(EXAMPLE,chunk_id='second')],REF).eligible


def test_original_full_source_and_raw_registry_recompute():
    result=prepare(SAVED['api']['question'],[ORIGINAL],SAVED['trace']['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible and result.display[0].text==ORIGINAL.text
    answer_facts.selection_records(result.evidence)
    assert 'glyph_decoding' not in result.records[0]['source_grammar']
    answer_facts.verify_raw_binding(result.evidence[0].text,ORIGINAL.text,article_id=ORIGINAL.article_id,
        chunk_id=ORIGINAL.chunk_id,citation_id=ORIGINAL.citation_id,page_start=2,page_end=3,source_type=ORIGINAL.source_type)


@pytest.mark.parametrize('field',['raw','ratio','value','unit','status','reference','claim'])
def test_selected_records_recompute_each_scientific_binding(field):
    result=bundle()
    payload=json.loads(result.evidence[0].text)
    first=payload['records'][0]['facts'][1]
    if field=='raw':
        payload['raw_source']=RAW.replace('23.2','24.1')
    elif field=='ratio':
        first['value']['text']='1/4.4'
    elif field in ('value','unit','reference'):
        first['conditions'][{'value':'mu','unit':'mu_unit','reference':'reference_ratio'}[field]]['text']='changed'
    elif field=='status':
        payload['records'][0]['facts'][3]['value']['text']='is a universal law'
    else:
        payload['records'][0]['allowed_claim']='concentration never matters'
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
        assert '1/1.6 и 1/4.4' in routes.render(body) and 'может служить дескриптором' in routes.render(body)
