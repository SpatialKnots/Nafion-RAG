"""Finite nomenclature/alias correspondence controls, not independent chemistry labels."""
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.quantitative_facts import prepare
from tests.unit.test_quantitative_facts import PREFIX, REF, source

QUESTION = PREFIX + ('Какие три фторированных диалкиловых эфира исследовались и какова степень '
                     'их фторирования относительно BASE?')
ONE = '1-ethoxy-2-(2-fluoroethoxy)ethane'
THREE = '1-ethoxy-2-(2,2,2-trifluoroethoxy)ethane'
FOUR = '1-(2-fluoroethoxy)-2-(2,2,2-trifluoroethoxy)ethane'
RAW = ('The reference is 1,2-diethoxyethane (BASE, ethylene glycol diethyl ether). '
       'In the present paper, we describe the physical and electrochemical properties of three '
       f'fluorinated dialkyl ethers: {FOUR} (AAA), {THREE} (BBB), {ONE} (CCC). '
       'CCC, BBB, and AAA correspond to monofluorinated, trifluorinated, and tetrafluorinated BASEs.')
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/nambu_identity_source_v01.json'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def test_names_and_fluorination_are_joined_by_alias_instead_of_list_position():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert [(f['sample']['text'], f['value']['text'], f['conditions']['degree']['text']) for f in record['facts']] == [
        ('AAA', FOUR, 'tetrafluorinated'), ('BBB', THREE, 'trifluorinated'), ('CCC', ONE, 'monofluorinated')]
    for fact in record['facts']:
        assert fact['unit'] is None and fact['value']['numeric_value'] is None
        assert fact['epistemic_status'] == 'source_declared_chemical_identity' and not fact['scientific_ownership_verified']
        assert fact['conditions']['item_count']['numeric_value'] == '3'
        for value in (fact['sample'], fact['value'], *fact['conditions'].values()):
            anchor = value['source']
            assert RAW[anchor['start']:anchor['end']] == anchor['text']
    claim = answer_facts.resolve_selections([GeneratedClaim('F1', ['E1'])], result.evidence)[0].text
    assert all(name in claim for name in (ONE, THREE, FOUR))
    assert 'тетрафторированный вариант BASE' in claim and 'синтез' not in claim


@pytest.mark.parametrize('old,new', [
    ('CCC, BBB, and AAA', 'AAA, BBB, and CCC'), ('CCC, BBB, and AAA', 'CCC, BBB, and BBB'),
    ('CCC, BBB, and AAA', 'CCC, BBB, and OTHER'), ('(AAA)', '(BBB)'),
    ('tetrafluorinated BASEs', 'trifluorinated BASEs'), ('monofluorinated, tri', 'difluorinated, tri'),
    ('2,2,2-trifluoroethoxy', '2,2-trifluoroethoxy'), ('2,2,2-trifluoroethoxy', '2,2,2,2-tetrafluoroethoxy'),
    ('2,2,2-trifluoroethoxy', '1,1,1-trifluoroethoxy'),
    ('fluoroethoxy', 'fluoromethoxy'), ('dialkyl ethers:', 'dialkyl esters:'),
    ('three fluorinated', 'two fluorinated'), ('1,2-diethoxyethane', '1,2-dimethoxyethane'),
    ('(BASE,', '(OTHER,'), ('tetrafluorinated BASEs', 'tetrafluorinated OTHERs'),
    ('correspond to', 'may correspond to'),
])
def test_wrong_identity_degree_locant_class_count_or_base_refuses(old, new):
    assert not bundle(RAW.replace(old, new)).eligible


def test_duplicate_full_name_cannot_be_presented_as_three_distinct_ethers():
    assert not bundle(RAW.replace(FOUR, THREE)).eligible


def test_swapping_equivalent_ethane_ends_cannot_create_a_second_identity():
    raw = RAW.replace(THREE, '1-(2,2,2-trifluoroethoxy)-2-(2-fluoroethoxy)ethane')
    raw = raw.replace('trifluorinated,', 'tetrafluorinated,')
    assert not bundle(raw).eligible


@pytest.mark.parametrize('prefix', ['In previous work, ', 'Previously reported ', 'We hypothesize: ',
                                  'Not observed: ', 'References\n'])
def test_noncurrent_or_bibliographic_enumeration_cannot_supply_identities(prefix):
    assert not bundle(RAW.replace('In the present paper', prefix + 'In the present paper')).eligible


@pytest.mark.parametrize('suffix', [' при 25 °C', ' и вязкость', ' и синтез', ' без ограничений',
                                  ' с AAA', ' для всех эфиров'])
def test_query_constraints_and_named_subsets_are_not_ignored(suffix):
    result = bundle(question=QUESTION[:-1] + suffix + '?')
    assert result is None or not result.eligible


def test_reference_base_count_and_complete_source_scope_are_required():
    assert not bundle(question=QUESTION.replace('BASE', 'OTHER')).eligible
    assert not bundle(question=QUESTION.replace('три', 'два')).eligible
    assert not prepare(QUESTION, [source(RAW, article_id='other')], REF).eligible
    assert not prepare(QUESTION, [source(RAW)], {**REF, 'year': '2023'}).eligible


def test_aliases_base_and_supported_degree_are_not_hardcoded_to_exposed_names():
    changed = RAW.replace('AAA', 'NEW').replace('BBB', 'ALT').replace('CCC', 'LAST').replace('BASE', 'REFBASE')
    assert bundle(changed, QUESTION.replace('BASE', 'REFBASE')).eligible
    changed = RAW.replace(ONE, '1-ethoxy-2-(2,2-difluoroethoxy)ethane').replace('monofluorinated,', 'difluorinated,')
    assert bundle(changed).eligible


def test_name_line_wrap_ligatures_and_hyphens_keep_exact_raw_quotes():
    raw = RAW.replace('fluoro', 'ﬂuoro').replace(')-2-', ')-\n2-').replace('trifluorinated', 'tri-\nfluorinated')
    result = bundle(raw)
    assert result.eligible
    for fact in result.records[0]['facts']:
        assert '\n' not in fact['value']['text'] and ' ' not in fact['value']['text']
        assert fact['value']['normalization'].endswith('chemical_name_whitespace_compaction')
        a = fact['value']['source']
        assert raw[a['start']:a['end']] == a['text']


@pytest.mark.parametrize('field', ['name', 'degree', 'base', 'alias', 'normalization', 'text', 'raw'])
def test_record_identity_conditions_and_rendering_are_recomputed(field):
    result = bundle()
    payload = json.loads(result.evidence[0].text)
    r = payload['records'][0]
    if field == 'name':
        r['facts'][0]['value']['text'] = ONE
    elif field in ('degree', 'base'):
        r['facts'][0]['conditions'][field]['text'] = 'unbound'
    elif field == 'alias':
        r['facts'][0]['sample']['text'] = 'OTHER'
    elif field == 'normalization':
        r['facts'][0]['value']['normalization'] = 'unrecorded_repair'
    elif field == 'text':
        r['allowed_claim'] = 'Wrong chemical identity'
    else:
        payload['raw_source'] = RAW.replace('monofluorinated,', 'difluorinated,')
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0], text=json.dumps(payload))])


def test_exposed_source_three_chemical_identities_recompute_from_exact_raw():
    j = json.loads(FIXTURE.read_bytes())
    items = [Evidence(**e) for e in j['trace']['evidence']]
    before = deepcopy(items)
    result = prepare(j['api']['question'], items, j['trace']['retrieval']['metadata']['explicit_source_reference'])
    assert result.eligible and items == before
    record = answer_facts.selection_records(result.evidence)['F1']
    assert [(f['sample']['text'], f['conditions']['degree']['text']) for f in record['facts']] == [
        ('FETFEE', 'tetrafluorinated'), ('ETFEE', 'trifluorinated'), ('EFEE', 'monofluorinated')]
    raw = result.display[0]
    answer_facts.verify_raw_binding(result.evidence[0].text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
        citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end, source_type=raw.source_type)


@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('prose', 502)])
def test_actual_api_synthetic_complete_selection_abstention_and_unbound_prose(monkeypatch, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult
    from scripts.gigachat_answer_smoke import configure

    j = json.loads(FIXTURE.read_bytes())
    data = j['trace']['retrieval']
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
            content = {'answerable': mode != 'abstain', 'claims': [] if mode == 'abstain' else [
                {'text': 'F1' if mode == 'select' else 'unbound prose', 'citation_ids': ['E1']}]}
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
            response = client.post('/answer/experimental/required-fields', json=j['api'])
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == status and calls == ['synthetic_oauth', 'synthetic_model']
    assert 'READ ONLY' in transactions[0] and transactions[-1] == 'rollback'
    if mode == 'select':
        body = response.json()
        assert body['answer']['status'] == 'answered' and body['delivery_status'] == 'not_evaluated'
        assert 'тетрафторированный' in routes.render(body) and FOUR in routes.render(body)
