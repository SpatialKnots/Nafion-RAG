"""Exact-source glyph data repair controls; exposed sources, not hidden evaluation."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.generation import answer_facts, quantitative_facts, reviewed_glyphs
from app.generation.fact_types import FactPatternError
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.ui import _prepared_statement_text
from scripts import gigachat_answer_smoke as f

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/reviewed_glyph_sources_v01.json'


def case(cid):
    fixture = json.loads(FIXTURE.read_bytes())['cases'][cid]
    before, api = fixture['trace'], fixture['api']
    return api, [Evidence(**e) for e in before['evidence']], before['retrieval']['metadata']['explicit_source_reference']


@pytest.mark.parametrize('cid', ['Peng_05', 'Peng_08'])
def test_reviewed_source_glyphs_preserve_raw_and_exact_numeric_fields(cid):
    api, evidence, ref = case(cid)
    before = list(evidence)
    bundle = quantitative_facts.prepare(api['question'], evidence, ref)
    assert bundle.eligible and evidence == before
    record = answer_facts.selection_records(bundle.evidence)['F1']
    raw = bundle.display[0]
    proof = record['source_grammar']['glyph_decoding']
    assert proof['original_pdf_sha256'] == json.loads(reviewed_glyphs.CATALOGUE.read_bytes())['pdf_sha256']
    assert proof['catalogue_sha256'] == reviewed_glyphs.CATALOGUE_SHA256
    assert '\x01' in raw.text and 'mA h g−1' in record['allowed_claim']
    for fact in record['facts']:
        for anchor in [fact['support'], *[v['source'] for v in (fact['value'], fact['unit'], fact['sample'],
                                                             *fact['conditions'].values()) if v]]:
            assert raw.text[anchor['start']:anchor['end']] == anchor['text']
            assert f.sha(raw.text.encode()) == anchor['raw_chunk_sha256']
        if fact['unit']:
            assert fact['unit']['normalization'].startswith(reviewed_glyphs.POLICY)
    answer_facts.verify_raw_binding(bundle.evidence[0].text, raw.text, article_id=raw.article_id,
        chunk_id=raw.chunk_id, citation_id=raw.citation_id, page_start=raw.page_start, page_end=raw.page_end,
        source_type=raw.source_type)
    resolved = answer_facts.resolve_selections([GeneratedClaim('F1', [raw.citation_id])], bundle.evidence)
    assert resolved[0].text == record['allowed_claim']
    display = _prepared_statement_text(bundle.evidence[0].text, bundle.evidence[0].source_type)
    assert record['allowed_claim'] in display and 'исходной кодировкой' in display
    assert all(fact['support']['text'] in display for fact in record['facts'])
    if cid == 'Peng_08':
        value = record['facts'][0]['conditions']['capacity_approximation']
        assert value['text'] == '~' and value['source']['text'] == '\x03'
        assert 'приблизительно' in resolved[0].text


@pytest.mark.parametrize('field,value', [('article_id', 'other'), ('chunk_id', 'other'), ('page_start', 1),
                                       ('page_end', 8), ('source_type', 'method'), ('text', 'unreviewed raw text')])
def test_copied_or_changed_source_cannot_use_reviewed_operations(field, value):
    _, evidence, _ = case('Peng_05')
    raw = next(e for e in evidence if reviewed_glyphs.operations(e))
    assert reviewed_glyphs.operations(replace(raw, **{field: value})) == []


@pytest.mark.parametrize('cid', ['Peng_05', 'Peng_08'])
@pytest.mark.parametrize('change', ['number', 'glyph', 'electrolyte', 'owner', 'extra_query_condition'])
def test_source_or_question_change_is_not_repaired_by_a_near_match(cid, change):
    api, evidence, ref = case(cid)
    raw = next(e for e in evidence if reviewed_glyphs.operations(e))
    if change == 'extra_query_condition':
        question = api['question'].rstrip('?') + ' при 17 °C?'
    else:
        question = api['question']
        before, after = {'number': ('234.5', '178.2') if cid == 'Peng_05' else ('205', '178'),
                         'glyph': ('\x01', '\x02'), 'electrolyte': ('FFT', 'ABC'),
                         'owner': ('LCO/Li', 'POS/Na') if cid == 'Peng_05' else ('LCO/MCMB', 'POS/NEG')}[change]
        raw = replace(raw, text=raw.text.replace(before, after))
    assert not quantitative_facts.prepare(question, [raw], ref).eligible


@pytest.mark.parametrize('mode', ['missing', 'corrupt'])
def test_unavailable_or_unverified_catalogue_stops_with_diagnostic(monkeypatch, tmp_path, mode):
    target = tmp_path / 'catalogue.json'
    if mode == 'corrupt':
        target.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(reviewed_glyphs, 'CATALOGUE', target)
    api, evidence, ref = case('Peng_05')
    bundle = quantitative_facts.prepare(api['question'], evidence, ref)
    assert not bundle.eligible and bundle.reason == 'reviewed_pdf_glyph_binding_unresolved'
    assert any(d['reason'].startswith('reviewed_glyph_catalogue_') for d in bundle.diagnostics)
    with pytest.raises(FactPatternError):
        reviewed_glyphs.operations(evidence[0])


@pytest.mark.parametrize('mode', ['offset', 'decoded', 'font', 'pdf', 'normalization', 'approximation'])
def test_glyph_proof_or_rendered_value_mutation_is_rejected(mode):
    api, evidence, ref = case('Peng_08')
    bundle = quantitative_facts.prepare(api['question'], evidence, ref)
    parent = bundle.evidence[0]
    payload = json.loads(parent.text)
    record = payload['records'][0]
    proof = record['source_grammar']['glyph_decoding']
    if mode == 'offset':
        proof['operations'][0]['raw_start'] += 1
    elif mode == 'decoded':
        proof['operations'][0]['decoded'] = '+'
    elif mode == 'font':
        proof['operations'][0]['font_program_sha256'] = '0' * 64
    elif mode == 'pdf':
        proof['original_pdf_sha256'] = '0' * 64
    elif mode == 'normalization':
        record['facts'][0]['unit']['normalization'] = 'inferred'
    else:
        record['facts'][0]['conditions']['capacity_approximation']['text'] = 'exact'
    with pytest.raises(GenerationOutputError):
        answer_facts.selection_records([replace(parent, text=json.dumps(payload))])


def test_packaged_resource_is_declared():
    import tomllib

    config = tomllib.loads((f.ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    assert 'resources/reviewed_pdf_glyph_aliases_v01.json' in config['tool']['setuptools']['package-data']['app']


@pytest.mark.parametrize('cid', ['Peng_05', 'Peng_08'])
@pytest.mark.parametrize('mode,status', [('select', 200), ('abstain', 200), ('free_prose', 502)])
def test_actual_api_glyph_contract_select_abstain_and_prose_boundary(monkeypatch, cid, mode, status):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult
    from scripts.gigachat_answer_smoke import configure

    settings, calls, transactions = configure(), [], []
    api, evidence, ref = case(cid)
    citation = quantitative_facts.prepare(api['question'], evidence, ref).evidence[0].citation_id
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
                {'text': 'F1' if mode == 'select' else 'The answer is 999.', 'citation_ids': [citation]}]}
            return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
                                            'content': json.dumps(content)}}]}).encode()
        provider._post = post
        return provider
    raw = json.loads(FIXTURE.read_bytes())['cases'][cid]['trace']['retrieval']
    retrieval = SearchResponse(**{**raw, 'results': [SearchResult(**r) for r in raw['results']]})
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
    assert response.status_code == status
    assert calls == ['synthetic_oauth', 'synthetic_model']
    assert 'READ ONLY' in transactions[0] and transactions[-1] == 'rollback'
    if mode == 'select':
        body = response.json()
        assert body['answer']['status'] == 'answered' and body['delivery_status'] == 'not_evaluated'
        assert 'mA h g−1' in body['answer']['claims'][0]['text']
        assert 'исходной кодировкой' in routes.render(body)
    elif mode == 'abstain':
        assert response.json()['answer']['status'] == 'insufficient_evidence'
