"""Finite ranking/context/approximation controls; exposed development sources only."""
import json
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.generation import answer_facts, quantitative_facts
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.generation.quantitative_facts import prepare
from app.retrieval.search import SearchResult
from app.retrieval.source_reference import rank_context
from tests.unit.test_quantitative_facts import PREFIX, REF, source

QUESTION = PREFIX + ('Какой электролит показал наилучшие результаты в NEG/Na-полуячейке '
                     'и какова его начальная кулоновская эффективность?')
RAW = ('The NEG/Na half cell was studied. The ABC exhibits highest initial CE (~92.7%) '
       'and best cycle performance among several cases, suggesting a possible interface effect.')
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/peng_best_ce_source_v01.json'


def bundle(raw=RAW, question=QUESTION):
    return prepare(question, [source(raw)], REF, answer_language='ru')


def retrieval():
    j = json.loads(FIXTURE.read_bytes())
    rows, role_metadata = rank_context(j['api']['question'], [SearchResult(**r) for r in j['pool']], top_k=5)
    current = deepcopy(j['baseline_trace']['retrieval'])
    current['results'] = [asdict(r) for r in rows]
    current['metadata']['explicit_source_reference'].update(role_metadata)
    return j, current


def test_complete_claim_is_limited_to_reported_cell_comparison_and_preserves_approximation():
    result = bundle()
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert len(record['facts']) == 2
    assert record['facts'][0]['sample']['text'] == 'ABC'
    assert record['facts'][0]['value']['text'] == '92.7'
    assert record['facts'][0]['unit']['text'] == '%'
    for fact in record['facts']:
        assert not fact['scientific_ownership_verified']
        assert fact['conditions']['cell']['text'] == 'NEG/Na'
        assert fact['conditions']['comparison']['text'] == 'among several cases'
        for value in (fact['sample'], fact['value'], fact['unit'], *fact['conditions'].values()):
            if value:
                a = value['source']
                assert RAW[a['start']:a['end']] == a['text']
    assert record['facts'][0]['conditions']['approximation']['text'] == '~'
    assert 'approximation' not in record['facts'][1]['conditions']
    assert 'ce_rank' not in record['facts'][1]['conditions']
    claim = answer_facts.resolve_selections([GeneratedClaim('F1', ['E1'])], result.evidence)[0].text
    assert 'приблизительно 92.7%' in claim and 'среди рассмотренных вариантов' in claim
    assert 'interface' not in claim and 'SEI' not in claim


@pytest.mark.parametrize('old,new', [
    ('NEG/Na', 'POS/Na'), ('half cell', 'full cell'),
    ('was studied.', 'was studied. A POS/Na cell was tested.'),
    ('was studied.', 'was studied. We hypothesize: '),
    ('highest initial CE', 'higher initial CE'), ('highest initial CE', 'highest average CE'),
    ('best cycle performance', 'adequate cycle performance'), ('among several cases', 'in previous work'),
    ('92.7%', '101%'), ('92.7%', '92.7 mAh'), ('~92.7', '\x0392.7'),
    ('The ABC exhibits', 'Not observed: the ABC exhibits'), ('The NEG', 'In previous work, the NEG'),
    ('The ABC exhibits', 'Previously reported The ABC exhibits'),
])
def test_wrong_cell_status_ranking_comparison_unit_or_unknown_glyph_refuses(old, new):
    assert not bundle(RAW.replace(old, new)).eligible


@pytest.mark.parametrize('suffix', [' при 25 °C', ' для всех электролитов', ' и механизм',
                                  ' в полной ячейке', ' с XYZ', ' без ограничений'])
def test_query_constraints_are_not_discarded(suffix):
    assert not bundle(question=QUESTION[:-1] + suffix + '?').eligible


def test_generic_labels_values_and_exact_values_are_not_hardcoded():
    result = bundle(RAW.replace('ABC', 'ALT').replace('~92.7', '88.4'))
    assert result.eligible and 'ALT' in result.records[0]['allowed_claim']
    assert '88.4%' in result.records[0]['allowed_claim'] and 'приблизительно' not in result.records[0]['allowed_claim']
    assert bundle(RAW.replace('NEG/Na', 'ANODE/K'), QUESTION.replace('NEG/Na', 'ANODE/K')).eligible


def test_conflicting_complete_comparisons_and_foreign_article_refuse():
    conflict = source(RAW.replace('ABC', 'ALT'), citation_id='E2', chunk_id='other')
    assert not prepare(QUESTION, [source(RAW), conflict], REF).eligible
    assert not prepare(QUESTION, [source(RAW, article_id='other')], REF).eligible
    assert not bundle('References\n' + RAW).eligible


def test_actual_full_article_pool_retains_requested_anode_context_inside_original_top5_limit():
    j, current = retrieval()
    assert len(current['results']) == 5
    assert current['results'] != j['baseline_trace']['retrieval']['results']
    reserved = current['results'][0]
    assert reserved in j['pool'] and 'highest initial CE' in reserved['full_text']
    assert current['metadata']['explicit_source_reference']['requested_roles'] == ['half_cell_best_initial_ce:mcmb/li']
    sources = [Evidence('E' + str(i + 1), r['article_id'], r['chunk_id'], r['title'], r['doi'], r['page_start'],
        r['page_end'], r['source_type'], r['full_text'], r['score'], r['retrieval_method'], r['method_scores'], r['method_ranks'])
        for i, r in enumerate(current['results'])]
    result = prepare(j['api']['question'], sources, current['metadata']['explicit_source_reference'])
    assert result.eligible
    record = answer_facts.selection_records(result.evidence)['F1']
    assert 'приблизительно 95.3%' in record['allowed_claim']
    assert record['facts'][0]['conditions']['approximation']['source']['text'] == '\x03'
    assert record['source_grammar']['glyph_decoding']['catalogue_sha256'] == quantitative_facts.BEST_CE_GLYPHS[1]


def test_ranking_cannot_retain_cathode_only_context_for_requested_anode():
    candidates = [SearchResult('work', 'a', None, None, 1, 1, 'main_text', RAW.replace('NEG/Na', 'POS/Na'),
        0.0, 'synthetic', full_text=RAW.replace('NEG/Na', 'POS/Na'))]
    rows, metadata = rank_context(QUESTION, candidates, top_k=1)
    assert rows == candidates and metadata['missing_roles'] == ['half_cell_best_initial_ce:neg/na']


@pytest.mark.parametrize('field,value', [('chunk_id', 'copy'), ('article_id', 'other'), ('page_end', 9),
                                      ('source_type', 'main_text'), ('text', None)])
def test_newly_selected_raw_identity_is_required_for_reviewed_approximation(field, value):
    j, current = retrieval()
    r = current['results'][0]
    raw = Evidence('E1', r['article_id'], r['chunk_id'], r['title'], r['doi'], r['page_start'], r['page_end'],
                   r['source_type'], r['full_text'], r['score'], r['retrieval_method'], r['method_scores'], r['method_ranks'])
    if field == 'text':
        value = raw.text + ' '
    assert not prepare(j['api']['question'], [replace(raw, **{field: value})],
                       current['metadata']['explicit_source_reference']).eligible


@pytest.mark.parametrize('mode', ['missing', 'changed'])
def test_new_approximation_catalogue_failure_is_explicit(monkeypatch, tmp_path, mode):
    path = tmp_path / 'resource.json'
    if mode == 'changed':
        path.write_text('{}')
    monkeypatch.setattr(quantitative_facts, 'BEST_CE_GLYPHS', (path, quantitative_facts.BEST_CE_GLYPHS[1]))
    result = bundle()
    assert not result.eligible and any(d['reason'].startswith('reviewed_glyph_catalogue_') for d in result.diagnostics)


@pytest.mark.parametrize('field', ['ce', 'cell', 'approximation', 'comparison', 'text', 'glyph'])
def test_record_scope_approximation_and_glyph_drift_rejected(field):
    result = bundle()
    payload = json.loads(result.evidence[0].text)
    record = payload['records'][0]
    if field == 'ce':
        record['facts'][0]['value']['text'] = '99.99'
    elif field in ('cell', 'approximation', 'comparison'):
        record['facts'][0]['conditions'][field]['text'] = 'unbound'
    elif field == 'text':
        record['allowed_claim'] = 'Universal best electrolyte'
    else:
        record['source_grammar']['glyph_decoding'] = {'operations': []}
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(result.evidence[0], text=json.dumps(payload))])


@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('prose', 502)])
def test_actual_api_synthetic_transport_includes_new_ranked_raw_context(monkeypatch, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse
    from scripts.gigachat_answer_smoke import configure

    j, current = retrieval()
    raw = SearchResponse(**{**current, 'results': [SearchResult(**r) for r in current['results']]})
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
        assert 'приблизительно 95.3%' in routes.render(body)
