"""Electrode direction, assumption and reference-zero controls; not independent science."""
import json
import re
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.generation import answer_facts
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from app.retrieval.source_reference import rank_context
from tests.unit.test_quantitative_facts import PREFIX, REF, source

QUESTION = PREFIX + 'Как экспериментально оценивали μNa⁺ и относительно какого состава задавали его нулевое значение?'
PREP = ('The NaABC salt was dissolved in electrolyte solvents to prepare electrolyte solutions in an Ar-filled glove box. '
        'The electrolyte containing 2 mmol dm−3 (mm) RC (Lab) was also prepared for measuring ENa with reference to RC/RC+. ')
METHOD = ('Evaluation of μNa+: To quantify μNa+ in an electrolyte, ENa was measured with reference to the redox potential '
          'of RC/RC+. The electrochemical cell used in this experiment was composed of three electrodes '
          '(Figure S7g, Supporting Information): a Au plate working electrode (Lab) and Na metal reference and counter '
          'electrodes (Lab) with electrolytes containing 2 mm RC. Cyclic voltammetry was conducted using a Device 123 '
          '(Lab) to measure the redox potential of RC/RC+ with reference to Na reference electrode, from the midpoint '
          'of the oxidation/reduction peaks. Here, supposing that the redox potential of RC/RC+ was constant,[8] ENa '
          'was defined as Na electrode potential with reference to the RC/RC+ redox potential. As shown in Note S3 '
          '(Supporting Information), μNa+ in an electrolyte can be derived from the ENa evaluated in the same '
          'electrolyte. μNa+ = FENa + constant (4) Here, μNa+ was defined to be zero in a standard electrolyte, '
          'NaABC/SOLV (2/7 by mol), and μNa+ in various electrolytes was obtained as relative values with reference '
          'to that in NaABC/SOLV (2/7 by mol).')
RAW = PREP + METHOD + ' Charge–Discharge Measurements: Cycling was conducted at 25 °C.'
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/kondo_potential_method_source_v01.json'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def retrieval():
    saved = json.loads(FIXTURE.read_bytes())
    rows, roles = rank_context(saved['api']['question'], [SearchResult(**r) for r in saved['pool']], top_k=5)
    current = deepcopy(saved['baseline_trace']['retrieval'])
    current['results'] = [asdict(r) for r in rows]
    current['metadata']['explicit_source_reference'].update(roles)
    return saved, current


def test_method_and_inverse_reference_definition_keep_distinct_directions_and_assumption():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 5
    observation, dose, definition, equation, zero = record['facts']
    assert observation['value']['text'] == 'redox potential of RC/RC+ with reference to Na reference electrode'
    assert observation['method']['text'] == 'Cyclic voltammetry'
    assert dose['value']['text'] == '2' and dose['unit']['text'] == 'mmol dm−3'
    assert definition['sample']['text'] == 'ENa'
    assert definition['value']['text'] == 'Na electrode potential with reference to the RC/RC+ redox potential'
    assert 'supposing' in definition['conditions']['assumption']['text']
    assert equation['value']['text'] == 'μNa+ = FENa + constant'
    assert zero['operation'] == 'chosen_relative_zero_convention' and zero['value']['text'] == 'zero'
    assert zero['conditions']['basis']['text'] == 'NaABC/SOLV' and zero['conditions']['ratio']['text'] == '2/7'
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        for value in (fact['sample'], fact['value'], fact['unit'], fact['method'], *fact['conditions'].values()):
            if value:
                anchor = value['source']
                assert RAW[anchor['start']:anchor['end']] == anchor['text']
    text = answer_facts.resolve_selections([GeneratedClaim('F1', ['E1'])], result.evidence)[0].text
    assert 'Предполагая постоянство' in text and 'Относительный ноль' in text and '2/7 по молям' in text
    assert '25' not in text and 'Температура CV' in text


@pytest.mark.parametrize('old,new', [
    ('μNa+ = FENa', 'μLi+ = FENa'), ('To quantify μNa+', 'To quantify μLi+'),
    ('FENa', 'FELi'), ('μNa+ = FENa', 'μNa+ = -FENa'), ('FENa + constant', 'FENa - constant'),
    ('Na metal reference', 'Li metal reference'), ('to Na reference electrode', 'to Li reference electrode'),
    ('defined as Na electrode', 'defined as Li electrode'), ('redox potential of RC/RC+', 'redox potential of RC/OTHER+'),
    ('with reference to the RC/RC+ redox', 'with reference to the XX/XX+ redox'),
    ('supposing that', 'having proven that'), ('was constant,[8]', 'varied,[8]'),
    ('midpoint of the oxidation/reduction peaks', 'oxidation peak'),
    ('evaluated in the same electrolyte', 'evaluated in another electrolyte'),
    ('zero in a standard', 'zero in every'), ('NaABC/SOLV (2/7 by mol),', 'NaABC/OTHER (2/7 by mol),'),
    ('that in NaABC/SOLV', 'that in LiABC/SOLV'), ('(2/7 by mol).', '(1/7 by mol).'),
    ('relative values', 'absolute values'), ('mmol dm−3', 'mol dm−3'),
    ('containing 2 mm RC', 'containing 3 mm RC'), ('(mm) RC', '(mm) OTHER'),
    ('The NaABC salt', 'The LiABC salt'), ('(2/7 by mol)', '(0/7 by mol)'),
])
def test_inconsistent_ion_reference_direction_formula_dose_or_zero_basis_refuses(old, new):
    assert not bundle(RAW.replace(old, new)).eligible


@pytest.mark.parametrize('prefix', ['In previous work, ', 'Previously reported ', 'We hypothesize: ',
                                  'Not observed: ', 'References\n'])
def test_noncurrent_scope_cannot_supply_measurement_or_zero(prefix):
    assert not bundle(PREP + prefix + METHOD).eligible
    assert not bundle(prefix + RAW).eligible


@pytest.mark.parametrize('suffix', [' при 25 °C', ' и механизм', ' для всех солей', ' без ограничений',
                                  ' в LiABC/SOLV', ' с численным значением μNa⁺'])
def test_extra_query_requirements_cannot_be_discarded(suffix):
    result = bundle(question=QUESTION[:-1] + suffix + '?')
    assert result is None or not result.eligible


def test_query_ion_metadata_and_source_scope_are_required():
    assert not bundle(question=QUESTION.replace('μNa⁺', 'μLi⁺')).eligible
    assert not bundle(question=QUESTION.replace('μNa⁺', '')).eligible
    assert not prepare(QUESTION, [source(RAW, article_id='other')], REF).eligible
    assert not prepare(QUESTION, [source(RAW)], {**REF, 'year': '2023'}).eligible


def test_consistent_other_metal_pair_basis_and_ratio_are_not_hardcoded():
    raw = RAW.replace('Na', 'K').replace('RC', 'OX').replace('NaABC', 'KABC').replace('2/7', '3/11')
    result = bundle(raw, QUESTION.replace('Na', 'K'))
    assert result.eligible and 'KABC/SOLV' in result.records[0]['allowed_claim']
    assert '3/11 по молям' in result.records[0]['allowed_claim']


def test_ambiguous_preparation_cannot_select_the_one_matching_method_dose():
    extra = PREP.replace('containing 2 mmol', 'containing 5 mmol')
    assert not bundle(extra + RAW).eligible


def test_molar_shorthand_cannot_replace_millimolar_in_both_source_mentions():
    raw = RAW.replace('(mm)', '(M)').replace('2 mm RC', '2 M RC')
    assert not bundle(raw).eligible


def test_complete_article_pool_retention_uses_original_top5_limit_and_raw_objects():
    saved, current = retrieval()
    assert len(current['results']) == 5 and all(row in saved['pool'] for row in current['results'])
    assert 'Cyclic voltammetry' in current['results'][0]['full_text']
    assert current['results'] != saved['baseline_trace']['retrieval']['results']
    evidence = [Evidence('E' + str(i + 1), r['article_id'], r['chunk_id'], r['title'], r['doi'], r['page_start'],
        r['page_end'], r['source_type'], r['full_text'], r['score'], r['retrieval_method'], r['method_scores'], r['method_ranks'])
        for i, r in enumerate(current['results'])]
    result = prepare(saved['api']['question'], evidence, current['metadata']['explicit_source_reference'])
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert record['facts'][-1]['conditions']['basis']['text'] == 'LiFSI/DME'
    assert record['facts'][-1]['conditions']['ratio']['text'] == '1/10'
    raw = result.display[0]
    answer_facts.verify_raw_binding(result.evidence[0].text, raw.text, article_id=raw.article_id, chunk_id=raw.chunk_id,
        citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end, source_type=raw.source_type)


@pytest.mark.parametrize('field', ['reference', 'assumption', 'zero', 'ratio', 'equation', 'raw'])
def test_record_reference_assumption_formula_and_relative_zero_recompute(field):
    result = bundle()
    payload = json.loads(result.evidence[0].text)
    record = payload['records'][0]
    if field == 'reference':
        record['facts'][0]['value']['text'] = 'opposite reference direction'
    elif field == 'assumption':
        record['facts'][2]['conditions']['assumption']['text'] = 'proven constant'
    elif field == 'zero':
        record['facts'][-1]['operation'] = 'absolute_zero'
    elif field == 'ratio':
        record['facts'][-1]['conditions']['ratio']['text'] = '1/10'
    elif field == 'equation':
        record['facts'][3]['value']['text'] = 'μNa+ = -FENa'
    else:
        payload['raw_source'] = RAW.replace('relative values', 'absolute values')
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
        assert 'Предполагая постоянство' in routes.render(body) and 'Относительный ноль' in routes.render(body)
