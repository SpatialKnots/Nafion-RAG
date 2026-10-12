import json
import re
from types import SimpleNamespace
from uuid import uuid4

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db.models import Article, Chunk
from app.db.session import get_session
from app.facts import review_ui
from app.facts.review_store import code_hashes, load_snapshot, sha
from app.main import app


@pytest.fixture
def review_client(tmp_path, monkeypatch):
    article_id, chunk_id = uuid4(), uuid4()
    pdf = tmp_path / 'original.pdf'
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), 'Scale bars, 10 nm.')
        document.save(pdf)
    source_text = 'Scale bars, 10 nm.'
    source = dict(article_id=str(article_id), title='<script>alert(1)</script>', pdf_path=str(pdf),
                  pdf_sha256=sha(pdf.read_bytes()), chunk_sha256=sha(source_text.encode()), text=source_text,
                  page_start=1, page_end=1, text_layer='original', source_type='text',
                  page_hashes={'1': sha(source_text.encode())})
    record = dict(id='item-one', chunk_id=str(chunk_id), direction='added',
                  candidate=dict(field_value_text='10 nm', field_name='length'), historical_annotations=[],
                  occurrences=[dict(start=12, end=17, decision='accepted', reason='selected',
                                    context_cues=[], context_start=0, context_end=len(source_text))])
    data = dict(schema_version=1, created_at='2026-09-14', diff_sha256='diff', code_hashes=code_hashes(),
                sources={str(chunk_id): source}, records=[record])
    raw = json.dumps(data).encode()
    sid = sha(raw)
    (tmp_path / 'snapshots').mkdir()
    (tmp_path / 'snapshots' / f'{sid}.json').write_bytes(raw)
    (tmp_path / 'current').write_text(sid)
    monkeypatch.setattr(review_ui, 'review_root', lambda: tmp_path)
    chunk = SimpleNamespace(text=source_text, article_id=article_id, text_layer='original',
                            source_type='text', page_start=1, page_end=1)
    article = SimpleNamespace(id=article_id, checksum_sha256=source['pdf_sha256'], pdf_original_path=str(pdf))
    layer = SimpleNamespace(text=source_text)

    class FakeSession:
        def get(self, model, identifier):
            return {Chunk: chunk, Article: article}[model]

        def scalar(self, statement):
            return layer

    app.dependency_overrides[get_session] = lambda: FakeSession()
    with TestClient(app) as client:
        page = client.get('/ui/numeric-review')
        assert page.status_code == 200
        csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        form = dict(snapshot=sid, item='item-one', csrf=csrf, revision=0, verdict='blocker',
                    comment='Scale bar, not measured thickness', reviewer='Test reviewer', page=1, occurrence_start=12)
        yield client, form, tmp_path, chunk, layer, pdf
    app.dependency_overrides.pop(get_session)


def test_save_reload_history_export_and_no_source_write(review_client):
    client, form, root, chunk, layer, pdf = review_client
    original = pdf.read_bytes()
    page = client.get('/ui/numeric-review')
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page.text
    assert '<script>alert(1)</script>' not in page.text
    result = client.post('/ui/numeric-review/decision', data=form)
    assert result.status_code == 200 and 'Решение сохранено' in result.text
    assert 'Scale bar, not measured thickness' in result.text
    form.update(revision=1, verdict='ambiguous', comment='Needs a second review')
    assert client.post('/ui/numeric-review/decision', data=form).status_code == 200
    exported = client.get('/ui/numeric-review/export', params={'snapshot': form['snapshot']}).json()
    assert [r['verdict'] for r in exported['history']] == ['blocker', 'ambiguous']
    assert exported['applied'] is False
    assert pdf.read_bytes() == original
    assert len(list((root / 'snapshots').iterdir())) == 1


def test_concurrent_revision_conflict_preserves_first_save(review_client):
    client, form, *_ = review_client
    assert client.post('/ui/numeric-review/decision', data=form).status_code == 200
    assert client.post('/ui/numeric-review/decision', data=form).status_code == 409
    history = client.get('/ui/numeric-review/export', params={'snapshot': form['snapshot']}).json()['history']
    assert len(history) == 1


@pytest.mark.parametrize('change', ['chunk', 'layer', 'pdf', 'code'])
def test_stale_source_or_code_blocks_decision(review_client, monkeypatch, change):
    client, form, root, chunk, layer, pdf = review_client
    if change == 'chunk':
        chunk.text += ' changed'
    elif change == 'layer':
        layer.text += ' changed'
    elif change == 'pdf':
        pdf.write_bytes(b'changed')
    else:
        monkeypatch.setattr(review_ui, 'code_hashes', lambda: {})
    assert client.post('/ui/numeric-review/decision', data=form).status_code == 409
    assert client.get('/ui/numeric-review/export', params={'snapshot': form['snapshot']}).json()['history'] == []


@pytest.mark.parametrize(('field', 'value'), [('csrf', 'bad'), ('occurrence_start', 999), ('page', 2),
                                            ('verdict', 'approved'), ('comment', '   '), ('reviewer', '  ')])
def test_invalid_decisions_do_not_write(review_client, field, value):
    client, form, *_ = review_client
    form[field] = value
    assert client.post('/ui/numeric-review/decision', data=form).status_code in {400, 403}
    assert client.get('/ui/numeric-review/export', params={'snapshot': form['snapshot']}).json()['history'] == []


def test_snapshot_tampering_and_path_traversal_rejected(review_client):
    client, form, root, *_ = review_client
    assert client.get('/ui/numeric-review', params={'snapshot': '../../other'}).status_code == 409
    sid, _ = load_snapshot(root)
    (root / 'snapshots' / f'{sid}.json').write_text('{}')
    assert client.post('/ui/numeric-review/decision', data=form).status_code == 409


def test_filter_and_missing_item(review_client):
    client, *_ = review_client
    assert 'Найдено: 0' in client.get('/ui/numeric-review?status=acceptable').text
    assert 'Найдено: 1' in client.get('/ui/numeric-review?direction=added').text
    assert client.get('/ui/numeric-review?item=missing').status_code == 404


def test_original_page_image_and_bounds(review_client):
    client, form, *_ = review_client
    params = dict(snapshot=form['snapshot'], item=form['item'], page=1)
    result = client.get('/ui/numeric-review/page-image', params=params)
    assert result.status_code == 200 and result.content.startswith(b'\x89PNG\r\n\x1a\n')
    assert client.get('/ui/numeric-review/page-image', params=params | {'page': 2}).status_code == 400


def test_image_refuses_changed_pdf(review_client):
    client, form, root, chunk, layer, pdf = review_client
    pdf.write_bytes(b'changed')
    result = client.get('/ui/numeric-review/page-image', params=dict(snapshot=form['snapshot'], item=form['item'], page=1))
    assert result.status_code == 409
