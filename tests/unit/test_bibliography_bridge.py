"""Legacy reuse, projection ownership and exact native PDF evidence regressions."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import fitz
import pytest

from app.db.models import ArticleMetadataExtraction
from app.documents.service import PdfStorageIntegrityError
from app.metadata import bibliography as bridge
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_article_windows import page_fixture


def native(tmp_path):
    template, _ = page_fixture(tmp_path)
    path = tmp_path / 'metadata.pdf'
    with fitz.open() as document:
        page = document.new_page()
        for y, text, size in [(40, 'Example Journal 2024, 12, 1-7', 9),
            (80, 'Scientific study of membrane conductivity', 17), (115, 'Alice Smith, Bob Jones', 11),
            (145, 'Department of Chemistry', 9), (220, 'ABSTRACT: Conductivity was measured.', 11)]:
            page.insert_text((40, y), text, fontsize=size)
        raw = page.get_text('text')
        document.save(path)
    checksum = file_hash(path)
    data = template.model_dump()
    data.update(original_pdf_path=str(path), layer_pdf_path=str(path), original_pdf_sha256=checksum,
        layer_pdf_sha256=checksum, page_text=raw, page_text_sha256=text_hash(raw), quote=raw,
        quote_sha256=text_hash(raw), start=0, end=len(raw))
    data['region_id'] = source_identity(data)
    return SourceRegion.model_validate(data)


class Session:
    def __init__(self, article, region):
        self.article = article
        self.pages = [SimpleNamespace(page_number=1, selected_text_layer='original', text=region.page_text)]
        self.rows = []
        self.locks = 0

    def scalars(self, query):
        return self.pages

    def scalar(self, query):
        return self.rows[-1] if self.rows else None

    def refresh(self, article, with_for_update=False):
        assert article is self.article and with_for_update
        self.locks += 1

    def add(self, row):
        assert isinstance(row, ArticleMetadataExtraction)
        row.sequence_no = len(self.rows) + 1
        self.rows.append(row)

    def flush(self):
        pass


def setup(tmp_path, monkeypatch, **values):
    region = native(tmp_path)
    article = SimpleNamespace(id=region.article_id, checksum_sha256=region.original_pdf_sha256,
        pdf_original_path=region.original_pdf_path, authors=None, year=None, journal=None, pages=[], chunks=[])
    for field, value in values.items():
        setattr(article, field, value)
    session = Session(article, region)
    monkeypatch.setattr(bridge, 'resolve_article_pdf', lambda *args: SimpleNamespace(path=Path(region.original_pdf_path)))
    monkeypatch.setattr(bridge, 'source_region_from_page', lambda *args, **kw: region)
    return session, article, region


def test_reuses_legacy_exact_results_and_keeps_source_bytes_immutable(tmp_path, monkeypatch):
    session, article, region = setup(tmp_path, monkeypatch)
    before = Path(region.original_pdf_path).read_bytes()
    preview = bridge.preview(session, None, article)
    assert preview['extracted']['authors'] == ['Alice Smith', 'Bob Jones']
    assert preview['extracted']['year'] == 2024
    assert preview['extracted']['journal'] == 'Example Journal'
    assert preview['extracted']['state'] == 'needs_metadata_review' and not preview['scientific_confirmation']
    assert article.authors is None and article.year is None and not session.rows
    assert preview['sources']['regions'] == [region.model_dump(mode='json')]
    for field in bridge.FIELDS:
        for c in preview['extracted']['fields'][field]['candidates']:
            e = c['evidence']
            assert region.page_text[e['start']:e['end']] == e['quote']
            assert e['page_text_sha256'] == region.page_text_sha256
    assert Path(region.original_pdf_path).read_bytes() == before


def test_projection_persists_once_and_repeated_refresh_is_idempotent(tmp_path, monkeypatch):
    session, article, _ = setup(tmp_path, monkeypatch)
    row = bridge.refresh(session, None, article)
    assert article.year == 2024 and article.authors[0] == {'name': 'Alice Smith', 'source': 'tac_file_metadata_v0.1'}
    assert bridge.refresh(session, None, article) is row and len(session.rows) == 1 and session.locks == 2
    assert row.payload_sha256 == text_hash(bridge.canonical(row.payload))
    assert row.payload['projection']['previous_values'] == dict.fromkeys(bridge.FIELDS)
    article.authors[0]['name'] = 'External edit'
    assert row.payload['projection']['after_values']['authors'][0]['name'] == 'Alice Smith'


def test_existing_values_preserved_and_manual_changes_detach_automatic_ownership(tmp_path, monkeypatch):
    session, article, _ = setup(tmp_path, monkeypatch, year=1999, authors=[{'name': 'Existing Author'}])
    first = bridge.refresh(session, None, article)
    assert article.year == 1999 and article.authors == [{'name': 'Existing Author'}]
    assert set(first.payload['projection']['managed_values']) == {'journal'}
    article.journal = 'Manual Journal'
    second = bridge.refresh(session, None, article)
    assert second is not first and article.journal == 'Manual Journal'
    assert not second.payload['projection']['managed_values']
    assert bridge.refresh(session, None, article) is second


@pytest.mark.parametrize('state', ['not_found', 'ambiguous'])
def test_unknown_and_ambiguous_results_do_not_fill_and_clear_only_own_stale_values(state):
    extracted = {f: None for f in bridge.FIELDS}
    extracted['fields'] = {f: {'status': state, 'candidates': [], 'selected': []} for f in bridge.FIELDS}
    current = {'authors': [{'name': 'Old', 'source': 'tac_file_metadata_v0.1'}], 'year': 2020, 'journal': 'Manual'}
    previous = {'projection': {'managed_values': {'authors': current['authors'], 'year': 2020}}}
    result = bridge.projection(current, extracted, previous)
    assert result['after_values'] == {'authors': None, 'year': None, 'journal': 'Manual'}
    assert result['actions']['journal'] == 'existing_value_preserved'
    assert current['year'] == 2020


def test_recorded_provenance_matches_projection_without_claiming_confirmation(tmp_path, monkeypatch):
    session, article, _ = setup(tmp_path, monkeypatch)
    row = bridge.refresh(session, None, article)
    result = bridge.recorded(session, None, article)
    assert result['state'] == 'proposed_not_confirmed' and result['extraction_id'] == str(row.id)
    assert all(result['field_matches_projection'].values()) and not result['scientific_confirmation']


@pytest.mark.parametrize('variant', ['pdf', 'text', 'payload', 'sources'])
def test_corruption_and_source_drift_are_visible(tmp_path, monkeypatch, variant):
    session, article, region = setup(tmp_path, monkeypatch)
    row = bridge.refresh(session, None, article)
    if variant == 'pdf':
        Path(region.original_pdf_path).write_bytes(b'corrupt')
    elif variant == 'text':
        monkeypatch.setattr(bridge, 'source_region_from_page', lambda *a, **kw: region.model_copy(update={'page_text': 'changed'}))
    elif variant == 'payload':
        row.payload['extracted']['year'] = 9999
    else:
        session.pages.append(SimpleNamespace(page_number=2, selected_text_layer='original', text=''))
    with pytest.raises(PdfStorageIntegrityError):
        bridge.recorded(session, None, article)


def test_empty_and_missing_front_pages_remain_explicit_and_no_filename_guess(tmp_path, monkeypatch):
    session, article, _ = setup(tmp_path, monkeypatch)
    session.pages = [SimpleNamespace(page_number=1, selected_text_layer='original', text='')]
    result = bridge.preview(session, None, article)
    assert result['sources']['diagnostics'] == ['empty_registered_front_page:1']
    assert result['extracted']['authors'] is result['extracted']['year'] is None
    session.pages = []
    assert 'registered_first_page_missing' in bridge.preview(session, None, article)['sources']['diagnostics']


def test_legacy_equal_priority_conflict_is_retained():
    from scripts.tac_metadata import candidate, choose
    selected = choose('year', [candidate('year', y, 100, {}, 'constructed') for y in (2023, 2024)])
    assert selected['status'] == 'ambiguous' and selected['value'] is None and len(selected['candidates']) == 2


def test_migration_head_fits_existing_version_column_and_has_provenance_identity():
    # Load from the repository path; installed Alembic owns the top-level module.
    import runpy
    migration = runpy.run_path('alembic/versions/0006_article_metadata_extractions.py')
    assert len(migration['revision']) <= 32 and migration['down_revision'] == '0005_library_sources'
    assert ArticleMetadataExtraction.__table__.c.sequence_no.identity.always
    assert 'payload_sha256' in ArticleMetadataExtraction.__table__.c


def test_duplicate_ingestion_refreshes_metadata_without_rechunking(tmp_path, monkeypatch):
    from app.ingestion import service
    session, article, region = setup(tmp_path, monkeypatch)
    session.scalar = lambda query: article
    metadata = Mock()
    monkeypatch.setattr(service, 'refresh_bibliography', metadata)
    rechunk = Mock(side_effect=AssertionError('Duplicate must not rechunk'))
    monkeypatch.setattr(service, '_replace_article_content', rechunk)
    result = service.process_pdf(session, None, Path(region.original_pdf_path), SimpleNamespace())
    assert result.status == 'duplicate'
    metadata.assert_called_once_with(session, None, article)
    rechunk.assert_not_called()


def test_legacy_failure_is_not_hidden_as_empty_metadata(tmp_path, monkeypatch):
    session, article, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(bridge.tac_metadata, 'extract_article', Mock(side_effect=RuntimeError('legacy failure')))
    with pytest.raises(RuntimeError, match='legacy failure'):
        bridge.refresh(session, None, article)
    assert not session.rows and article.authors is None


def test_refresh_cannot_use_corrupt_history_to_claim_ownership(tmp_path, monkeypatch):
    session, article, _ = setup(tmp_path, monkeypatch)
    row = bridge.refresh(session, None, article)
    row.payload['projection']['managed_values']['year'] = 1999
    article.year = 1999
    with pytest.raises(PdfStorageIntegrityError, match='payload checksum'):
        bridge.refresh(session, None, article)
    assert article.year == 1999 and len(session.rows) == 1
