"""Constructed provenance/gap counterexamples; not independent scientific gold."""

import copy
import json
import socket
from pathlib import Path

import fitz
import pytest

from app.evaluation import evidence_gaps_run as runner
from app.generation.evidence_gaps import document_checklist, in_packet, inventory, search_pages
from app.records.extraction import write_json
from app.records.schema import text_hash
from app.records.sources import file_hash


def page(raw='Sample 2 impedance conductivity in argon at 25 C.'):
    return {'page_ref': 'a:p1', 'article_id': 'a', 'original_pdf_sha256': 'f' * 64,
        'original_pdf_path': str(Path('constructed.pdf').resolve()), 'page_number': 1,
        'text_layer': 'original', 'text_layer_id': 'layer', 'text': raw,
        'blocks': [{'page_start': 0, 'page_end': len(raw), 'bbox': [1, 2, 3, 4]}], 'mapping_diagnostic': None}


def selected(p):
    return {'selected': True, 'node_id': 'constructed-node', 'events': [],
        'source': {k: p[k] for k in ('article_id', 'original_pdf_sha256', 'text_layer', 'text_layer_id')}
        | {'page': p['page_number']}, 'start': 0, 'end': len(p['text']), 'text': p['text']}


def test_exact_unicode_offsets_and_full_context_preserved():
    raw = 'Not DSC; prior work [3]: Naﬁon sample; марсианский реголит.'
    p = page(raw)
    hits = search_pages([p])
    assert hits[0]['text'] == raw
    assert 'not_resolved' in hits[0]['interpretation']
    for spans in inventory(raw, 7).values():
        for span in spans:
            assert raw[span['start'] - 7:span['end'] - 7] == span['text']


@pytest.mark.parametrize('change', ['article', 'pdf', 'layer', 'layer_id', 'text', 'selection', 'range'])
def test_packet_presence_requires_exact_identity_layer_text_and_selection(change):
    p = page()
    row = selected(p)
    hit = search_pages([p])[0]
    assert in_packet(hit, p, [row])
    if change in ('article', 'pdf', 'layer', 'layer_id'):
        key = {'article': 'article_id', 'pdf': 'original_pdf_sha256', 'layer': 'text_layer', 'layer_id': 'text_layer_id'}[change]
        row['source'][key] = 'foreign'
    elif change == 'text':
        row['text'] = 'X' + row['text'][1:]
    elif change == 'selection':
        row['selected'] = False
    else:
        row['end'] -= 1
    assert not in_packet(hit, p, [row])


def test_outside_packet_findings_never_resolve_sample_or_atmosphere_relation():
    p = page('Sample 2 was prepared in argon. Conductivity impedance sample 2; samples 2, 3.')
    hits = search_pages([p])
    for identifier in ('conductivity_protocol', 'preparation_atmosphere'):
        result = document_checklist(identifier, {'article_id': 'a'}, [p], hits, [])
        assert any(r['status'] == 'found_outside_packet' for r in result['requirements'])
        assert result['relation']['status'] == 'relation_unresolved'
        assert not result['relation']['automatically_resolved']


def test_wrong_dsc_article_cannot_satisfy_despite_cues():
    p = page('DSC membrane heating at 25 C.')
    result = document_checklist('dsc_protocol', {'article_id': 'a'}, [p], search_pages([p]), [selected(p)])
    assert {r['status'] for r in result['requirements']} == {'source_identity_unresolved'}


def test_cross_article_cues_do_not_fill_missing_requirements():
    p = page('Sample only.')
    foreign = page('DSC heating sample impedance conductivity.')
    foreign.update(article_id='other', page_ref='other:p1')
    result = document_checklist('conductivity_protocol', {'article_id': 'a'}, [p, foreign], search_pages([p, foreign]), [])
    assert result['requirements'][0]['status'] == 'not_found_in_inspected_scope'


def test_empty_pages_and_uninspected_are_explicit_not_absence_claims():
    p = page('')
    p['mapping_diagnostic'] = 'unproven'
    result = document_checklist('conductivity_protocol', {'article_id': 'a'}, [p], [], [])
    assert result['coverage']['empty_text_pages'] == [1]
    assert result['coverage']['unproven_mapping_pages'] == [1]
    assert result['coverage']['visual_coverage'] == 'not_inspected_by_algorithm'
    assert all('это не отсутствие' in r['gap'] for r in result['requirements'])
    result = document_checklist('conductivity_protocol', {'article_id': 'a'}, [], [], [])
    assert {r['status'] for r in result['requirements']} == {'not_inspected'}


def test_negative_control_cooccurrence_never_becomes_measurement():
    p = page('No conductivity evidence for Nafion with Mars regolith.')
    result = document_checklist('absent_material', {'article_id': 'a'}, [p], search_pages([p]), [selected(p)])
    assert {r['status'] for r in result['requirements']} == {'supported_in_packet'}
    assert result['all_qualifiers_cooccurring_is_not_entailment']
    assert result['relation']['status'] == 'relation_unresolved'


def test_generic_membrane_does_not_satisfy_named_nafion_qualifier():
    p = page('Conductivity of a membrane sample with Mars regolith is not established.')
    result = document_checklist('absent_material', {'article_id': 'a'}, [p], search_pages([p]), [selected(p)])
    nafion = next(r for r in result['requirements'] if r['key'] == 'nafion')
    assert nafion['status'] == 'not_found_in_inspected_scope'


def test_registration_rejects_missing_ambiguous_or_non_byline_identity():
    registration = {'version': 'source_identity_registration_v0.1',
        'anchors': {'title': 'Title', 'authors': 'A. Istomina', 'publication': 'Journal 2021', 'doi': 'doi:1'}}
    raw = 'polymers\nArticle\nTitle\nA. Istomina\nJournal 2021\ndoi:1'
    assert runner.registration_check(registration, raw)['verified']
    assert not runner.registration_check(registration, raw.replace('2021', '2020'))['verified']
    assert not runner.registration_check(registration, raw + '\ndoi:1')['verified']
    assert not runner.registration_check(registration, raw.replace('Title\nA.', 'Title\nOther\nA.'))['verified']


def make_pdf(path, raw):
    with fitz.open() as doc:
        p = doc.new_page()
        p.insert_text((50, 50), raw)
        doc.save(path)
    return runner.extract_pages(path)[0].text


@pytest.fixture
def fixture(tmp_path):
    parent = tmp_path / 'parent'
    parent.mkdir()
    pdf = tmp_path / 'parent.pdf'
    raw = make_pdf(pdf, 'Sample 2 prepared in argon.\nImpedance conductivity; equilibrium.')
    aid = 'constructed-article'
    source = {'article_id': aid, 'original_pdf_path': str(pdf), 'original_pdf_sha256': file_hash(pdf),
        'page_number': 1, 'text_layer': 'original', 'text_layer_id': 'registered-layer', 'page_text_sha256': text_hash(raw)}
    article = {'article_id': aid, 'title': 'Constructed <script> title',
        'proposal': {'sources': {k: source[k] for k in ('article_id', 'original_pdf_path', 'original_pdf_sha256')},
            'projection': {'after_values': {'authors': None, 'journal': None, 'year': None}},
            'extracted': {'fields': {k: {'status': 'unknown'} for k in ('authors', 'journal', 'year')}}},
        'historical_tac': {'sections': []}}
    write_json(parent / 'metadata.json', {'version': 'constructed', 'phase': 'fixture', 'articles': [article], 'summary': {}})
    entries, cases = [], []
    for identifier, question in runner.frozen_questions().items():
        directory = parent / identifier
        directory.mkdir()
        audit_file, identifiers_file = identifier + '/audit.json', identifier + '/identifiers.json'
        write_json(parent / audit_file, {'question': question, 'pages': [{'source': source}]})
        write_json(parent / identifiers_file, {'question': question, 'rows': [], 'blocking_reasons': ['old-refusal'],
            'network_ready': False, 'metrics': {'selected_blocks': 0}, 'selected_binding_states': {}})
        entries.append({'id': identifier, 'audit_file': audit_file, 'identifiers_file': identifiers_file})
        cases.append({'id': identifier, 'blocking_reasons': ['old-refusal']})
    write_json(parent / 'report.json', {'results': entries})
    write_json(parent / 'manifest.json', {'version': 'sample_identifier_audit_v0.1', 'phase': 'offline_sample_identifier_audit',
        'inputs': {str(pdf): file_hash(pdf)}, 'code': {},
        'outputs': {p.relative_to(parent).as_posix(): file_hash(p) for p in sorted(parent.rglob('*')) if p.is_file()}})
    candidate = tmp_path / 'candidate.pdf'
    make_pdf(candidate, 'polymers\nArticle\nTitle\nA. Istomina\nJournal 2021\ndoi:1\nDSC heating membrane at 25 C.')
    registration = tmp_path / 'registration.json'
    write_json(registration, {'version': 'source_identity_registration_v0.1', 'original_pdf_path': str(candidate),
        'original_pdf_sha256': file_hash(candidate),
        'anchors': {'title': 'Title', 'authors': 'A. Istomina', 'publication': 'Journal 2021', 'doi': 'doi:1'}})
    checks = tmp_path / 'checks.json'
    write_json(checks, {'version': 'evidence_gap_checks_v0.1', 'origin': 'exposed_source_development_not_independent_gold',
        'parent_report_sha256': file_hash(parent / 'report.json'), 'questions': runner.frozen_questions(), 'cases': cases})
    return parent, registration, checks


def test_frozen_lifecycle_source_reconstruction_exports_and_html(fixture, tmp_path, monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', lambda *args, **kwargs: pytest.fail('network forbidden'))
    parent, registration, checks = fixture
    prepared, run = tmp_path / 'prepared', tmp_path / 'run'
    runner.prepare(parent, registration, checks, prepared)
    summary = runner.execute(prepared, run)
    assert summary['identity_verified']
    assert summary['scientific_relations_established'] == 0
    assert summary['checks_passed'] == 4
    assert summary['questions'] == 4
    report = runner.read(run / 'report.json')
    assert report['results'][-1]['purpose'] == 'negative_control_not_reported_measurement'
    html = (run / 'review.html').read_text(encoding='utf-8')
    assert 'Constructed &lt;script&gt; title' in html
    assert 'Constructed <script> title' not in html
    assert html.count('<article data-query>') == 4
    metadata = (run / 'metadata_review.html').read_text(encoding='utf-8')
    assert metadata.count('<tr data-article') == 2
    assert '<th>Terms</th>' in metadata
    assert (run / 'metadata.json').read_bytes() == (parent / 'metadata.json').read_bytes()
    assert (run / 'baseline/manifest.json').read_bytes() == (parent / 'manifest.json').read_bytes()
    exports = [tmp_path / 'export1', tmp_path / 'export2']
    for directory in exports:
        runner.execute(run, directory, export=True)
    left = {p.relative_to(exports[0]).as_posix(): p.read_bytes() for p in exports[0].rglob('*') if p.is_file()}
    right = {p.relative_to(exports[1]).as_posix(): p.read_bytes() for p in exports[1].rglob('*') if p.is_file()}
    assert left == right
    with pytest.raises(FileExistsError):
        runner.execute(prepared, run)
    (run / 'hits.json').write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(run, tmp_path / 'badexport', export=True)


def test_pdf_drift_and_historical_text_drift_fail_loud(fixture, tmp_path):
    parent, registration, checks = fixture
    prepared = tmp_path / 'prepared'
    runner.prepare(parent, registration, checks, prepared)
    plan = runner.read(prepared / 'plan.json')
    registered = copy.deepcopy(plan['registered_pages'])
    next(iter(registered.values()))['page_text_sha256'] = 'bad'
    with pytest.raises(ValueError, match='Historical page text'):
        runner.capture(plan['documents'], registered)
    source = Path(plan['documents'][0]['original_pdf_path'])
    source.write_bytes(source.read_bytes() + b'\nchanged\n')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(prepared, tmp_path / 'run')


def test_reference_and_scope_drift_rejected(fixture, tmp_path):
    parent, registration, checks = fixture
    data = json.loads(checks.read_bytes())
    data['questions']['dsc_protocol'] = 'changed'
    checks.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='checks differ'):
        runner.prepare(parent, registration, checks, tmp_path / 'prepared')
