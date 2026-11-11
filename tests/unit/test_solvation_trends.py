"""Directional/ion/status controls for one finite source explanation, not causal validation."""
import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import solvation_trends as c
from app.generation.fact_types import SourceView
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/kondo_solvation_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ORIGINAL = Evidence(**SAVED['trace']['evidence'][1])
VIEW = SourceView(ORIGINAL,join_soft_hyphen_lines=True)
PREPARATION = c.PREPARATION.search(VIEW.text).group()
TREND = c.TREND.search(VIEW.text).group()
CORRELATION = c.CORRELATION.search(VIEW.text).group()
RAW = ' '.join([PREPARATION,TREND,CORRELATION])
QUESTION = PREFIX + 'Как влияют сольватирующая способность растворителя и концентрация соли на μLi⁺?'


def bundle(raw=RAW,question=QUESTION):
    return prepare(question,[source(raw)],REF,answer_language='ru')


def retrieval():
    return deepcopy(SAVED),deepcopy(SAVED['trace']['retrieval'])


def test_both_directions_and_localized_condition_match_qualified_correlation():
    result=bundle()
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts'])==4 and record['arithmetic'] is None
    solvent,concentration,association,factors=record['facts']
    assert solvent['value']['text']=='increases' and concentration['value']['text']=='increases'
    assert solvent['conditions']['solvation']['text']=='weaker solvation ability of solvents'
    assert concentration['conditions']['concentration']['text']=='higher salt concentration'
    assert concentration['conditions']['localized']['text']=='including a localized high-concentration state'
    assert solvent['conditions']['stability']['text']=='destabilized'
    assert association['value']['text']=='linear correlation' and association['conditions']['status']['text']=='suggesting'
    assert factors['conditions']['basicity']['text']=='Lewis basicity of the anion'
    assert record['source_grammar']['basicity_direction']=='not_asserted'
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified'] and fact['unit'] is None
        assert fact['value']['numeric_value'] is None
        for v in (fact['sample'],fact['value'],*fact['conditions'].values()):
            a=v['source']
            assert RAW[a['start']:a['end']]==a['text']
    claim=record['allowed_claim']
    assert 'ослаблении' in claim and 'повышении концентрации' in claim and 'предложенная авторами интерпретация' in claim
    assert 'SEI' not in claim and '25' not in claim and 'kJ' not in claim


@pytest.mark.parametrize('old,new',[
    ('μLi + increases','μLi + decreases'),('weaker solvation','stronger solvation'),
    ('higher salt concentration','lower salt concentration'),('is destabilized','is stabilized'),
    ('including a localized high-concentration state','excluding a localized high-concentration state'),
    ('linear correlation','proven causal relationship'),('suggesting that','proving that'),
    ('commonly related','universally determined'),('increase in μLi','decrease in μLi'),
    ('pairing of Li+ and FSI−','pairing of Na+ and FSI−'),('FSI−. In summary','TFSI−. In summary'),
    ('interaction between Li+','interaction between Na+'),('mixing LiFSI','mixing NaFSI'),
    ('various LiFSI electrolytes','various LiTFSI electrolytes'),('Figure 2c','Figure 3c'),
    ('coordination number','only solvent activity'),('important factors','only factors'),
    ('Lewis basicity of the anion','Lewis acidity of the cation'),
    ('control the μLi','control the μNa'),('the μLi + values and','the μNa + values and'),
    ('In summary, μLi','In summary, μNa'),
])
def test_wrong_direction_ion_salt_figure_or_epistemic_strength_refuses(old,new):
    assert old in RAW
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix',['Previously reported ','In previous work, ','References\n',
                                  'Hypothetical: ','Unmeasured: ','Not observed: '])
@pytest.mark.parametrize('part',[PREPARATION,TREND,CORRELATION])
def test_each_source_scope_must_be_current(prefix,part):
    assert not bundle(RAW.replace(part,prefix+part)).eligible


@pytest.mark.parametrize('extra',[' и механизм SEI',' при 25°C',' для всех солей',' без ограничений',
                                  ' и численные значения',' и направление эффекта основности аниона'])
def test_extra_constraints_not_dropped(extra):
    assert not bundle(question=QUESTION[:-1]+extra+'?').eligible


def test_query_symbol_and_single_reference_required():
    assert not bundle(question=QUESTION.replace('μLi⁺','μNa⁺')).eligible
    assert not bundle(question=QUESTION.replace('μLi⁺','μLi⁺ и μNa⁺')).eligible
    assert not bundle(question=QUESTION.replace('μLi⁺','')).eligible
    assert not prepare(QUESTION,[source(RAW,article_id='other')],REF).eligible


def test_no_general_why_proof_or_negative_admission():
    for question in (QUESTION.replace('Как влияют','Почему влияют'),QUESTION.replace('Как влияют','Как доказывают')):
        assert prepare(question,[source(RAW)],REF) is None
    assert not bundle(question=QUESTION.replace('влияют','не влияют')).eligible


def test_consistent_other_monovalent_cation_and_anion_codes_not_hardcoded():
    result=bundle(RAW.replace('Li','Na').replace('FSI','TFSI'),QUESTION.replace('Li','Na'))
    assert result.eligible
    claim=result.records[0]['allowed_claim']
    assert 'NaTFSI' in claim and 'Na+' in claim and 'TFSI−' in claim


def test_scope_order_cross_section_duplicates_and_separate_parents_refuse():
    assert not bundle(PREPARATION+' '+CORRELATION+' '+TREND).eligible
    assert not bundle(PREPARATION+' '+TREND+'\n2.2. Another section\n'+CORRELATION).eligible
    assert not bundle(RAW+' '+CORRELATION).eligible
    assert not prepare(QUESTION,[source(PREPARATION+' '+TREND),source(CORRELATION,chunk_id='other')],REF).eligible


def test_source_typography_spaces_preserve_all_raw_anchors():
    for raw in (RAW.replace('FSI−vibration','FSI− vibration'),RAW.replace('μLi +','µLi\n+')):
        result=bundle(raw)
        assert result.eligible
        answer_facts.selection_records(result.evidence)
    saved=prepare(SAVED['api']['question'],[ORIGINAL],SAVED['trace']['retrieval']['metadata']['explicit_source_reference'])
    assert saved.eligible and saved.display[0].text==ORIGINAL.text
    assert 'glyph_decoding' not in saved.records[0]['source_grammar']


@pytest.mark.parametrize('field',['raw','direction','ion','status','claim'])
def test_selected_fields_and_interpretation_recompute(field):
    result=bundle()
    payload=json.loads(result.evidence[0].text)
    if field=='raw':
        payload['raw_source']=RAW.replace('weaker','stronger')
    elif field=='direction':
        payload['records'][0]['facts'][1]['value']['text']='decreases'
    elif field=='ion':
        payload['records'][0]['facts'][0]['conditions']['ion']['text']='Na+'
    elif field=='status':
        payload['records'][0]['facts'][2]['conditions']['status']['text']='proving'
    else:
        payload['records'][0]['allowed_claim']='universal causal law proved'
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
        assert 'ослаблении сольватирующей' in routes.render(body) and 'предложенная авторами интерпретация' in routes.render(body)
