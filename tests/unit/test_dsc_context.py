"""Constructed DSC packet integrity tests; no independent scientific gold."""

import copy
import json
import socket
from pathlib import Path
from uuid import UUID

import fitz
import pytest

from app.evaluation import dsc_context_run as runner
from app.evaluation.evidence_gaps_run import capture, registration_check
from app.records.extraction import write_json
from app.records.sources import file_hash


@pytest.fixture
def parent(tmp_path):
    pdf = tmp_path / 'source.pdf'
    header = 'polymers\nArticle\nTitle\nA. Istomina\nJournal 2021\ndoi:1\nAbstract: unrelated context.'
    method = (runner.START + '\nThe samples were investigated using DSC 214 Polyma.\n'
        'Dry nitrogen flow 40 mL/min. Heating 50 C; cooling -150 C.\n' + runner.END
        + '\nWAXD conditions must not be borrowed.\n2.6. AC Conductivity Measurements\nUnrelated impedance conditions.')
    with fitz.open() as doc:
        for raw in (header, 'Page two', 'Page three', method):
            page = doc.new_page()
            page.insert_text((40, 40), raw)
        doc.save(pdf)
    aid = str(UUID(int=1))
    document = {'article_id': aid, 'original_pdf_path': str(pdf), 'original_pdf_sha256': file_hash(pdf),
        'scope': 'separate_candidate_supplement', 'requested_identity_verified': True, 'title': 'Title'}
    pages = capture([document], {})
    registration = {'version': 'source_identity_registration_v0.1', 'original_pdf_path': str(pdf),
        'original_pdf_sha256': file_hash(pdf),
        'anchors': {'title': 'Title', 'authors': 'A. Istomina', 'publication': 'Journal 2021', 'doi': 'doi:1'}}
    document['identity'] = registration_check(registration, pages[0]['text'])
    assert document['identity']['verified']
    root = tmp_path / 'parent'
    root.mkdir()
    write_json(root / 'plan.json', {'registration': registration})
    write_json(root / 'source_pages.json', pages)
    write_json(root / 'report.json', {'documents': [document], 'results': [{'id': 'dsc_protocol',
        'question': runner.frozen_questions()['dsc_protocol'], 'blocking_reasons': ['historical-refusal']}]})
    write_json(root / 'manifest.json', {'version': runner.PARENT_VERSION, 'phase': 'offline_evidence_gap_audit',
        'inputs': {str(pdf): file_hash(pdf)}, 'code': {},
        'outputs': {p.name: file_hash(p) for p in root.iterdir() if p.is_file()}})
    return root


def test_full_section_and_identity_roles_exact_without_neighbor_conditions(parent):
    plan, _ = runner.load_source(parent)
    wire, sources, report = runner.build(plan)
    assert len(sources) == len(wire['contexts']) == 5
    assert [c['citation_id'] for c in wire['contexts']] == ['B1', 'B2', 'B3', 'B4', 'M1']
    assert wire['contexts'][-1]['text'].startswith(runner.START + '\n')
    assert runner.END not in wire['contexts'][-1]['text']
    assert 'AC Conductivity' not in wire['contexts'][-1]['text']
    assert wire['contexts'][-1]['text'].endswith('cooling -150 C.\n')
    assert str(parent) not in runner.wire_text(wire)
    assert report['historical_blocking_reasons'] == ['historical-refusal']
    assert not report['summary']['network_ready']
    assert report['summary']['admission'] == 'not_evaluated_in_source_packet_stage'


@pytest.mark.parametrize('raw', [runner.START, runner.END + '\n' + runner.START,
    runner.START + '\nDSC\n' + runner.END + '\n' + runner.END, runner.START + 'DSC\n' + runner.END])
def test_missing_ambiguous_or_reordered_headings_fail(raw):
    with pytest.raises(ValueError, match='heading'):
        runner.section_span(raw)


@pytest.mark.parametrize('kind', ['question', 'article', 'hash', 'missing_anchor', 'quote'])
def test_source_question_or_header_drift_fail(parent, kind):
    plan, _ = runner.load_source(parent)
    if kind == 'question':
        plan['question'] = 'different question'
    elif kind == 'article':
        plan['pages'][1]['article_id'] = str(UUID(int=2))
    elif kind == 'hash':
        plan['pages'][1]['text_sha256'] = 'changed'
    elif kind == 'missing_anchor':
        del plan['identity']['spans']['doi']
    else:
        plan['identity']['spans']['title']['text'] = 'modified title'
    with pytest.raises(ValueError):
        runner.build(plan)


@pytest.mark.parametrize('field', ['text', 'start', 'page_number', 'text_layer_id', 'original_pdf_sha256'])
def test_wire_context_cannot_diverge_from_registered_source(parent, field):
    plan, _ = runner.load_source(parent)
    wire, sources, _ = runner.build(plan)
    context = wire['contexts'][-1]
    context[field] = 'foreign' if isinstance(context[field], str) else context[field] + 1
    with pytest.raises(ValueError, match='exact registered source'):
        runner.guard_wire(wire, sources, plan['pages'])


def test_registry_layer_and_whole_section_checks(parent):
    plan, _ = runner.load_source(parent)
    wire, sources, _ = runner.build(plan)
    pages = copy.deepcopy(plan['pages'])
    pages[1]['text_layer_id'] = str(UUID(int=222))
    with pytest.raises(ValueError, match='captured page'):
        runner.guard_wire(wire, sources, pages)
    method_page = plan['pages'][1]
    short = runner.region(method_page, sources[-1].start, sources[-1].end - 5)
    sources[-1] = short
    wire['contexts'][-1].update(region_id=short.region_id, end=short.end, text=short.quote)
    with pytest.raises(ValueError, match='complete bounded section'):
        runner.guard_wire(wire, sources, plan['pages'])


def test_full_page_union_and_byte_guards(parent, monkeypatch):
    plan, _ = runner.load_source(parent)
    wire, sources, _ = runner.build(plan)
    first = plan['pages'][0]
    length = len(first['text'])
    bounds = [0, length // 4, length // 2, 3 * length // 4, length]
    for i in range(4):
        source = runner.region(first, bounds[i], bounds[i + 1])
        sources[i] = source
        wire['contexts'][i].update(region_id=source.region_id, start=source.start, end=source.end, text=source.quote)
    with pytest.raises(ValueError, match='complete page|complete source pages'):
        runner.guard_wire(wire, sources, plan['pages'])
    monkeypatch.setattr(runner, 'MAX_BYTES', 10)
    with pytest.raises(ValueError, match='byte ceiling'):
        runner.build(plan)


def test_frozen_lifecycle_exports_no_network_html_and_source_drift(parent, tmp_path, monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **kw: pytest.fail('Network forbidden'))
    prepared, run = tmp_path / 'prepared', tmp_path / 'run'
    runner.prepare(parent, prepared)
    summary = runner.execute(prepared, run)
    assert (run / 'wire.json').stat().st_size == summary['wire_bytes']
    assert summary['exact_region_checks'] == 5
    assert summary['methods_contexts'] == 1
    html = (run / 'review.html').read_text(encoding='utf-8')
    assert html.count('<tr data-context>') == 5
    metadata = (run / 'metadata_review.html').read_text(encoding='utf-8')
    assert metadata.count('<th>') == 8
    assert metadata.count('<tr data-article>') == 1
    outputs = [tmp_path / 'export1', tmp_path / 'export2']
    for directory in outputs:
        runner.execute(run, directory, export=True)
    assert {p.name: p.read_bytes() for p in outputs[0].iterdir()} == {p.name: p.read_bytes() for p in outputs[1].iterdir()}
    with pytest.raises(FileExistsError):
        runner.execute(prepared, run)
    plan = runner.read(prepared / 'plan.json')
    pdf = Path(plan['document']['original_pdf_path'])
    pdf.write_bytes(pdf.read_bytes() + b'\nmodified\n')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(run, tmp_path / 'badexport', export=True)


def test_html_escapes_source_markup_and_wire_tampering_rejected(parent, tmp_path):
    plan, _ = runner.load_source(parent)
    wire, sources, report = runner.build(plan)
    wire['question'] = '<script>alert(1)</script>'
    rendered = runner.render(wire, sources, report)
    assert '&lt;script&gt;' in rendered
    assert '<script>alert(1)</script>' not in rendered
    prepared, run = tmp_path / 'prepared', tmp_path / 'run'
    runner.prepare(parent, prepared)
    runner.execute(prepared, run)
    altered = json.loads((run / 'wire.json').read_bytes())
    altered['contexts'][-1]['text'] = 'modified'
    (run / 'wire.json').write_text(json.dumps(altered), encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(run, tmp_path / 'badexport', export=True)
