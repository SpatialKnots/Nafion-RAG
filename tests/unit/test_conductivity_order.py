"""Constructed ordering/scope controls and exposed source replay, not scientific acceptance."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts, conductivity_order
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.quantitative_facts import prepare
from tests.unit.test_quantitative_facts import PREFIX, REF, source

QUESTION = PREFIX + 'Каков порядок ионной проводимости 0.75 M растворов NaABC в исследованных фторированных эфирах?'
RAW = ('Figure 8(a) shows the temperature (T) dependence of conductivities (κ) of electrolyte solutions in '
       'AAA, BBB, and CCC. We used NaABC (0.75 mol dm−3 at 20°C) as the electrolyte. '
       'The solubility of NaABC in DDD was much less than 0.75 mol dm−3. '
       'The conductivities increased with an increase in temperature. The viscosities of the fluorinated DEEs '
       'decreased rapidly with an increase in temperature and approached that of DDD at high temperatures, '
       'as shown in Fig. 7(a). Interestingly, the conductivity of NaABC solution in BBB was higher than '
       'that in CCC: AAA > BBB > CCC.')
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/nambu_order_source_v01.json'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def exposed():
    saved = json.loads(FIXTURE.read_bytes())
    return saved['api'], [Evidence(**e) for e in saved['trace']['evidence']], saved['trace']['retrieval']['metadata'][
        'explicit_source_reference']


def test_strict_order_salt_concentration_and_temperature_scope_recompute():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    fact = record['facts'][0]
    assert fact['sample']['text'] == 'NaABC' and fact['value']['text'] == 'AAA > BBB > CCC'
    assert fact['conditions']['concentration']['text'] == '0.75'
    assert fact['conditions']['concentration_unit']['text'] == 'mol dm−3'
    assert fact['conditions']['concentration_reference_temperature']['text'] == '20'
    assert 'measurement_temperature_range' in fact['unknown_fields'] and fact['unit'] is None
    assert not fact['scientific_ownership_verified']
    for value in (fact['sample'], fact['value'], *fact['conditions'].values()):
        anchor = value['source']
        assert RAW[anchor['start']:anchor['end']] == anchor['text']
    claim = answer_facts.resolve_selections([GeneratedClaim('F1', ['E1'])], result.evidence)[0].text
    assert 'AAA > BBB > CCC' in claim and 'Концентрация указана при 20°C' in claim
    assert 'температурным зависимостям' in claim and 'Абсолютные значения' in claim
    assert record['source_grammar']['concentration_unit_alias'] == 'M_equals_mol_dm_minus3_same_numeric_value'


@pytest.mark.parametrize('old,new', [
    ('We used NaABC', 'We used LiXYZ'), ('solubility of NaABC', 'solubility of LiXYZ'),
    ('conductivity of NaABC solution', 'conductivity of LiXYZ solution'),
    ('0.75 mol', '0.70 mol'), ('mol dm−3', 'mol dm3'), ('mol dm−3', 'mol dm¹3'), ('mol dm−3', 'mol kg−1'),
    ('AAA > BBB > CCC', 'AAA > BBB > AAA'), ('AAA > BBB > CCC', 'BBB > AAA > DDD'),
    ('AAA > BBB > CCC', 'AAA > CCC > BBB'), ('AAA > BBB > CCC', 'AAA < BBB < CCC'),
    ('AAA > BBB > CCC', 'AAA ≈ BBB > CCC'), ('in BBB was higher', 'in CCC was higher'),
    ('and CCC. We', 'and DDD. We'), ('in DDD was much', 'in AAA was much'),
    ('of DDD at high', 'of OTHER at high'), ('fluorinated DEEs', 'carbonates'),
    ('dependence of conductivities', 'dependence of viscosities'),
    ('as the electrolyte.', 'as the electrolyte. In another experiment, '),
    ('Interestingly, the conductivity', 'Previously, the conductivity'),
    ('Figure 8(a)', 'Previously reported Figure 8(a)'),
])
def test_wrong_quantity_salt_concentration_units_owner_or_order_refuses(old, new):
    assert not bundle(RAW.replace(old, new)).eligible


@pytest.mark.parametrize('suffix', [' при 25 °C', ' в EC смеси', ' и механизм', ' для всех солей',
                                  ' без ограничений', ' и абсолютные значения', ' по вязкости'])
def test_unknown_or_extra_query_requirements_are_not_masked(suffix):
    assert not bundle(question=QUESTION[:-1] + suffix + '?').eligible


def test_query_units_concentration_formula_and_extra_named_solvent_are_required():
    for question in (QUESTION.replace('NaABC', 'LiXYZ'), QUESTION.replace('0.75', '1'),
                     QUESTION.replace(' M ', ' m '), QUESTION.replace(' M ', ' mM '),
                     QUESTION.replace('0.75', '0'), QUESTION[:-1] + ' в AAA?'):
        assert not bundle(question=question).eligible
    assert bundle(RAW.replace('0.75', '2.5').replace('NaABC', 'LiXYZ'),
                  QUESTION.replace('0.75', '2.5').replace('NaABC', 'LiXYZ')).eligible


def test_consistent_alternative_order_and_symbols_are_not_hardcoded():
    changed = RAW.replace('AAA > BBB > CCC', 'CCC > BBB > AAA').replace('that in CCC:', 'that in AAA:')
    assert bundle(changed).eligible
    assert 'CCC > BBB > AAA' in bundle(changed).records[0]['allowed_claim']
    assert bundle(RAW.replace('mol dm−3', 'mol dm-3')).eligible


def test_noncurrent_reference_and_cross_article_cannot_upgrade_order():
    for prefix in ('References\n', 'In previous work, ', 'We hypothesize: ', 'Not observed: '):
        assert not bundle(prefix + RAW).eligible
    assert not prepare(QUESTION, [source(RAW), source(RAW, article_id='other')], REF).eligible


def test_conflicting_complete_orders_refuse():
    other = RAW.replace('AAA > BBB > CCC', 'CCC > BBB > AAA').replace('that in CCC:', 'that in AAA:')
    result = prepare(QUESTION, [source(RAW), source(other, citation_id='E2', chunk_id='other')], REF)
    assert not result.eligible and result.reason == 'conflicting_quantitative_values_or_conditions'


def test_exposed_source_uses_separate_reviewed_resource_and_exact_raw_unit():
    api, evidence, ref = exposed()
    before = deepcopy(evidence)
    result = prepare(api['question'], evidence, ref)
    assert result.eligible and evidence == before
    record = answer_facts.selection_records(result.evidence)['F1']
    fact = record['facts'][0]
    unit = fact['conditions']['concentration_unit']
    assert unit['text'] == 'mol dm−3' and unit['source']['text'] == 'mol dm¹3'
    assert unit['normalization'].startswith('reviewed_pdf_glyph_aliases_')
    assert fact['value']['text'] == 'EFEE > FETFEE > ETFEE'
    assert record['source_grammar']['glyph_decoding']['catalogue_sha256'] == conductivity_order.GLYPH_CATALOGUE[1]
    assert len(record['source_grammar']['glyph_decoding']['operations']) == 2


@pytest.mark.parametrize('field,value', [('article_id', 'other'), ('chunk_id', 'copy'), ('page_start', 1),
                                      ('page_end', 3), ('source_type', 'main_text'), ('text', None)])
def test_changed_or_copied_raw_parent_cannot_borrow_reviewed_unit(field, value):
    api, evidence, ref = exposed()
    raw = next(e for e in evidence if e.page_start == e.page_end == 2)
    if field == 'text':
        value = raw.text + ' '
    result = prepare(api['question'], [replace(raw, **{field: value})], ref)
    assert not result.eligible


@pytest.mark.parametrize('mode', ['missing', 'changed'])
def test_unavailable_or_changed_new_catalogue_refuses(monkeypatch, tmp_path, mode):
    from tests.unit.test_resistance_table import bundle as table_bundle

    target = tmp_path / 'catalogue.json'
    if mode == 'changed':
        target.write_text('{}')
    monkeypatch.setattr(conductivity_order, 'GLYPH_CATALOGUE', (target, conductivity_order.GLYPH_CATALOGUE[1]))
    assert not bundle().eligible
    assert table_bundle().eligible  # A failure of the new resource cannot disable the old default catalogue.


@pytest.mark.parametrize('field', ['order', 'salt', 'temperature', 'unit', 'alias', 'glyph', 'raw'])
def test_record_and_provenance_recompute_before_selection(field):
    api, evidence, ref = exposed()
    result = prepare(api['question'], evidence, ref)
    payload = json.loads(result.evidence[0].text)
    record = payload['records'][0]
    if field == 'order':
        record['facts'][0]['value']['text'] = 'Invented order'
    elif field == 'salt':
        record['facts'][0]['sample']['text'] = 'LiXYZ'
    elif field in ('temperature', 'unit'):
        key = 'concentration_reference_temperature' if field == 'temperature' else 'concentration_unit'
        record['facts'][0]['conditions'][key]['text'] = 'unbound'
    elif field == 'alias':
        record['source_grammar']['concentration_unit_alias'] = 'unbound'
    elif field == 'glyph':
        record['source_grammar']['glyph_decoding']['operations'][0]['decoded'] = '+'
    else:
        payload['raw_source'] += ' '
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0], text=json.dumps(payload))])


@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('prose', 502)])
def test_actual_experimental_api_with_synthetic_transport(monkeypatch, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult
    from scripts.gigachat_answer_smoke import configure

    saved = json.loads(FIXTURE.read_bytes())
    api, raw = saved['api'], saved['trace']['retrieval']
    retrieval = SearchResponse(**{**raw, 'results': [SearchResult(**r) for r in raw['results']]})
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
                {'text': 'F1' if mode == 'select' else 'Invented order', 'citation_ids': ['E2']}]}
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
                'role': 'assistant', 'content': json.dumps(content)}}]}).encode()

        provider._post = post
        return provider

    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: deepcopy(retrieval))
    monkeypatch.setattr(routes, 'make_provider', factory)
    app.dependency_overrides[get_session] = dependency
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post('/answer/experimental/required-fields', json=api)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == status and calls == ['synthetic_oauth', 'synthetic_model']
    assert 'READ ONLY' in transactions[0] and transactions[-1] == 'rollback'
    if mode == 'select':
        body = response.json()
        assert body['delivery_status'] == 'not_evaluated' and body['answer']['status'] == 'answered'
        assert 'EFEE > FETFEE > ETFEE' in body['answer']['claims'][0]['text']
        assert 'Концентрация указана при 25°C' in routes.render(body)
    elif mode == 'abstain':
        assert response.json()['answer']['status'] == 'insufficient_evidence'
