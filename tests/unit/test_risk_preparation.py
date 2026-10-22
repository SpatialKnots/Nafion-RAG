"""Preparation risk integration checks; constructed evidence is not scientific gold."""

import copy
import json
from html import escape
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.evaluation.context_risks import audit_context_risks, canonical
from app.generation import risk_routes as routes
from app.generation.risk_routes import VERSION, render_risks
from app.records.sources import file_hash
from tests.unit.test_answer_preparation import client as preparation_client_fixture
from tests.unit.test_context_risks import asset, parent_fixture, real_parent

client = preparation_client_fixture


def envelope(parent):
    return {'version': VERSION, 'preparation': parent, 'audit': audit_context_risks(parent),
            'generation_performed': False, 'external_request_constructed': False, 'network_ready': False}


def test_api_passes_all_validated_options_and_preserves_complete_preparation(client, tmp_path, monkeypatch):
    parent, _ = parent_fixture(tmp_path, baseline_allowed=False)
    original = copy.deepcopy(parent)
    block = Mock(return_value=parent)
    monkeypatch.setattr(routes, 'block_api', block)
    library = UUID(int=33)
    response = client.post('/answer/prepare/blocks/risks', json={'question': 'Conductivity?', 'method': 'exact',
        'top_k': 3, 'collection': 'selected-library', 'library_source_id': str(library),
        'answer_style': 'mini_review', 'answer_language': 'ru'})
    assert response.status_code == 200
    payload = response.json()
    assert canonical(payload) == canonical(envelope(parent))
    assert parent == original
    request = block.call_args.args[1]
    assert request.library_source_id == library and request.top_k == 3 and request.collection == 'selected-library'
    assert request.method == 'exact' and request.answer_style == 'mini_review' and request.answer_language == 'ru'
    assert payload['audit']['parent_blocking_reasons'] == parent['blocking_reasons']
    assert not payload['network_ready'] and not payload['audit']['admission_changed']


@pytest.mark.parametrize('extra', [{'question': ''}, {'top_k': 0}, {'method': 'unknown'}, {'library_source_id': 'bad'},
    {'generate': True}, {'pdf_path': 'private.pdf'}, {'plans': {}}, {'audit': {}}, {'answer_language': 'unknown'}])
def test_invalid_request_never_runs_preparation(client, monkeypatch, extra):
    block = Mock(side_effect=AssertionError('Invalid request must not prepare'))
    monkeypatch.setattr(routes, 'block_api', block)
    assert client.post('/answer/prepare/blocks/risks', json={'question': 'Conductivity?', **extra}).status_code == 422
    block.assert_not_called()


def test_real_pdf_block_builder_and_auditor_are_used_without_generation(client, tmp_path, monkeypatch):
    from app.generation import block_routes, service
    from app.records.sources import file_hash
    parent, pdf = real_parent(tmp_path)
    checksum = file_hash(pdf)
    monkeypatch.setattr(block_routes, 'prepare_api', Mock(return_value=parent['baseline']))
    forbidden = Mock(side_effect=AssertionError('Generation factory must not run'))
    monkeypatch.setattr(service, 'build_answer_provider', forbidden)
    response = client.post('/answer/prepare/blocks/risks', json={'question': parent['baseline']['question']})
    assert response.status_code == 200
    assert canonical(response.json()) == canonical(envelope(parent))
    assert file_hash(pdf) == checksum
    forbidden.assert_not_called()


@pytest.mark.parametrize('status', [400, 409, 503])
def test_preparation_errors_retain_status_in_api_and_complete_ui_form(client, monkeypatch, status):
    monkeypatch.setattr(routes, 'block_api', Mock(side_effect=HTTPException(status, '<unsafe> source failure')))
    assert client.post('/answer/prepare/blocks/risks', json={'question': 'Conductivity?'}).status_code == status
    response = client.post('/ui/answer/prepare/blocks/risks', data={'question': '<query>', 'method': 'exact',
        'top_k': '2', 'collection': 'private-library', 'library_source_id': str(UUID(int=9))})
    assert response.status_code == status and '&lt;unsafe&gt; source failure' in response.text
    assert '<unsafe>' not in response.text and '&lt;query&gt;' in response.text
    assert 'action="/ui/answer/prepare/blocks/risks"' in response.text
    assert 'value="private-library"' in response.text and '<option selected>exact</option>' in response.text
    assert str(UUID(int=9)) in response.text and '<html' in response.text


def test_audit_source_identity_failure_is_visible(client, tmp_path, monkeypatch):
    parent, _ = parent_fixture(tmp_path)
    monkeypatch.setattr(routes, 'block_api', Mock(return_value=parent))
    monkeypatch.setattr(routes, 'audit_context_risks', Mock(side_effect=ValueError('constructed audit identity failure')))
    response = client.post('/answer/prepare/blocks/risks', json={'question': 'Conductivity?'})
    assert response.status_code == 400 and 'audit identity failure' in response.text


def test_unexpected_audit_failure_propagates(client, tmp_path, monkeypatch):
    parent, _ = parent_fixture(tmp_path)
    monkeypatch.setattr(routes, 'block_api', Mock(return_value=parent))
    monkeypatch.setattr(routes, 'audit_context_risks', Mock(side_effect=RuntimeError('constructed failure')))
    with pytest.raises(RuntimeError, match='constructed failure'):
        client.post('/answer/prepare/blocks/risks', json={'question': 'Conductivity?'})


def test_ui_preserves_exact_text_unknown_states_options_and_old_refusal(client, tmp_path, monkeypatch):
    parent, _ = parent_fixture(tmp_path, [asset((20, 1, 30, 3))], baseline_allowed=False,
        blocks=['Background.\n', 'Background.\n', 'Background.\n', 'Conductivity <script>source</script>.\n',
                'Background.\n', 'Background.\n', 'Background.\n'])
    payload = envelope(parent)
    monkeypatch.setattr(routes, 'risk_api', Mock(return_value=payload))
    response = client.post('/ui/answer/prepare/blocks/risks', data={'question': '<script>query</script>',
        'method': 'exact', 'collection': 'selected-library', 'top_k': '3', 'library_source_id': str(UUID(int=5))})
    assert response.status_code == 200
    assert '&lt;script&gt;query&lt;/script&gt;' in response.text and '<script>query' not in response.text
    assert '&lt;script&gt;source&lt;/script&gt;' in response.text and '<script>source' not in response.text
    assert 'значимость неизвестна' in response.text and 'недостаточно доказательств' in response.text
    assert 'value="selected-library"' in response.text and '<option selected>exact</option>' in response.text
    assert 'data-risk-search' in response.text and 'data-risk-window' in response.text
    assert 'action="/ui/answer/prepare/blocks/risks"' in response.text and 'Генерация отключена' in response.text
    for w in payload['audit']['pages'][0]['windows']:
        assert escape(w['quote']) in response.text


@pytest.mark.parametrize('cookie,explicit', [(str(UUID(int=7)), None), ('malformed', None),
                                          (str(UUID(int=7)), str(UUID(int=8)))])
def test_get_library_scope_cookie_and_explicit_override_without_preparation(client, monkeypatch, cookie, explicit):
    client.cookies.set('ariadne_library_id', cookie)
    block = Mock(side_effect=AssertionError('GET must not prepare'))
    monkeypatch.setattr(routes, 'block_api', block)
    response = client.get('/ui/answer/prepare/blocks/risks', params={'library_source_id': explicit} if explicit else {})
    assert response.status_code == 200
    expected = explicit or (cookie if cookie != 'malformed' else '')
    assert 'name="library_source_id" value="' + expected + '"' in response.text
    assert 'action="/ui/answer/prepare/blocks/risks"' in response.text
    block.assert_not_called()


@pytest.mark.parametrize('mode', ['no_anchor', 'whole_page', 'unproven_mapping'])
def test_all_empty_and_guard_states_remain_in_rendered_audit(tmp_path, mode):
    parent, region = parent_fixture(tmp_path, question='DSC?' if mode == 'no_anchor' else 'Conductivity?',
        blocks=[f'Conductivity sample {i}.\n' for i in range(7)] if mode == 'whole_page' else None)
    payload = envelope(parent)
    if mode == 'unproven_mapping':
        payload['audit']['pages'][0].update(mapping_unproven=True, windows=[])
    text = render_risks(payload)
    assert ('не подтверждена' if mode == 'unproven_mapping' else
            'Нет удерживаемого окружения' if mode == 'no_anchor' else 'покрывает полную страницу') in text
    assert f'/articles/{region.article_id}/pdf?layer=original#page=1' in text
    assert region.layer_pdf_path not in text.split('<summary>Точный источник')[0]


def test_offline_pdf_links_are_explicit_renderer_option_only(tmp_path):
    parent, region = parent_fixture(tmp_path)
    text = render_risks(envelope(parent), local_pdf_links=True)
    from pathlib import Path
    assert Path(region.original_pdf_path).as_uri() + '#page=1' in text


def test_preparation_forms_discover_new_mode(client):
    for url in ['/ui/answer/prepare', '/ui/answer/prepare/blocks']:
        assert 'href="/ui/answer/prepare/blocks/risks"' in client.get(url).text


@pytest.mark.parametrize('entry', ['/ui/answer/prepare', '/ui/answer/prepare/blocks'])
def test_navigation_to_audit_preserves_explicit_library_over_different_cookie(client, entry):
    selected, cookie = UUID(int=40), UUID(int=41)
    client.cookies.set('ariadne_library_id', str(cookie))
    first = client.get(entry, params={'library_source_id': str(selected)})
    target = '/ui/answer/prepare/blocks/risks?library_source_id=' + str(selected)
    assert 'href="' + target + '"' in first.text
    second = client.get(target)
    assert 'name="library_source_id" value="' + str(selected) + '"' in second.text
    assert 'name="library_source_id" value="' + str(cookie) + '"' not in second.text


def frozen_fixture(tmp_path):
    from app.evaluation import risk_preparation_run as runner
    parent, region = parent_fixture(tmp_path)
    payload = envelope(parent)
    prepared, captured = tmp_path / 'prepared', tmp_path / 'captured'
    prepared.mkdir()
    (captured / 'constructed').mkdir(parents=True)
    plan = {'version': VERSION, 'tasks': [{'id': 'constructed', 'previous_preparation': parent,
        'previous_audit': payload['audit']}], 'historical_source_mappings': []}
    (prepared / 'plan.json').write_text(canonical(plan), encoding='utf-8')
    (prepared / 'manifest.json').write_text(canonical({'version': VERSION, 'phase': 'prepared_before_risk_api_smoke',
        'inputs': {region.original_pdf_path: region.original_pdf_sha256},
        'code': {str(Path(n).resolve()): file_hash(Path(n)) for n in runner.CODE},
        'outputs': {'plan.json': file_hash(prepared / 'plan.json')}}), encoding='utf-8')
    _, bindings = runner.load(prepared)
    rows = [{'id': 'constructed', 'response': payload, 'preparation_identical': True, 'audit_identical': True}]
    report = {'version': VERSION, 'summary': runner.summarize(rows), 'results': rows}
    (captured / 'report.json').write_text(canonical(report), encoding='utf-8')
    (captured / 'constructed' / 'response.json').write_text(canonical(payload), encoding='utf-8')
    (captured / 'manifest.json').write_text(canonical({'version': VERSION, 'phase': 'read_only_risk_api_smoke',
        'inputs': bindings, 'code': {}, 'outputs': {p.relative_to(captured).as_posix(): file_hash(p)
            for p in captured.rglob('*') if p.is_file()}}), encoding='utf-8')
    return prepared, captured, region


def test_frozen_exports_are_exclusive_deterministic_and_have_only_local_pdf_links(tmp_path):
    from app.evaluation import risk_preparation_run as runner
    prepared, captured, region = frozen_fixture(tmp_path)
    first, repeat = tmp_path / 'review', tmp_path / 'repeat'
    assert runner.export(prepared, captured, first) == runner.export(prepared, captured, repeat)
    for p in first.iterdir():
        assert p.read_bytes() == (repeat / p.name).read_bytes()
    page = (first / 'review.html').read_text(encoding='utf-8')
    assert 'href="/articles/' not in page
    assert Path(region.original_pdf_path).as_uri() in page
    assert (first / 'report.json').read_bytes() != b''
    assert canonical(json.loads((first / 'report.json').read_bytes())) == canonical(json.loads((captured / 'report.json').read_bytes()))
    with pytest.raises(FileExistsError):
        runner.export(prepared, captured, first)


@pytest.mark.parametrize('variant', ['phase', 'code', 'plan', 'private_pdf', 'native', 'summary', 'comparison'])
def test_frozen_drift_cannot_silently_create_review(tmp_path, variant):
    from app.evaluation import risk_preparation_run as runner
    prepared, captured, region = frozen_fixture(tmp_path)
    if variant in {'phase', 'code'}:
        path = prepared / 'manifest.json'
        data = json.loads(path.read_bytes())
        data['phase' if variant == 'phase' else 'code'] = 'wrong' if variant == 'phase' else {}
        path.write_text(canonical(data), encoding='utf-8')
    elif variant == 'private_pdf':
        Path(region.original_pdf_path).write_bytes(b'changed')
    elif variant == 'plan':
        (prepared / 'plan.json').write_bytes(b'changed')
    elif variant == 'native':
        (captured / 'constructed' / 'response.json').write_bytes(b'changed')
    else:
        path = captured / 'report.json'
        data = json.loads(path.read_bytes())
        if variant == 'summary':
            data['summary']['diagnostic_windows'] += 1
        else:
            data['results'][0]['preparation_identical'] = False
            data['summary'] = runner.summarize(data['results'])
        path.write_text(canonical(data), encoding='utf-8')
        manifest = captured / 'manifest.json'
        value = json.loads(manifest.read_bytes())
        value['outputs']['report.json'] = file_hash(path)
        manifest.write_text(canonical(value), encoding='utf-8')
    with pytest.raises(ValueError):
        runner.export(prepared, captured, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('status', [400, 409])
def test_audit_known_errors_map_to_diagnostic_status(client, tmp_path, monkeypatch, status):
    from app.documents.service import PdfStorageIntegrityError
    parent, _ = parent_fixture(tmp_path)
    monkeypatch.setattr(routes, 'block_api', Mock(return_value=parent))
    error = ValueError('bad identity') if status == 400 else PdfStorageIntegrityError('bad PDF')
    monkeypatch.setattr(routes, 'audit_context_risks', Mock(side_effect=error))
    assert client.post('/answer/prepare/blocks/risks', json={'question': 'Conductivity?'}).status_code == status
