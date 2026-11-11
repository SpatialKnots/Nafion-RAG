"""Finite source interpretation: anion role, modal chain and salt/solvent ownership."""
import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation import conductivity_explanation as c
from app.generation.providers import Evidence, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from tests.unit.test_quantitative_facts import PREFIX, REF, source

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/nambu_conductivity_explanation_source_v01.json'
SAVED = json.loads(FIXTURE.read_bytes())
ORIGINAL = Evidence(**SAVED['trace']['evidence'][1])
RAW = c.PATTERN.search(c.view(ORIGINAL).text).group()
QUESTION = PREFIX+'Как авторы объясняют более высокую проводимость раствора LiPF₆ в FETFEE по сравнению с ETFEE?'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def test_order_concentration_ionic_role_and_modal_chain_have_raw_anchors():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 4 and record['arithmetic'] is None
    observed, partial, anion, group = record['facts']
    assert observed['value']['text'] == 'EFEE > FETFEE > ETFEE'
    assert observed['conditions']['concentration']['text'] == '1'
    assert observed['conditions']['concentration_reference_temperature']['text'] == '25'
    assert partial['value']['text'].startswith('can increase')
    assert anion['sample']['text'] == 'PF6' and anion['conditions']['ion_charge']['text'] == '−'
    assert anion['value']['text'].startswith('may result')
    assert group['value']['text'] == 'may serve as an anion-attracting group'
    assert group['conditions']['formula']['text'] == 'CH2F-'
    assert 'numeric_dissociation_fraction' in anion['unknown_fields']
    text = record['allowed_claim']
    assert 'сольватацию анионов PF6−' in text and 'может усилить' in text
    assert 'может служить' in text and 'независимое доказательство' in text
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for value in (fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values()):
            if value:
                a = value['source']
                assert RAW[a['start']:a['end']] == a['text']


@pytest.mark.parametrize('old,new', [
    ('can increase', 'does increase'), ('can increase', 'cannot increase'),
    ('may result', 'does result'), ('may result', 'may not result'),
    ('may serve', 'must serve'), ('may serve', 'cannot serve'),
    ('higher degree of ionic dissociation', 'lower degree of ionic dissociation'),
    ('increased solvation', 'decreased solvation'), ('PF6− ions', 'PF6+ ions'),
    ('PF6− ions', 'Li+ ions'), ('PF6− ions', 'BF4− ions'),
    ('anion-attracting', 'cation-attracting'), ('CH2F-', 'CF3-'),
    ('partial fluorination', 'polyfluorination'), ('hydrogen bonds', 'covalent bonds'),
    ('acceptability of an electron-pair', 'donability of an electron-pair'),
    ('LiPF6 solution in FETFEE', 'LiBF4 solution in FETFEE'),
    ('LiPF6 (1 mol', 'LiBF4 (1 mol'), ('1 mol dm−3', '1 mmol dm−3'),
    ('EFEE > FETFEE > ETFEE', 'EFEE > ETFEE > FETFEE'),
    ('EFEE > FETFEE > ETFEE', 'FETFEE > FETFEE > ETFEE'),
    ('FETFEE, EFEE, and ETFEE', 'OTHER, EFEE, and ETFEE'),
    ('as the electrolyte', 'as an additive'),
])
def test_wrong_modality_direction_ion_group_salt_units_or_pair_refuse(old, new):
    assert old in RAW
    assert not bundle(RAW.replace(old, new)).eligible


@pytest.mark.parametrize('prefix', ['References\n', 'Previously reported ', 'In previous work, ',
                                  'Hypothetical: ', 'Unmeasured: ', 'Not observed: '])
def test_source_not_current_or_endorsed(prefix):
    assert not bundle(prefix+RAW).eligible


@pytest.mark.parametrize('question', [
    QUESTION.replace('LiPF₆', 'LiBF4'), QUESTION.replace('FETFEE', 'EFEE'),
    QUESTION.replace('ETFEE?', 'DEE?'), QUESTION.replace('более высокую', 'более низкую'),
    QUESTION[:-1]+' и точная проводимость?', QUESTION[:-1]+' и степень диссоциации?',
    QUESTION[:-1]+' при 25 °C?', QUESTION[:-1]+' для всех солей?',
    QUESTION.replace('объясняют', 'доказывают'),
])
def test_exact_query_salt_pair_and_no_extra_requirements(question):
    result = bundle(question=question)
    assert result is None or not result.eligible


def test_other_why_query_not_unlocked():
    assert bundle(question=PREFIX+'Почему проводимость раствора высокая?') is None


def test_source_names_values_and_temperature_not_hardcoded():
    raw = (RAW.replace('FETFEE', 'SOL1').replace('ETFEE', 'SOL2').replace('LiPF6', 'NaBF4')
           .replace('PF6−', 'BF4−').replace('1 mol dm−3', '2 mol dm−3').replace('25°C', '30°C'))
    question = QUESTION.replace('FETFEE', 'SOL1').replace('ETFEE', 'SOL2').replace('LiPF₆', 'NaBF4')
    result = bundle(raw, question)
    assert result.eligible
    assert '2 mol dm−3' in result.records[0]['allowed_claim'] and 'BF4−' in result.records[0]['allowed_claim']


def test_complete_single_parent_not_spliced_or_ambiguous():
    split = RAW.index('The partial')
    assert not prepare(QUESTION, [source(RAW[:split]), source(RAW[split:], chunk_id='second')], REF).eligible
    assert not bundle(RAW+' '+RAW).eligible
    assert not bundle(RAW[:split]+' 3.3. Another system '+RAW[split:]).eligible


def test_reviewed_glyphs_pin_electrolyte_units_and_negative_anion_charge():
    reference = SAVED['trace']['retrieval']['metadata']['explicit_source_reference']
    result = prepare(SAVED['api']['question'], [ORIGINAL], reference)
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['source_grammar']['glyph_decoding']['operations']) == 3
    assert record['facts'][0]['conditions']['concentration_unit']['source']['text'] == 'mol dm¹3'
    charge = record['facts'][2]['conditions']['ion_charge']
    assert charge['source']['text'] == '¹' and charge['text'] == '−'
    assert charge['normalization'].startswith('reviewed_pdf_glyph')
    for changed in (replace(ORIGINAL, chunk_id='copy'), replace(ORIGINAL, text=ORIGINAL.text+' '),
                    replace(ORIGINAL, source_type='main_text')):
        assert not prepare(SAVED['api']['question'], [changed], reference).eligible
    answer_facts.verify_raw_binding(result.evidence[0].text, ORIGINAL.text, article_id=ORIGINAL.article_id,
        chunk_id=ORIGINAL.chunk_id, citation_id=ORIGINAL.citation_id, page_start=2, page_end=3, source_type=ORIGINAL.source_type)


def test_missing_catalogue_does_not_guess_charge(monkeypatch, tmp_path):
    monkeypatch.setattr(c, 'GLYPHS', (tmp_path/'absent.json', c.GLYPHS[1]))
    assert not bundle().eligible


@pytest.mark.parametrize('field', ['raw', 'anion', 'charge', 'modal', 'formula', 'claim'])
def test_source_fields_and_rendered_claim_recomputed(field):
    result = bundle()
    payload = json.loads(result.evidence[0].text)
    facts = payload['records'][0]['facts']
    if field == 'raw':
        payload['raw_source'] = RAW.replace('PF6−', 'BF4−')
    elif field == 'anion':
        facts[2]['sample']['text'] = 'Li'
    elif field == 'charge':
        facts[2]['conditions']['ion_charge']['text'] = '+'
    elif field == 'modal':
        facts[2]['value']['text'] = 'proven lithium cation solvation'
    elif field == 'formula':
        facts[3]['conditions']['formula']['text'] = 'CF3-'
    else:
        payload['records'][0]['allowed_claim'] = 'Mechanism independently proven'
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
        assert 'сольватацию анионов PF6−' in routes.render(body) and 'может служить' in routes.render(body)


def test_other_valid_source_order_retains_requested_pair_without_fixed_ranking():
    result = bundle(RAW.replace('EFEE > FETFEE > ETFEE', 'FETFEE > EFEE > ETFEE'))
    assert result.eligible
    assert 'FETFEE > EFEE > ETFEE' in result.records[0]['allowed_claim']
