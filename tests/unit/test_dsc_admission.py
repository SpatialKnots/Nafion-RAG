"""Constructed source-admission counterexamples, not independent scientific gold."""

import copy
import json
import socket
from pathlib import Path
from uuid import UUID

import fitz
import pytest

from app.evaluation import dsc_admission_run as runner
from app.evaluation import dsc_context_run as context
from app.evaluation.evidence_gaps_run import capture, registration_check
from app.generation.dsc_admission import assess
from app.records.extraction import write_json
from app.records.schema import text_hash
from app.records.sources import file_hash

HEADER = 'polymers\nArticle\nTitle\nA. Istomina\nJournal 2021\ndoi:1\nAbstract contains DSC, not the source method.\nOther introduction.'
BODY = ('The samples were investigated using a DSC 214 Polyma\ndifferential scanning calorimeter.\n'
    'The measurements were performed under dry nitrogen flow within\na temperature range from -150 to 300 C.\n'
    'The following temperature programme was used:\nheating to 50 C; cooling to -150 C; heating to 300 C.\n')


def registration():
    return {'version': 'source_identity_registration_v0.1',
        'anchors': {'title': 'Title', 'authors': 'A. Istomina', 'publication': 'Journal 2021', 'doi': 'doi:1'}}


def source_plan(body=BODY):
    path = str(Path('constructed.pdf').resolve())
    aid = str(UUID(int=1))
    document = {'article_id': aid, 'original_pdf_path': path, 'original_pdf_sha256': 'a' * 64}
    pages = []
    method = context.START + '\n' + body + context.END + '\nAdjacent unrelated WAXD source.'
    for number, raw in ((1, HEADER), (4, method)):
        pages.append({**document, 'page_ref': f'{aid}:p{number}', 'page_number': number, 'text_layer': 'original',
            'text_layer_id': str(UUID(int=number + 10)), 'text': raw, 'text_sha256': text_hash(raw),
            'layer_pdf_path': path, 'layer_pdf_sha256': 'a' * 64, 'mapping_diagnostic': None,
            'blocks': [{'page_start': 0, 'page_end': len(raw), 'bbox': [0, 0, 100, 200]}]})
    start, end = context.section_span(method)
    return {'parent': 'constructed-parent', 'document': document, 'pages': pages,
        'identity': registration_check(registration(), HEADER), 'question': context.frozen_questions()['dsc_protocol'],
        'expected_methods_sha256': text_hash(method[start:end]),
        'source_expectation_origin': 'constructed_test_not_gold', 'historical_blocking_reasons': ['old-missing-context', 'old-byte-limit']}


def assessment(plan=None):
    plan = plan or source_plan()
    wire, sources, _ = context.build(plan)
    return assess(wire, sources, plan), wire, sources, plan


def test_new_source_admitted_unknowns_retained_and_network_still_prohibited():
    report, _, _, plan = assessment()
    assert report['source_packet_eligible_for_frozen_experiment']
    assert report['current_source_blocking_reasons'] == []
    assert report['historical_blocking_reasons'] == plan['historical_blocking_reasons']
    assert not report['execution']['network_ready']
    assert not report['execution']['api_calls_authorized']
    assert len(report['execution']['blocking_reasons']) == 3
    assert report['scientific_acceptance'] == 'not_evaluated'


@pytest.mark.parametrize('question', [
    'For Other 2021, what conditions and temperature programme were used for DSC measurements?',
    'For Istomina 2020, what conditions and temperature programme were used for DSC measurements?',
    'What conductivity was reported for Nafion membranes containing Mars regolith?',
])
def test_wrong_author_year_and_negative_control_are_not_upgraded(question):
    _, wire, sources, plan = assessment()
    wire['question'] = question
    result = assess(wire, sources, plan)
    assert not result['source_packet_eligible_for_frozen_experiment']
    assert 'necessary_query_mentions' in result['current_source_blocking_reasons']
    assert not result['execution']['network_ready']


def test_author_in_title_or_body_cannot_replace_byline_identity():
    _, wire, sources, plan = assessment()
    wire['contexts'][1]['role'] = 'bibliographic_title'
    result = assess(wire, sources, plan)
    assert not result['source_packet_eligible_for_frozen_experiment']
    assert 'bound_header_identity' in result['current_source_blocking_reasons']
    qualifier = next(c for c in result['checks'] if c['id'] == 'necessary_query_mentions')
    assert qualifier['evidence']['qualifiers'][0]['state'] == 'not_established'


@pytest.mark.parametrize(('old', 'new', 'reason'), [
    ('DSC 214 Polyma', 'other instrument', 'dsc_instrument'),
    ('measurements were performed under', 'preparation was performed under', 'measurement_environment'),
    ('temperature range from', 'other range from', 'measurement_temperature_range'),
    ('temperature programme was used:', 'different procedure:', 'temperature_programme'),
    ('cooling to -150 C', 'heating to -150 C', 'programme_action_order'),
])
def test_conditions_and_method_require_the_actual_methods_context(old, new, reason):
    plan = source_plan(BODY.replace(old, new))
    result, _, _, _ = assessment(plan)
    assert not result['source_packet_eligible_for_frozen_experiment']
    assert reason in result['current_source_blocking_reasons']


def test_dsc_in_abstract_cannot_supply_missing_methods_mention():
    result, _, _, _ = assessment(source_plan(BODY.replace('DSC 214 Polyma', 'unrelated instrument')))
    assert not result['source_packet_eligible_for_frozen_experiment']
    qualifier = next(c for c in result['checks'] if c['id'] == 'necessary_query_mentions')
    method = next(q for q in qualifier['evidence']['qualifiers'] if q['qualifier_kind'] == 'method_or_property_mention')
    assert method['state'] == 'not_established'


def test_source_mapping_and_unknown_promotion_fail_closed():
    _, wire, sources, plan = assessment()
    wire['unknowns']['per_result_applicability'] = 'established'
    plan['pages'][1]['mapping_diagnostic'] = 'unproven'
    result = assess(wire, sources, plan)
    assert not result['source_packet_eligible_for_frozen_experiment']
    assert {'unknowns_preserved', 'source_context_boundaries'} <= set(result['current_source_blocking_reasons'])


def test_every_reported_match_is_an_exact_registered_source_span():
    report, _, sources, _ = assessment()
    registry = {s.region_id: s for s in sources}
    for check in report['checks']:
        if isinstance(check['evidence'], dict):
            for span in check['evidence'].get('source_spans', []):
                source = registry[span['region_id']]
                assert source.page_text[span['start']:span['end']] == span['text']
            for qualifier in check['evidence'].get('qualifiers', []):
                for span in qualifier['source_spans']:
                    source = registry[span['region_id']]
                    assert source.page_text[span['start']:span['end']] == span['text']


def test_malformed_source_and_actual_byte_limit_raise_without_hiding_failure(monkeypatch):
    _, wire, sources, plan = assessment()
    bad = copy.deepcopy(wire)
    bad['contexts'][-1]['text'] = 'truncated'
    with pytest.raises(ValueError, match='exact registered source'):
        assess(bad, sources, plan)
    monkeypatch.setattr(context, 'MAX_BYTES', 10)
    with pytest.raises(ValueError, match='byte ceiling'):
        assess(wire, sources, plan)


@pytest.fixture
def packet(tmp_path):
    pdf = tmp_path / 'source.pdf'
    method = context.START + '\n' + BODY + context.END + '\nAdjacent WAXD methods.'
    with fitz.open() as document:
        for raw in (HEADER, 'Other page', 'Another page', method):
            page = document.new_page()
            page.insert_text((40, 40), raw)
        document.save(pdf)
    source = {'article_id': str(UUID(int=1)), 'original_pdf_path': str(pdf), 'original_pdf_sha256': file_hash(pdf),
        'scope': 'separate_candidate_supplement', 'requested_identity_verified': True, 'title': 'Constructed source'}
    pages = capture([source], {})
    source['identity'] = registration_check(registration(), pages[0]['text'])
    stage46 = tmp_path / 'stage46'
    stage46.mkdir()
    write_json(stage46 / 'plan.json', {'registration': registration()})
    write_json(stage46 / 'source_pages.json', pages)
    write_json(stage46 / 'report.json', {'documents': [source], 'results': [{'id': 'dsc_protocol',
        'question': context.frozen_questions()['dsc_protocol'], 'blocking_reasons': ['old-refusal']}]})
    write_json(stage46 / 'manifest.json', {'version': context.PARENT_VERSION, 'phase': 'offline_evidence_gap_audit',
        'inputs': {str(pdf): file_hash(pdf)}, 'code': {},
        'outputs': {p.name: file_hash(p) for p in stage46.iterdir() if p.is_file()}})
    prepared, run = tmp_path / 'context-prepared', tmp_path / 'context-run'
    context.prepare(stage46, prepared)
    context.execute(prepared, run)
    return run


def test_frozen_run_exports_parent_preservation_and_drift(packet, tmp_path, monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **kw: pytest.fail('Network forbidden'))
    prepared, run = tmp_path / 'prepared', tmp_path / 'run'
    runner.prepare(packet, prepared)
    summary = runner.execute(prepared, run)
    report = context.read(run / 'report.json')
    assert report['source_packet_eligible_for_frozen_experiment']
    assert summary['source_checks'] == summary['source_checks_passed']
    assert summary['development_checks_passed'] == 3
    for p in packet.iterdir():
        assert p.read_bytes() == (run / 'packet' / p.name).read_bytes()
    html = (run / 'review.html').read_text(encoding='utf-8')
    assert html.count('<tr data-check>') == summary['source_checks']
    assert 'network_ready=false' in html
    exports = [tmp_path / 'export1', tmp_path / 'export2']
    for directory in exports:
        runner.execute(run, directory, export=True)
    assert {p.relative_to(exports[0]): p.read_bytes() for p in exports[0].rglob('*') if p.is_file()} == {
        p.relative_to(exports[1]): p.read_bytes() for p in exports[1].rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        runner.execute(prepared, run)
    (packet / 'wire.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(run, tmp_path / 'bad-export', export=True)


def test_report_escaping_and_code_or_output_drift_fail(packet, tmp_path):
    prepared, run = tmp_path / 'prepared', tmp_path / 'run'
    runner.prepare(packet, prepared)
    runner.execute(prepared, run)
    report = context.read(run / 'report.json')
    report['question'] = '<script>alert(1)</script>'
    html = runner.render(report)
    assert '&lt;script&gt;' in html and '<script>alert(1)</script>' not in html
    (run / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(run, tmp_path / 'bad-export', export=True)
