"""Source applicability and possible-shift controls; not independent universal validation."""
import json
import re
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import threshold_scope as c
from app.generation.fact_types import SourceView
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from app.retrieval.source_reference import rank_context
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/kondo_threshold_scope_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ROW = next(r for r in SAVED['pool'] if r['page_start']==5 and r['page_end']==5)
ORIGINAL = Evidence('E1',ROW['article_id'],ROW['chunk_id'],ROW['title'],ROW['doi'],5,5,ROW['source_type'],
                    ROW['full_text'],ROW['score'],ROW['retrieval_method'],ROW['method_scores'],ROW['method_ranks'])
VIEW = SourceView(ORIGINAL,join_soft_hyphen_lines=True)
RAW = c.PATTERN.search(VIEW.text).group()
QUESTION = (PREFIX+'Доказывает ли работа универсальное неизменное значение порога μLi⁺ '
            'для любых солей, добавок и поверхностных покрытий?')


def bundle(raw=RAW,question=QUESTION):
    return prepare(question,[source(raw)],REF,answer_language='ru')


def retrieval():
    rows,roles=rank_context(SAVED['api']['question'],[SearchResult(**r) for r in SAVED['pool']],top_k=5)
    data=deepcopy(SAVED['baseline_trace']['retrieval'])
    data['results']=[asdict(r) for r in rows]
    data['metadata']['explicit_source_reference'].update(roles)
    return deepcopy(SAVED),data


def test_scoped_applicability_possible_shift_and_all_four_contexts_retained():
    result=bundle()
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts'])==6 and record['arithmetic'] is None
    scope,possible,*factors=record['facts']
    assert scope['value']['text']=='various types of LiFSI-based electrolytes'
    assert scope['conditions']['applicability']['text']=='generally applicable'
    assert possible['value']['text']=='may be shifted'
    assert possible['conditions']['condition']['text']=='nature of SEI is significantly changed'
    assert [fact['value']['text'] for fact in factors]==[
        'SEI forming additives','extremely unstable solvent/salt for reduction',
        'passivating binders','functional surface coatings']
    assert all(f['conditions']['modal']['text']=='may be shifted' for f in factors)
    assert record['source_grammar']['shift_direction']=='not_asserted'
    claim=record['allowed_claim']
    assert 'в целом применимый' in claim and 'порог может сдвигаться' in claim
    assert 'не утверждение, что он обязательно происходит' in claim and '10' not in claim and '25' not in claim
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified'] and fact['unit'] is None
        assert fact['value']['numeric_value'] is None
        for v in (fact['sample'],fact['value'],*fact['conditions'].values()):
            a=v['source']
            assert RAW[a['start']:a['end']]==a['text']


@pytest.mark.parametrize('old,new',[
    ('generally applicable','universally applicable'),('may be shifted','will always be shifted'),
    ('may be shifted','cannot be shifted'),('significantly changed','unchanged'),
    ('μLi + is a quantitative','μNa + is a quantitative'),('when μLi','when μNa'),
    ('focus on μLi','focus on μNa'),('The μLi + threshold','The μNa + threshold'),
    ('the Li+ intercalation','the Na+ intercalation'),('Unfavorable Li+','Unfavorable Na+'),
    ('thus, Li+','thus, Na+'),('LiFSI-based','NaFSI-based'),
    ('graphite negative electrodes','silicon negative electrodes'),
    ('SEI forming additives','cathode additives'),('solvent/salt for reduction','solvent/salt for oxidation'),
    ('passivating binders','all binders'),('functional surface coatings','any surface coatings'),
    ('commonly suppressed','always suppressed'),('inorganic-rich SEI','organic-rich CEI'),
])
def test_wrong_symbol_ion_scope_modality_or_conditions_refuse(old,new):
    assert old in RAW
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix',['References\n','Previously reported ','In previous work, ',
                                  'Hypothetical: ','Unmeasured: ','Not observed: '])
def test_modal_exception_cannot_hide_noncurrent_scope(prefix):
    assert not bundle(prefix+RAW).eligible


@pytest.mark.parametrize('question',[
    QUESTION.replace('Доказывает ли','Почему доказывает'),QUESTION.replace('неизменное','повышенное'),
    QUESTION.replace('μLi⁺','μNa⁺'),QUESTION.replace('μLi⁺','μLi⁺ и μNa⁺'),
    QUESTION[:-1]+' при 25°C?',QUESTION[:-1]+' и на сколько сдвигается?',
    QUESTION.replace('любых солей','LiFSI'),QUESTION.replace('для любых','не для любых'),
])
def test_only_complete_fixed_question_admitted_no_proof_or_negative_bypass(question):
    result=prepare(question,[source(RAW)],REF)
    assert result is None or not result.eligible


def test_other_proof_or_universal_questions_are_unsupported():
    assert prepare(PREFIX+'Доказывает ли работа безопасность любых электролитов?',[source(RAW)],REF) is None
    assert prepare(PREFIX+'Универсален ли порог μLi⁺?',[source(RAW)],REF) is None


def test_consistent_other_source_cation_and_salt_not_hardcoded():
    result=bundle(RAW.replace('Li','Na').replace('FSI','TFSI'),QUESTION.replace('Li','Na'))
    assert result.eligible and 'NaTFSI-based' in result.records[0]['allowed_claim']


def test_no_incomplete_cross_parent_cross_subsection_or_ambiguous_bundle():
    split=RAW.index('The μLi + threshold')
    assert not bundle(RAW[:split]).eligible
    assert not bundle(RAW+RAW).eligible
    assert not bundle(RAW[:split]+'2.4. Another system '+RAW[split:]).eligible
    assert not prepare(QUESTION,[source(RAW[:split]),source(RAW[split:],chunk_id='second')],REF).eligible


def test_retention_uses_unchanged_pool_objects_and_original_raw_binding():
    saved,data=retrieval()
    assert len(data['results'])==5 and data['results'][0]['chunk_id']==ORIGINAL.chunk_id
    assert all(row in saved['pool'] for row in data['results'])
    assert data['results']!=saved['baseline_trace']['retrieval']['results']
    result=prepare(saved['api']['question'],[ORIGINAL],data['metadata']['explicit_source_reference'])
    assert result.eligible and result.display[0].text==ORIGINAL.text
    answer_facts.selection_records(result.evidence)
    assert 'glyph_decoding' not in result.records[0]['source_grammar']
    answer_facts.verify_raw_binding(result.evidence[0].text,ORIGINAL.text,article_id=ORIGINAL.article_id,
        chunk_id=ORIGINAL.chunk_id,citation_id='E1',page_start=5,page_end=5,source_type=ORIGINAL.source_type)


@pytest.mark.parametrize('field',['raw','scope','modal','condition','factor','claim'])
def test_output_records_recompute_and_cannot_strengthen_source(field):
    result=bundle()
    payload=json.loads(result.evidence[0].text)
    facts=payload['records'][0]['facts']
    if field=='raw':
        payload['raw_source']=RAW.replace('may be shifted','is unchanged')
    elif field=='scope':
        facts[0]['value']['text']='all salts'
    elif field=='modal':
        facts[1]['value']['text']='must be shifted'
    elif field=='condition':
        facts[1]['conditions']['condition']['text']='SEI is irrelevant'
    elif field=='factor':
        facts[-1]['value']['text']='all electrodes'
    else:
        payload['records'][0]['allowed_claim']='universal invariant threshold proven'
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
        assert 'порог может сдвигаться' in routes.render(body) and 'в целом применимый' in routes.render(body)
