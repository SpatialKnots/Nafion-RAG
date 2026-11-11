"""Actual experimental API/UI controls with synthetic search/session/provider."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.generation import required_fields_guard_routes as routes
from app.generation import service
from app.generation.providers import GeneratedClaim, ProviderResult
from app.main import app
from app.retrieval.search import SearchResponse, SearchResult

BODY = ('Energy density of731 Wh kg−1 based on the total cathode/anode masses is achieved. '
        'The Li metal was depleted after 143 cycles.')


class Session:
    def __init__(self):
        self.statements, self.rollbacks = [], 0

    def execute(self, statement):
        self.statements.append(str(statement))

    def rollback(self):
        self.rollbacks += 1


class Provider:
    def __init__(self, text):
        self.result = ProviderResult(True, [GeneratedClaim(text, ['E1'])], 'synthetic', 'offline')
        self.calls = 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return self.result


@pytest.fixture
def runtime(monkeypatch):
    state = {'session': Session(), 'provider': Provider('Energy density731Wh/kg.'), 'searches': []}
    settings = Settings(_env_file=None, gigachat_credentials='offline-placeholder')
    result = SearchResult(article_id='00000000-0000-0000-0000-000000000001',
        chunk_id='00000000-0000-0000-0000-000000000002', title='Constructed evidence', doi=None,
        page_start=2, page_end=3, source_type='main_text', snippet=BODY, full_text=BODY,
        score=1, retrieval_method='frozen_synthetic')

    def search(*args, **kwargs):
        state['searches'].append((args, kwargs))
        return SearchResponse(query='energy density', results=[result])

    monkeypatch.setattr(service, 'search_chunks', search)
    monkeypatch.setattr(routes, 'make_provider', lambda s: state['provider'])
    monkeypatch.setattr(service, 'build_answer_provider', lambda s: state['provider'])

    def session():
        yield state['session']

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, state
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)


def test_actual_api_holds_missing_fields_and_retains_native_for_review(runtime):
    client, state = runtime
    original = deepcopy(state['provider'].result)
    response = client.post('/answer/experimental/required-fields', json={'question': 'energy density'})
    assert response.status_code == 200
    data = response.json()
    assert data['delivery_status'] == 'insufficient_confirmation'
    assert data['answer']['status'] == 'insufficient_evidence' and data['answer']['claims'] == []
    assert data['review']['native_result']['claims'][0]['text'] == original.claims[0].text
    assert state['provider'].result == original and state['provider'].calls == 1
    assert state['session'].rollbacks == 1
    assert state['session'].statements == ['SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY']


def test_actual_api_retains_filled_answer_without_scientific_acceptance(runtime):
    client, state = runtime
    state['provider'] = Provider('Energy density731Wh/kg based on the total cathode/anode masses.')
    data = client.post('/answer/experimental/required-fields', json={'question': 'energy density'}).json()
    assert data['delivery_status'] == 'required_literal_fields_present'
    assert data['answer']['status'] == 'answered' and data['review']['scientific_support'] == 'not_evaluated'
    assert state['provider'].calls == 1


def test_unrecognized_wording_is_withheld_for_review_not_called_error(runtime):
    client, state = runtime
    state['provider'] = Provider('Energy density731Wh/kg based on the combined positive and negative electrode masses.')
    data = client.post('/answer/experimental/required-fields', json={'question': 'energy density'}).json()
    assert data['delivery_status'] == 'insufficient_confirmation'
    assert data['review']['reasons'][0]['state'] == 'answer_wording_or_binding_not_recognized'
    assert not data['review']['reasons'][0]['scientific_error_established']


def test_normal_answer_api_keeps_previous_body_and_does_not_activate_guard(runtime):
    client, state = runtime
    import app.main as main

    # Normal route obtains settings directly; avoid environment credentials in this synthetic test.
    with patch.object(main, 'get_settings', lambda: Settings(_env_file=None, gigachat_credentials='offline-placeholder')):
        response = client.post('/answer', json={'question': 'energy density'})
    assert response.status_code == 200 and response.json()['status'] == 'answered'
    assert response.json()['claims'][0]['text'] == 'Energy density731Wh/kg.'
    assert 'review' not in response.json() and state['provider'].calls == 1


def test_request_options_and_library_scope_reach_unchanged_search(runtime):
    client, state = runtime
    payload = {'question': 'energy density', 'collection': 'subset', 'top_k': 3, 'method': 'exact',
               'answer_language': 'en', 'library_source_id': '00000000-0000-0000-0000-000000000007'}
    response = client.post('/answer/experimental/required-fields', json=payload)
    assert response.status_code == 200
    args, kwargs = state['searches'][0]
    assert args[2:4] == ('subset', 3) and kwargs['method'] == 'exact'
    assert str(kwargs['filters'].library_source_id) == payload['library_source_id']


@pytest.mark.parametrize('extra', ['evidence', 'native_result', 'reference_answer', 'path'])
def test_client_cannot_submit_evidence_answers_gold_or_paths(runtime, extra):
    client, state = runtime
    response = client.post('/answer/experimental/required-fields', json={'question': 'energy density', extra: 'untrusted'})
    assert response.status_code == 422 and state['provider'].calls == 0 and not state['searches']


def test_ui_status_and_raw_withheld_result_are_distinct_and_escaped(runtime):
    client, state = runtime
    state['provider'] = Provider('Energy density731Wh/kg. <script id="evil">bad()</script>')
    response = client.post('/ui/answer/experimental/required-fields', data={'question': 'energy density'})
    assert response.status_code == 200
    assert 'Недостаточно подтверждений' in response.text and 'не допущен' in response.text
    assert 'Причины и неустановленные связи' in response.text
    assert '<script id="evil">' not in response.text and '&lt;script' in response.text
    assert state['provider'].calls == 1


def test_ui_get_does_not_generate(runtime):
    client, state = runtime
    response = client.get('/ui/answer/experimental/required-fields')
    assert response.status_code == 200 and state['provider'].calls == 0 and not state['searches']


def test_preprovider_refusal_is_distinct_and_makes_no_model_call(runtime, monkeypatch):
    client, state = runtime
    monkeypatch.setattr(service, 'search_chunks', lambda *a, **kw: SearchResponse(query='energy density', results=[]))
    data = client.post('/answer/experimental/required-fields', json={'question': 'energy density'}).json()
    assert data['delivery_status'] == 'baseline_preprovider_refusal' and data['review'] is None
    assert state['provider'].calls == 0 and state['session'].rollbacks == 1


def test_native_abstention_has_its_own_status(runtime):
    client, state = runtime
    state['provider'].result = ProviderResult(False, [], 'synthetic', 'offline')
    data = client.post('/answer/experimental/required-fields', json={'question': 'energy density'}).json()
    assert data['delivery_status'] == 'provider_abstained' and not data['review']['withheld']
    assert state['provider'].calls == 1


def test_provider_failure_propagates_once_and_transaction_rolls_back(runtime, monkeypatch):
    from app.generation.providers import GenerationUnavailableError

    client, state = runtime

    def fail(*args, **kwargs):
        state['provider'].calls += 1
        raise GenerationUnavailableError('synthetic failure')

    monkeypatch.setattr(state['provider'], 'generate', fail)
    response = client.post('/answer/experimental/required-fields', json={'question': 'energy density'})
    assert response.status_code == 503 and state['provider'].calls == 1 and state['session'].rollbacks == 1
