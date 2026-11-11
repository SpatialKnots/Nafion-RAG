"""Finite conditions and nontransfer caveat; exposed source, no independent science."""
import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import cell_solution_conditions as c
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/nambu_cell_conditions_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ORIGINAL = Evidence(**SAVED['trace']['evidence'][-1])
VIEW = c.view(ORIGINAL)
BODY = c.BODY.search(VIEW.text).group()
CAPTION = c.CAPTION.search(VIEW.text).group()
RAW = BODY + ' ' + CAPTION
QUESTION = (PREFIX + 'Какие концентрации LiPF₆ и смеси растворителей применяли в сравнительных испытаниях '
            'Li/LiCoO₂, и почему важно не смешивать эти условия?')


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def retrieval():
    return deepcopy(SAVED), deepcopy(SAVED['trace']['retrieval'])


def test_separate_conditions_complete_bindings_and_literal_units():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert [(f['sample']['text'], f['value']['text']) for f in record['facts'][:4]] == [
        ('EC–FETFEE', '1'), ('EC–EFEE', '1'), ('EC–DEE', '1'), ('EC–ETFEE', '0.5')]
    assert record['facts'][-1]['conditions']['minC']['text'] == '−5'
    assert record['arithmetic'] is None
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for value in (fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values()):
            if value:
                a=value['source']
                assert RAW[a['start']:a['end']] == a['text']
    assert 'отдельные причинные вклады' in record['allowed_claim']


@pytest.mark.parametrize('old,new', [
    ('0.5 mol', '1 mol'), ('0.5 mol', '0 mol'), ('1 mol', '0 mol'),
    ('LiPF6 solutions in EC', 'NaPF6 solutions in EC'), ('LiPF6 solution in an', 'NaPF6 solution in an'),
    ('Figure 3.','Figure 4.'), ('Li | LiCoO2','Li | Other'), ('EC–ETFEE','EC–DEE'),
    ('EC–DEE','OTHER–DEE'), ('EC–DEE','EC–EC'), ('EC–FETFEE','EC–UNKNOWN'),
    ('mol dm−3','mmol dm−3'), ('mol dm−3','mol dm13'), ('(−5°C)','(90°C)'),
    ('333.15 K','200 K'), ('We used LiPF6 (1','We used LiPF6 (2'),
    ('equimolar binary mixtures','volume binary mixtures'), ('and 0.5','or 0.5'),
    ('(b) Variation','(c) Variation'), ('conductivities','hypothetical conductivities'),
])
def test_mixed_experiments_missing_units_ambiguity_and_inconsistent_conditions_refuse(old,new):
    assert not bundle(RAW.replace(old,new)).eligible


@pytest.mark.parametrize('prefix', ['References\n', 'Previously reported ', 'In previous work, ', 'Not observed: '])
def test_noncurrent_scopes_refuse(prefix):
    assert not bundle(prefix+RAW).eligible
    assert not bundle(BODY+' '+prefix+CAPTION).eligible


@pytest.mark.parametrize('tail', ['и почему это повышает ёмкость?', 'и почему это доказано?',
    'и почему важно не смешивать эти условия при 30°C?', 'и почему важно не смешивать все условия?',
    'и почему важно не смешивать эти условия и каков механизм?'])
def test_exact_methodological_tail_cannot_admit_other_causal_or_universal_questions(tail):
    result=bundle(question=QUESTION.replace('и почему важно не смешивать эти условия?',tail))
    assert result is None or not result.eligible


@pytest.mark.parametrize('extra',[' при 30°C',' без ограничений',' и вязкость',' и механизм'])
def test_extra_requirements_in_main_question_refuse(extra):
    assert not bundle(question=QUESTION.replace(', и почему',extra+', и почему')).eligible


def test_source_identity_glyph_catalogue_and_recomputation():
    result=prepare(SAVED['api']['question'], [ORIGINAL], SAVED['trace']['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible
    record=answer_facts.selection_records(result.evidence)['F1']
    assert len(record['source_grammar']['glyph_decoding']['operations']) == 6
    changed=replace(ORIGINAL,chunk_id='other')
    assert not prepare(SAVED['api']['question'],[changed],SAVED['trace']['retrieval']['metadata']['explicit_source_reference']).eligible
    payload=json.loads(result.evidence[0].text)
    payload['records'][0]['facts'][3]['value']['text']='1'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0],text=json.dumps(payload))])


def test_complete_parent_required_no_cross_chunk_assembly_or_ambiguous_caption():
    assert not prepare(QUESTION,[source(BODY),source(CAPTION,chunk_id='second')],REF).eligible
    assert not bundle(RAW+' '+CAPTION).eligible


def test_values_names_and_temperatures_are_not_hardcoded():
    raw=(RAW.replace('LiPF6','NaPF6').replace('Li | LiCoO2','Na | Cath')
         .replace('1 mol','2 mol').replace('0.5 mol','0.7 mol').replace('25°C','31°C'))
    result=bundle(raw,QUESTION.replace('LiPF₆','NaPF6').replace('Li/LiCoO₂','Na/Cath'))
    assert result.eligible and '0.7 mol dm−3' in result.records[0]['allowed_claim']
    assert '31°C' in result.records[0]['allowed_claim']


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
        assert 'EC–ETFEE — 0.5' in routes.render(body) and 'Отдельное измерение проводимости' in routes.render(body)
