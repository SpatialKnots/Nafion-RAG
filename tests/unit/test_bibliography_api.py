"""Read-only metadata API/UI and frozen metadata review regressions."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from app.db.session import get_session
from app.documents.service import PdfStorageIntegrityError
from app.main import app
from app.metadata import routes
from app.metadata.bibliography import VERSION, canonical, refresh
from app.metadata.bridge_run import export, render, summary, write_review
from tests.unit.test_answer_preparation import client as preparation_client_fixture
from tests.unit.test_bibliography_bridge import setup

client = preparation_client_fixture


def test_api_is_read_only_and_html_escapes_all_recorded_values(client, monkeypatch):
    article = SimpleNamespace(id=UUID(int=8))
    app.dependency_overrides[get_session] = lambda: SimpleNamespace(get=lambda *args: article)
    value = {'version': VERSION, 'state': 'not_extracted', 'current_values': {'authors': '<script>bad</script>'}}
    record = Mock(return_value=value)
    monkeypatch.setattr(routes, 'recorded', record)
    assert client.get(f'/articles/{article.id}/bibliography').json() == value
    page = client.get(f'/ui/articles/{article.id}/bibliography')
    assert page.status_code == 200 and '&lt;script&gt;bad&lt;/script&gt;' in page.text
    assert '<script>bad</script>' not in page.text and '<form' not in page.text
    assert 'не являются независимым подтверждением' in page.text
    assert client.post(f'/articles/{article.id}/bibliography', json={'authors': ['injected']}).status_code == 405


@pytest.mark.parametrize('variant,status', [('missing', 404), ('stale', 409)])
def test_missing_and_stale_metadata_are_not_hidden(client, monkeypatch, variant, status):
    app.dependency_overrides[get_session] = lambda: SimpleNamespace(get=lambda *args:
        None if variant == 'missing' else SimpleNamespace())
    monkeypatch.setattr(routes, 'recorded', Mock(side_effect=PdfStorageIntegrityError('source mismatch')))
    response = client.get(f'/articles/{UUID(int=8)}/bibliography')
    assert response.status_code == status


def test_unexpected_metadata_error_propagates(client, monkeypatch):
    app.dependency_overrides[get_session] = lambda: SimpleNamespace(get=lambda *args: SimpleNamespace())
    monkeypatch.setattr(routes, 'recorded', Mock(side_effect=RuntimeError('DB failure')))
    with pytest.raises(RuntimeError, match='DB failure'):
        client.get(f'/articles/{UUID(int=8)}/bibliography')


def report_fixture(tmp_path, monkeypatch):
    session, article, region = setup(tmp_path, monkeypatch)
    row = refresh(session, None, article)
    proposal = row.payload
    rows = [{'article_id': str(article.id), 'title': 'Existing <unsafe> title', 'proposal': proposal,
        'historical_tac': {'sections': [{'kind': 'A', 'quote': 'Full <unsafe> abstract', 'current_source_valid': True}],
                           'schema': 'constructed_legacy_snapshot'}}]
    return {'version': VERSION, 'phase': 'applied_metadata_proposals', 'articles': rows, 'summary': summary(rows)}, region


def test_review_keeps_agreed_columns_exact_proposals_and_full_historical_text(tmp_path, monkeypatch):
    report, region = report_fixture(tmp_path, monkeypatch)
    page = render(report)
    for header in ['Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms', 'Original file']:
        assert '<th>' + header + '</th>' in page
    assert 'Full &lt;unsafe&gt; abstract' in page and 'Existing &lt;unsafe&gt;' in page
    assert '<unsafe>' not in page and 'Alice Smith' in page and 'Terms не пересчитывались' in page
    assert Path(region.original_pdf_path).as_uri() in page and 'type="search"' in page and '<form' not in page


def test_review_exports_are_exclusive_deterministic_and_reject_input_drift(tmp_path, monkeypatch):
    report, region = report_fixture(tmp_path, monkeypatch)
    capture = tmp_path / 'capture'
    write_review(capture, report, {region.original_pdf_path: region.original_pdf_sha256})
    first, repeat = tmp_path / 'first', tmp_path / 'repeat'
    assert export(capture, first) == export(capture, repeat)
    for p in first.iterdir():
        assert p.read_bytes() == (repeat / p.name).read_bytes()
    assert canonical(json.loads((first / 'report.json').read_bytes())) == canonical(report)
    with pytest.raises(FileExistsError):
        export(capture, first)
    Path(region.original_pdf_path).write_bytes(b'changed')
    with pytest.raises(ValueError):
        export(capture, tmp_path / 'drift')
    assert not (tmp_path / 'drift').exists()


def test_existing_preparation_links_to_recorded_metadata(client, monkeypatch):
    import app.generation.preparation as service
    from app.generation import preparation_routes
    from tests.unit.test_answer_preparation import _settings, setup_service
    session, item, _ = setup_service(monkeypatch)
    payload = service.prepare_answer(session, _settings(), 'Conductivity?')
    monkeypatch.setattr(preparation_routes, 'prepare_api', Mock(return_value=payload))
    page = client.post('/ui/answer/prepare', data={'question': 'Conductivity?'})
    assert f'/ui/articles/{item.article_id}/bibliography' in page.text


def test_fresh_preview_of_already_applied_fields_preserves_immutable_history(tmp_path, monkeypatch):
    from contextlib import nullcontext

    from app.db.models import Article
    from app.metadata import bridge_run as runner
    from app.metadata.bibliography import preview
    session, article, _ = setup(tmp_path, monkeypatch)
    old = refresh(session, None, article)
    expected = preview(session, None, article)
    assert expected['projection']['previous_values'] != old.payload['projection']['previous_values']
    folder = tmp_path / 'preview'
    folder.mkdir()
    rows = [{'article_id': str(article.id), 'title': 'Constructed', 'proposal': expected, 'historical_tac': {'sections': []}}]
    (folder / 'report.json').write_text(canonical({'articles': rows}), encoding='utf-8')
    session.scalar = lambda query: article if query.column_descriptions[0]['entity'] is Article else session.rows[-1]
    session.get = lambda *args: article
    factory = Mock(side_effect=lambda: nullcontext(session))
    factory.begin = lambda: nullcontext(session)
    monkeypatch.setattr(runner, 'SessionLocal', factory)
    monkeypatch.setattr(runner, 'get_settings', lambda: None)
    monkeypatch.setattr(runner, 'load', lambda *args: ({'article_ids': [str(article.id)]}, {}))
    monkeypatch.setattr(runner, 'read_frozen', lambda *args: ({'phase': 'read_only_metadata_preview'}, {}))
    writer = Mock()
    monkeypatch.setattr(runner, 'write_review', writer)
    assert runner.apply(tmp_path / 'prepared', folder, tmp_path / 'out')['articles'] == 1
    assert len(session.rows) == 1
    assert writer.call_args.args[1]['articles'][0]['recorded']['extraction_id'] == str(old.id)
