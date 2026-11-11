"""SEI necessity/sufficiency, sequence and modality controls; exposed development source."""
import json
import re
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import sei_sufficiency as c
from app.generation.fact_types import SourceView
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from app.retrieval.source_reference import rank_context
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/kondo_sei_sufficiency_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ROW = next(r for r in SAVED['pool'] if r['page_start']==3 and r['page_end']==4)
ORIGINAL = Evidence('E1',ROW['article_id'],ROW['chunk_id'],ROW['title'],ROW['doi'],3,4,ROW['source_type'],
                    ROW['full_text'],ROW['score'],ROW['retrieval_method'],ROW['method_scores'],ROW['method_ranks'])
VIEW = SourceView(ORIGINAL,join_soft_hyphen_lines=True)
PROPOSAL = c.PROPOSAL.search(VIEW.text).group()
CONTRIBUTION = c.CONTRIBUTION.search(VIEW.text).group()
OBSERVATIONS = c.OBSERVATIONS.search(VIEW.text).group()
CONCLUSION = c.CONCLUSION.search(VIEW.text).group()
RAW = ' '.join([PROPOSAL,CONTRIBUTION,OBSERVATIONS,CONCLUSION])
QUESTION = (PREFIX+'Достаточно ли одного образования SEI из продуктов разложения аниона FSI⁻, '
            'чтобы гарантировать отсутствие совместной интеркаляции растворителя?')


def bundle(raw=RAW,question=QUESTION):
    return prepare(question,[source(raw)],REF,answer_language='ru')


def retrieval():
    rows,roles=rank_context(SAVED['api']['question'],[SearchResult(**r) for r in SAVED['pool']],top_k=5)
    data=deepcopy(SAVED['baseline_trace']['retrieval'])
    data['results']=[asdict(r) for r in rows]
    data['metadata']['explicit_source_reference'].update(roles)
    return deepcopy(SAVED),data


def test_partial_contribution_comparison_preformation_sequence_and_modality_kept_distinct():
    result=bundle()
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts'])==5 and record['arithmetic'] is None
    mechanism,partial,similar,challenge,limit=record['facts']
    assert mechanism['conditions']['status']['text']=='we suppose'
    assert 'to some extent' in partial['value']['text']
    assert similar['conditions']['ratio1']['text']=='1/2' and similar['conditions']['ratio2']['text']=='1/3'
    assert similar['conditions']['no_change']['text']=='did not remarkably change'
    assert challenge['conditions']['challenge']['text']=='1/3' and challenge['conditions']['formed']['text']=='1/2'
    assert challenge['value']['text']=='could not be suppressed'
    assert limit['value']['text']=='may not be the only dominant factor'
    assert limit['conditions']['essential']['text']=='essential for suppressing electrolyte decomposition'
    claim=record['allowed_claim']
    assert claim.startswith('Нет:')
    assert 'а не утверждение об отсутствии вклада SEI' in claim and 'в некоторой степени' in claim
    assert 'предполагают два механизма' in claim and '1/3 по молям' in claim and '1/2 по молям' in claim
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for v in (fact['sample'],fact['value'],fact['unit'],fact['method'],*fact['conditions'].values()):
            if v:
                a=v['source']
                assert RAW[a['start']:a['end']]==a['text']


@pytest.mark.parametrize('old,new',[
    ('we suppose','we proved'),('to some extent','in every case'),
    ('formation of FSI','formation of TFSI'),('similar FSI','similar TFSI'),
    ('LiFSI/DME (1/3 by mol)','LiFSI/OTHER (1/3 by mol)'),
    ('forming SEI in LiFSI/DME','forming SEI in NaFSI/DME'),
    ('LiFSI/DME (1/3 by mol)','LiFSI/DME (1/2 by mol)'),
    ('LiFSI/DME (1/2 by mol)','LiFSI/DME (1/3 by mol)'),
    ('1/2 and 1/3','1/2 and 2/4'),('1/2 and 1/3','1/0 and 1/3'),
    ('1/2 and 1/3','1/2 and 0/3'),('by mol','by weight'),
    ('did not remarkably change','did remarkably change'),
    ('could not be suppressed','was fully suppressed'),('even after forming','before forming'),
    ('remarkably different graphite reactions','identical graphite reactions'),
    ('may not be the only dominant factor','is never a relevant factor'),
    ('essential for suppressing electrolyte decomposition','sufficient for suppressing cointercalation'),
    ('with higher μLi','with lower μLi'),('solvated Li+','solvated Na+'),
    ('high-μLi','high-μNa'),('depending on μLi','depending on μNa'),
    ('boundary μLi','boundary μNa'),('S24','S23'),
])
def test_wrong_ion_origin_ratios_sequence_results_or_strength_refuse(old,new):
    assert old in RAW
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix',['References\n','Previously reported ','In previous work, ',
                                  'Hypothetical: ','Unmeasured: ','Not observed: '])
@pytest.mark.parametrize('part',[PROPOSAL,CONTRIBUTION,OBSERVATIONS,CONCLUSION])
def test_status_exceptions_cannot_hide_prior_hypothetical_or_negative_leads(prefix,part):
    assert not bundle(RAW.replace(part,prefix+part)).eligible


@pytest.mark.parametrize('question',[
    QUESTION.replace('одного образования','любого образования'),QUESTION.replace('SEI','CEI'),
    QUESTION.replace('FSI⁻','TFSI⁻'),QUESTION.replace('отсутствие','наличие'),
    QUESTION[:-1]+' при 25°C?',QUESTION[:-1]+' и точный механизм?',
    QUESTION[:-1]+' для всех электродов?',QUESTION.replace('FSI⁻','FSI⁻ и TFSI⁻'),
])
def test_query_is_exact_sufficiency_scope_with_no_unknown_constraints(question):
    result=prepare(question,[source(RAW)],REF)
    assert result is None or not result.eligible


def test_other_sufficiency_and_guarantee_questions_not_unlocked():
    assert prepare(PREFIX+'Достаточно ли SEI для работы аккумулятора?',[source(RAW)],REF) is None
    assert prepare(PREFIX+'Почему SEI гарантирует отсутствие совместной интеркаляции?',[source(RAW)],REF) is None


def test_other_codes_ratios_and_charged_anion_are_source_driven():
    raw=RAW.replace('Li','Na').replace('FSI','TFSI').replace('DME','SOL').replace('1/2','1/4').replace('1/3','1/5')
    result=bundle(raw,QUESTION.replace('FSI','TFSI'))
    assert result.eligible and 'NaTFSI/SOL' in result.records[0]['allowed_claim']
    assert '1/5 по молям' in result.records[0]['allowed_claim'] and '1/4 по молям' in result.records[0]['allowed_claim']


def test_no_partial_or_cross_parent_assembly_or_ambiguous_source():
    assert not bundle(PROPOSAL+' '+CONTRIBUTION+' '+OBSERVATIONS).eligible
    assert not bundle(RAW+' '+CONCLUSION).eligible
    assert not bundle(CONCLUSION+' '+PROPOSAL+' '+CONTRIBUTION+' '+OBSERVATIONS).eligible
    assert not prepare(QUESTION,[source(PROPOSAL+' '+CONTRIBUTION+' '+OBSERVATIONS),
                                source(CONCLUSION,chunk_id='second')],REF).eligible


def test_existing_pool_object_retained_same_top5_and_raw_binding():
    saved,data=retrieval()
    assert len(data['results'])==5 and data['results'][0]['chunk_id']==ORIGINAL.chunk_id
    assert all(row in saved['pool'] for row in data['results'])
    assert data['results']!=saved['baseline_trace']['retrieval']['results']
    result=prepare(saved['api']['question'],[ORIGINAL],data['metadata']['explicit_source_reference'])
    assert result.eligible and result.display[0].text==ORIGINAL.text
    answer_facts.selection_records(result.evidence)
    assert 'glyph_decoding' not in result.records[0]['source_grammar']
    answer_facts.verify_raw_binding(result.evidence[0].text,ORIGINAL.text,article_id=ORIGINAL.article_id,
        chunk_id=ORIGINAL.chunk_id,citation_id='E1',page_start=3,page_end=4,source_type=ORIGINAL.source_type)


@pytest.mark.parametrize('field',['raw','formation','challenge','contribution','modality','claim'])
def test_record_raw_role_and_modality_tampering_recompute(field):
    result=bundle()
    payload=json.loads(result.evidence[0].text)
    facts=payload['records'][0]['facts']
    if field=='raw':
        payload['raw_source']=RAW.replace('could not be suppressed','was suppressed')
    elif field=='formation':
        facts[3]['conditions']['formed']['text']='1/3'
    elif field=='challenge':
        facts[3]['conditions']['challenge']['text']='1/2'
    elif field=='contribution':
        facts[1]['value']['text']='has no effect'
    elif field=='modality':
        facts[4]['value']['text']='SEI never matters'
    else:
        payload['records'][0]['allowed_claim']='SEI cannot suppress any side reactions'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0],text=json.dumps(payload))])


def test_conclusion_from_another_subsection_cannot_complete_sufficiency_bundle():
    raw = RAW.replace(CONCLUSION, '2.4. Another system\n' + CONCLUSION)
    assert not bundle(raw).eligible


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
        assert 'после предварительного формирования SEI' in routes.render(body) and 'может быть не единственным' in routes.render(body)
