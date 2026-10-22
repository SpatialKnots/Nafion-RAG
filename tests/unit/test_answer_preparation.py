"""Constructed integration checks; no paid providers, real corpus writes or scientific labels."""

import copy
import json
from contextlib import nullcontext
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.documents.service import PdfStorageIntegrityError
from app.generation import preparation as service
from app.generation import preparation_routes as routes
from app.generation.service import AnswerResponse
from app.main import app
from app.retrieval.search import SearchResponse
from app.retrieval.vector_index import VectorIndexUnavailableError
from tests.unit.test_generation import _settings
from tests.unit.test_query_evidence_packet import evidence, full_page
from tests.unit.test_record_protocol_association import case


class Session:
    def __init__(self, authors=None, year=2017):
        self.no_autoflush = nullcontext()
        self.commands = []
        self.article = SimpleNamespace(authors=authors, year=year, title='Constructed article', doi=None)

    def execute(self, sql):
        self.commands.append(str(sql))

    def get(self, model, key):
        return self.article


def setup_service(monkeypatch, *, text='Conductivity was measured. Constructed unsupported tail', full=False,
                  baseline=True, authors=None, year=2017, source_variant=None):
    c = case(text)
    e = evidence(c, full_page(c).page_text if full else c['source']['quote'])
    page = full_page(c)
    sources = {'chunks': {e.chunk_id: {'text': e.text}}, 'chunk_layers': {e.chunk_id: page.text_layer},
               'pages': {'page': page.model_dump(mode='json')}, 'diagnostics': []}
    if source_variant == 'missing_registry':
        sources['pages'] = {}
    elif source_variant == 'derived':
        e = replace(e, source_type='table_derived', chunk_id='derived:synthetic')
        sources = {'chunks': {}, 'chunk_layers': {}, 'pages': {},
                   'diagnostics': [{'state': 'derived_source_retained_without_raw_chunk_binding'}]}
    session = Session(authors, year)
    def answer(session_arg, settings, question, **kwargs):
        assert session_arg.commands == ['SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY']
        kwargs['trace_observer'](SearchResponse(question, []), [e],
            {'evidence_adequacy': {'adequate': baseline, 'reason': 'constructed_gate'}, 'options': {
                k: kwargs[k] for k in ['collection', 'top_k', 'method', 'answer_style', 'answer_language', 'library_source_id']}})
        if baseline:
            return kwargs['provider'].generate(question, [e])
        return AnswerResponse(question, 'insufficient_evidence', None, [], [], 'constructed', 'not-called', None, {})
    monkeypatch.setattr(service, 'answer_question', answer)
    monkeypatch.setattr(service, 'collect_sources', lambda *a: copy.deepcopy(sources))
    return session, e, sources


def test_prepare_retains_every_evidence_field_and_source_with_no_request_even_when_checks_pass(monkeypatch):
    session, e, sources = setup_service(monkeypatch)
    payload = service.prepare_answer(session, _settings(), 'Conductivity?', method='exact', top_k=3)
    assert payload['status'] == 'checks_passed' and payload['blocking_reasons'] == []
    assert payload['evidence'] == [asdict(e)] and payload['sources'] == sources
    assert not payload['generation_performed'] and not payload['external_request_constructed'] and not payload['network_ready']
    assert payload['baseline_metadata']['options']['method'] == 'exact'
    assert payload['baseline_metadata']['options']['top_k'] == 3
    assert payload['scientific_admission'] == 'not_evaluated'


@pytest.mark.parametrize('variant,reason', [('full', 'complete_source_pages_retained'),
    ('missing_registry', 'source_registry_unproven'), ('derived', 'source_registry_unproven'),
    ('baseline', 'baseline_insufficient_evidence'), ('qualifier', 'query_qualifier_check_failed'),
    ('budget', 'evidence_bundle_over_budget')])
def test_prepare_fails_closed_without_removing_text(monkeypatch, variant, reason):
    text = 'Conductivity was measured. ' + ('x' * 101000 if variant == 'budget' else 'Constructed tail')
    session, e, _ = setup_service(monkeypatch, text=text, full=variant == 'full', baseline=variant != 'baseline',
                                  source_variant=variant)
    question = 'Conductivity containing hafnium boride?' if variant == 'qualifier' else 'Conductivity?'
    payload = service.prepare_answer(session, _settings(), question)
    assert payload['status'] == 'blocked' and reason in payload['blocking_reasons']
    assert payload['evidence'] == [asdict(e)] and payload['network_ready'] is False
    if variant == 'derived':
        assert payload['source_links'][0]['context_url'] is None


@pytest.mark.parametrize('authors,expected', [([{'name': 'Rivera'}], True), ([{'family': 'Rivera'}], True),
    ([{'last_name': 'Rivera'}], True), ([{'lastName': 'Rivera'}], True), (None, False),
    ([{'given': 'Rivera'}], False), ([{'family': 'Rivera'}, {'other': 'unresolved'}], False)])
def test_author_mapping_preserves_raw_data_and_unknown_incomplete_shapes(monkeypatch, authors, expected):
    session, _, _ = setup_service(monkeypatch, text='DSC was discussed. Constructed tail', authors=authors)
    payload = service.prepare_answer(session, _settings(), 'For Rivera 2017, DSC?')
    meta = next(iter(payload['article_metadata'].values()))
    assert meta['source_authors'] == authors
    assert payload['query_qualifiers']['candidate_allowed'] is expected
    if not expected:
        assert meta['authors'] is None


def test_source_failure_propagates_and_does_not_fall_back_to_generation(monkeypatch):
    session, _, _ = setup_service(monkeypatch)
    monkeypatch.setattr(service, 'collect_sources', Mock(side_effect=PdfStorageIntegrityError('constructed checksum mismatch')))
    with pytest.raises(PdfStorageIntegrityError, match='checksum mismatch'):
        service.prepare_answer(session, _settings(), 'Conductivity?')


def test_actual_answer_pipeline_stops_before_provider_factory(monkeypatch):
    from app.generation import service as generation
    from tests.unit.test_generation import _search_result

    session, e, _ = setup_service(monkeypatch)
    monkeypatch.setattr(service, 'answer_question', generation.answer_question)
    result = replace(_search_result(), article_id=e.article_id, chunk_id=e.chunk_id, page_start=e.page_start,
                     page_end=e.page_end, title=e.title, full_text=e.text, snippet=e.text)
    monkeypatch.setattr(generation, 'search_chunks', lambda *a, **kw: SearchResponse('Conductivity?', [result]))
    forbidden = Mock(side_effect=AssertionError('Generation provider factory must not be called'))
    monkeypatch.setattr(generation, 'build_answer_provider', forbidden)
    payload = service.prepare_answer(session, _settings(), 'Conductivity?')
    assert payload['baseline_allowed'] and not payload['generation_performed']
    forbidden.assert_not_called()


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[get_session] = lambda: object()
    monkeypatch.setattr(routes, 'get_settings', _settings)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


def test_api_calls_preparation_with_validated_options_and_library_scope(client, monkeypatch):
    fake = Mock(return_value={'version': service.VERSION, 'generation_performed': False})
    monkeypatch.setattr(routes, 'prepare_answer', fake)
    library = str(UUID(int=17))
    response = client.post('/answer/prepare', json={'question': 'DSC?', 'method': 'exact', 'top_k': 2,
        'answer_style': 'mini_review', 'answer_language': 'ru', 'library_source_id': library})
    assert response.status_code == 200 and response.json()['generation_performed'] is False
    assert fake.call_args.kwargs['library_source_id'] == UUID(library)
    assert fake.call_args.kwargs['answer_style'] == 'mini_review'


@pytest.mark.parametrize('extra', [{'top_k': 0}, {'method': 'unknown'}, {'answer_style': 'unknown'},
                                {'answer_language': 'unknown'}, {'generate': True}, {'library_source_id': 'bad-id'}])
def test_api_validation_never_calls_preparation(client, monkeypatch, extra):
    fake = Mock(side_effect=AssertionError('Invalid request must not run'))
    monkeypatch.setattr(routes, 'prepare_answer', fake)
    response = client.post('/answer/prepare', json={'question': 'DSC?', **extra})
    assert response.status_code == 422
    fake.assert_not_called()


@pytest.mark.parametrize('error,status', [(ValueError('bad query'), 400),
    (VectorIndexUnavailableError('missing index'), 503), (PdfStorageIntegrityError('checksum mismatch'), 409)])
def test_api_errors_are_visible_with_explicit_status(client, monkeypatch, error, status):
    monkeypatch.setattr(routes, 'prepare_answer', Mock(side_effect=error))
    response = client.post('/answer/prepare', json={'question': 'DSC?'})
    assert response.status_code == status and str(error) in response.json()['detail']


def test_unexpected_error_is_not_hidden_as_a_scientific_refusal(client, monkeypatch):
    monkeypatch.setattr(routes, 'prepare_answer', Mock(side_effect=RuntimeError('constructed DB failure')))
    with pytest.raises(RuntimeError, match='constructed DB failure'):
        client.post('/answer/prepare', json={'question': 'DSC?'})


def test_ui_escapes_source_question_and_metadata_and_preserves_full_text_and_options(client, monkeypatch):
    session, e, _ = setup_service(monkeypatch, text='Conductivity. <script>source attack</script> Constructed tail')
    payload = service.prepare_answer(session, _settings(), 'Conductivity?')
    monkeypatch.setattr(routes, 'prepare_answer', Mock(return_value=payload))
    response = client.post('/ui/answer/prepare', data={'question': '<script>question</script>', 'method': 'exact',
        'collection': 'test-collection', 'top_k': '3'})
    assert response.status_code == 200
    html = response.text
    assert '&lt;script&gt;source attack' in html and '<script>source attack' not in html
    assert '&lt;script&gt;question' in html and '<script>question' not in html
    assert e.text.replace('<', '&lt;').replace('>', '&gt;') in html
    assert 'value="test-collection"' in html and 'value="3"' in html and '<option selected>exact</option>' in html
    assert 'Генерация отключена' in html and 'Полная диагностика' in html
    assert '/articles/' in html and '#page=' in html


@pytest.mark.parametrize('cookie', [str(UUID(int=9)), 'malformed'])
def test_ui_get_inherits_valid_library_cookie_without_search(client, cookie):
    client.cookies.set('ariadne_library_id', cookie)
    response = client.get('/ui/answer/prepare')
    assert response.status_code == 200
    assert 'value="' + (cookie if cookie != 'malformed' else '') + '"' in response.text


def test_ui_explicit_library_scope_wins_over_cookie(client):
    client.cookies.set('ariadne_library_id', str(UUID(int=9)))
    response = client.get('/ui/answer/prepare', params={'library_source_id': str(UUID(int=10))})
    assert 'value="' + str(UUID(int=10)) + '"' in response.text


@pytest.mark.parametrize('value', ['', str(UUID(int=11))])
def test_ui_form_accepts_empty_or_explicit_library_input(client, monkeypatch, value):
    session, _, _ = setup_service(monkeypatch)
    payload = service.prepare_answer(session, _settings(), 'Conductivity?')
    fake = Mock(return_value=payload)
    monkeypatch.setattr(routes, 'prepare_answer', fake)
    response = client.post('/ui/answer/prepare', data={'question': 'Conductivity?', 'library_source_id': value})
    assert response.status_code == 200
    assert fake.call_args.kwargs['library_source_id'] == (UUID(value) if value else None)


def test_ui_source_failure_is_escaped_and_not_rendered_as_pass(client, monkeypatch):
    monkeypatch.setattr(routes, 'prepare_answer', Mock(side_effect=PdfStorageIntegrityError('<script>failure</script>')))
    response = client.post('/ui/answer/prepare', data={'question': 'DSC?', 'method': 'exact'})
    assert response.status_code == 409 and '&lt;script&gt;failure' in response.text
    assert '<script>failure' not in response.text and 'Необходимые проверки пройдены' not in response.text


def test_old_answer_api_contract_and_routing_are_unchanged(client, monkeypatch):
    from app import main
    old = Mock(return_value=object())
    monkeypatch.setattr(main, 'answer_question', old)
    monkeypatch.setattr(main, 'answer_response_to_dict', lambda response: {'status': 'existing-contract'})
    preparation = Mock(side_effect=AssertionError('Old route must not call new preparation'))
    monkeypatch.setattr(routes, 'prepare_answer', preparation)
    assert client.post('/answer', json={'question': 'DSC?'}).json() == {'status': 'existing-contract'}
    old.assert_called_once()
    preparation.assert_not_called()


def smoke_prepared(tmp_path, monkeypatch):
    from app.evaluation import preparation_run as smoke
    from app.records.sources import file_hash

    session, e, sources = setup_service(monkeypatch)
    payload = service.prepare_answer(session, _settings(), 'Conductivity?')
    parent = {'observed_queries': [{'id': 'constructed_smoke', 'question': 'Conductivity?',
                                   'trace': {'evidence': [asdict(e)]}, 'sources': sources}]}
    monkeypatch.setattr(smoke, 'load_qualifiers', lambda path: (parent, {}))
    weights = tmp_path / 'constructed-weights'
    weights.write_bytes(b'not-a-real-model')
    cache = tmp_path / 'cache.json'
    cache.write_text(json.dumps({'query_embedding_files': {str(weights): file_hash(weights)},
                                'cache_directory': str(tmp_path)}), encoding='utf-8')
    prepared = tmp_path / 'prepared'
    smoke.prepare(tmp_path / 'unused-parent', cache, prepared)
    return prepared, payload, weights


def test_smoke_export_preserves_native_result_and_is_repeatable_exclusive_and_escaped(tmp_path, monkeypatch):
    from app.evaluation import preparation_run as smoke
    from app.records.sources import file_hash

    prepared, payload, _ = smoke_prepared(tmp_path, monkeypatch)
    captured = tmp_path / 'captured'
    captured.mkdir()
    rows = [{'id': 'constructed_smoke', 'response': payload, 'evidence_identical_to_stage29': True}]
    report = {'version': service.VERSION, 'summary': smoke.summarize(rows), 'results': rows}
    (captured / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    _, bindings = smoke.load(prepared)
    (captured / 'manifest.json').write_text(json.dumps({'version': service.VERSION, 'phase': 'read_only_api_smoke',
        'inputs': bindings, 'code': {}, 'outputs': {'report.json': file_hash(captured / 'report.json')}}), encoding='utf-8')
    first, repeat = tmp_path / 'first', tmp_path / 'repeat'
    smoke.export(prepared, captured, first)
    smoke.export(prepared, captured, repeat)
    assert json.loads((first / 'report.json').read_bytes()) == json.loads((captured / 'report.json').read_bytes())
    for path in first.iterdir():
        assert path.read_bytes() == (repeat / path.name).read_bytes()
    with pytest.raises(FileExistsError):
        smoke.export(prepared, captured, first)


@pytest.mark.parametrize('variant', ['phase', 'code', 'input', 'plan_hash'])
def test_smoke_freeze_drift_is_not_reused(tmp_path, monkeypatch, variant):
    from app.evaluation import preparation_run as smoke

    prepared, _, weights = smoke_prepared(tmp_path, monkeypatch)
    manifest = prepared / 'manifest.json'
    data = json.loads(manifest.read_bytes())
    if variant == 'phase':
        data['phase'] = 'other'
    elif variant == 'code':
        data['code'] = {}
    elif variant == 'input':
        weights.write_bytes(b'changed')
    else:
        (prepared / 'plan.json').write_bytes(b'changed')
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        smoke.load(prepared)
