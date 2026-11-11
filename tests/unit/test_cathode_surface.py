"""Cathode ownership, grouping and status controls; exposed development sources."""
import json
import re
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import cathode_surface as c
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from app.retrieval.source_reference import rank_context
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/peng_surface_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ROW = next(r for r in SAVED['pool'] if r['page_start']==6 and r['page_end']==7)
ORIGINAL = Evidence('E1', ROW['article_id'], ROW['chunk_id'], ROW['title'], ROW['doi'], 6, 7, ROW['source_type'],
                    ROW['full_text'], ROW['score'], ROW['retrieval_method'], ROW['method_scores'], ROW['method_ranks'])
VIEW = c.view(ORIGINAL)
FRAME = c.FRAME.search(VIEW.text).group()
SEM = c.SEM.search(VIEW.text).group()
XPS = c.XPS.search(VIEW.text).group()
CAPTION = next(m.group() for m in c.CAPTION.finditer(VIEW.text) if m['electrode']=='LCO')
RAW = ' '.join([FRAME,SEM,CAPTION,XPS])
QUESTION = PREFIX + 'Какие изменения морфологии LCO и состава поверхностной плёнки авторы наблюдали после циклирования в FFT?'


def bundle(raw=RAW,question=QUESTION):
    return prepare(question,[source(raw)],REF,answer_language='ru')


def retrieval():
    rows, roles = rank_context(SAVED['api']['question'],[SearchResult(**r) for r in SAVED['pool']],top_k=5)
    data=deepcopy(SAVED['baseline_trace']['retrieval'])
    data['results']=[asdict(r) for r in rows]
    data['metadata']['explicit_source_reference'].update(roles)
    return deepcopy(SAVED),data


def test_cathode_sem_xps_groups_and_interpretation_remain_distinct():
    result=bundle()
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts'])==6 and record['arithmetic'] is None
    fresh,sem,carbon,oxygen,fluorine,interpretation=record['facts']
    assert sem['value']['text']=='almost disappears' and sem['conditions']['label']['text']=='FFT'
    assert carbon['conditions']['carbonyl']['text']=='C=O'
    assert oxygen['conditions']['group']['text']=='two FEC-contained electrolytes'
    assert 'named_formulations_for_component_group' in oxygen['unknown_fields']
    assert not {'label','other2','caption_label','caption_other2'} & oxygen['conditions'].keys()
    assert fluorine['value']['text']=='LixPOyFz' and fluorine['conditions']['f_change']['text']=='lower'
    assert interpretation['conditions']['status']['text']=='suggest'
    claim=record['allowed_claim']
    assert 'почти исчезают' in claim and 'авторы считают' in claim and 'LiF' not in claim
    assert '100' not in claim and '4.45' not in claim and 'SEI' not in claim
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for v in (fact['sample'],fact['value'],fact['unit'],fact['method'],*fact['conditions'].values()):
            if v:
                a=v['source']
                assert RAW[a['start']:a['end']]==a['text']


@pytest.mark.parametrize('old,new',[
    ('The fresh LCO','The fresh MCMB'),('on the LCO surface','on the MCMB surface'),
    ('deeply charged LCO','deeply charged MCMB'),('in the LCO cycled','in the MCMB cycled'),
    ('cycled LCO cathode','cycled MCMB cathode'),('cycled LCO is covered','cycled MCMB is covered'),
    ('(from LCO)','(from MCMB)'),('formed on LCO','formed on MCMB'),('CEI on the LCO','SEI on the MCMB'),
    ('case of FFT','case of OTHER'),('FFT than EE','OTHER than EE'),('FET and FFT than','EET and FFT than'),
    ('in the EET compared','in the OTHER compared'),('Fig. 6e','Fig. 5e'),
    ('compared in Fig. 7','compared in Fig. 9'),('(d) FFT.','(d) OTHER.'),
    ('almost disappears','completely disappears'),('a lower Lix','a higher Lix'),('suggesting the effective','proving the effective'),
    ('results suggest','results prove'),('mainly from FEC decomposition','mainly from OTHER decomposition'),
    ('than those without it','than those with it'),('two FEC-contained','all FEC-contained'),
    ('full cell was','half cell was'),('C=O','C]O'),
])
def test_wrong_owner_labels_figures_scope_trends_groups_or_strength_refuse(old,new):
    assert old in RAW
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix',['Previously reported ','References\n','Hypothetical: ','Unmeasured: ','Not observed: '])
@pytest.mark.parametrize('part',[FRAME,SEM,CAPTION,XPS])
def test_each_scientific_scope_must_be_current(prefix,part):
    assert not bundle(RAW.replace(part,prefix+part)).eligible


@pytest.mark.parametrize('extra',[' и механизм',' при 100 циклах',' и доли LiF',' и толщина плёнки',' без ограничений'])
def test_unasked_numeric_or_causal_requirements_cannot_be_dropped(extra):
    assert not bundle(question=QUESTION[:-1]+extra+'?').eligible


def test_general_why_and_other_requested_owner_refuse():
    assert prepare(QUESTION.replace('Какие изменения','Почему изменения'),[source(RAW)],REF) is None
    assert not bundle(question=QUESTION.replace('морфологии LCO','морфологии MCMB')).eligible
    assert not bundle(question=QUESTION.replace('в FFT','в FET')).eligible


def test_other_source_codes_are_not_hardcoded():
    raw=RAW.replace('LCO','CATH').replace('FFT','SOL').replace('FEC','COMP')
    result=bundle(raw,QUESTION.replace('LCO','CATH').replace('FFT','SOL'))
    assert result.eligible and 'COMP-содержащих' in result.records[0]['allowed_claim']


def test_other_electrode_lif_and_total_f_text_does_not_transfer_to_cathode_claim():
    text=' The XPS spectra obtained from the cycled MCMB show LiF and higher total F in FFT. '
    result=bundle(RAW+text+CAPTION.replace('LCO','MCMB').replace('Fig. 7','Fig. 9'))
    assert result.eligible and result.records[0]['allowed_claim']==bundle().records[0]['allowed_claim']


def test_no_cross_fragment_assembly_or_ambiguous_cathode_records():
    assert not prepare(QUESTION,[source(FRAME+' '+SEM),source(CAPTION+' '+XPS,chunk_id='other')],REF).eligible
    assert not bundle(RAW+' '+XPS).eligible
    assert not bundle(RAW+' '+CAPTION).eligible


def test_original_glyph_identity_and_carbonyl_are_explicit():
    result=prepare(SAVED['api']['question'],[ORIGINAL],SAVED['baseline_trace']['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['source_grammar']['glyph_decoding']['operations'])==6
    value=record['facts'][2]['conditions']['carbonyl']
    assert value['text']=='C=O' and value['source']['text']=='C]O'
    assert value['normalization'].startswith('reviewed_pdf_glyph')
    for changed in (replace(ORIGINAL,chunk_id='copy'),replace(ORIGINAL,text=ORIGINAL.text+' ')):
        ref=SAVED['baseline_trace']['retrieval']['metadata']['explicit_source_reference']
        assert not prepare(SAVED['api']['question'],[changed],ref).eligible


@pytest.mark.parametrize('field',['raw','group','owner','carbonyl','claim'])
def test_record_and_raw_tampering_recompute(field):
    result=bundle()
    payload=json.loads(result.evidence[0].text)
    if field=='raw':
        payload['raw_source']=RAW.replace('almost disappears','completely disappears')
    elif field=='group':
        payload['records'][0]['facts'][3]['conditions']['group']['text']='FFT only'
    elif field=='owner':
        payload['records'][0]['facts'][4]['sample']['text']='MCMB'
    elif field=='carbonyl':
        payload['records'][0]['facts'][2]['conditions']['carbonyl']['text']='C-O'
    else:
        payload['records'][0]['allowed_claim']='LiF-rich SEI on LCO, proven by XPS'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0],text=json.dumps(payload))])


def test_retention_uses_existing_pool_objects_same_top5_and_no_new_lookup():
    saved,current=retrieval()
    assert len(current['results'])==5 and current['results'][0]['chunk_id']==ORIGINAL.chunk_id
    assert all(row in saved['pool'] for row in current['results'])
    assert current['results'] != saved['baseline_trace']['retrieval']['results']
    assert current['metadata']['explicit_source_reference']['source_statement_ownership_verified'] is False


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
        assert 'в FFT почти исчезают' in routes.render(body) and 'группы из двух FEC' in routes.render(body)
