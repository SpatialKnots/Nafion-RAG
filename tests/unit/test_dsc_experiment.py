"""Constructed Responses fixtures only; no provider run or scientific gold."""

import copy
import hashlib
import json
import socket
from uuid import UUID

import fitz
import pytest

from app.evaluation import dsc_admission_run as admission_run
from app.evaluation import dsc_context_run as context
from app.evaluation import dsc_experiment_run as runner
from app.evaluation.evidence_gaps_run import capture, registration_check
from app.generation import dsc_experiment as policy
from app.records.extraction import write_json
from app.records.sources import file_hash
from tests.unit.test_dsc_admission import BODY, HEADER, registration, source_plan


def inputs():
    plan = source_plan()
    wire, sources, _ = context.build(plan)
    return plan, wire, sources


def reply(wire, present=6):
    outcome = 'answer_proposal' if present == 6 else 'partial_proposal' if present else 'abstention'
    return {'outcome': outcome, 'fields': [{'topic': topic, 'status': 'present' if i < present else 'unsupported',
        'evidence': [{'citation_id': 'M1', 'quote': wire['contexts'][-1]['text']}] if i < present else [],
        'diagnostic': 'Constructed proposal, not a scientific finding.'} for i, topic in enumerate(policy.TOPICS)],
        'diagnostic': 'Constructed test only.'}


def envelope(value, **extra):
    return json.dumps({'status': 'completed', 'model': 'constructed-model-not-provider', 'id': 'constructed-response',
        'usage': {'fixture_tokens': 7}, 'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
            'content': [{'type': 'output_text', 'text': json.dumps(value, ensure_ascii=False)}]}], **extra},
        ensure_ascii=False).encode('utf-8')


def test_contract_budget_full_envelope_and_zero_execution():
    plan, wire, sources = inputs()
    frozen = policy.contract(wire, sources, plan)
    assert frozen['budget']['maximum_transport_attempts'] == 1
    assert frozen['budget']['automatic_retries'] == frozen['budget']['model_fallbacks'] == 0
    assert frozen['budget']['max_output_tokens_per_attempt'] == 4096
    assert frozen['budget']['timeout_seconds'] == 180
    assert frozen['budget']['estimated_cost_usd'] is None
    raw = policy.payload(policy.request(wire))
    assert frozen['request_bytes'] == len(raw)
    assert frozen['request_sha256'] == hashlib.sha256(raw).hexdigest()
    assert plan['pages'][0]['original_pdf_path'] not in raw.decode('utf-8')
    assert not frozen['execution']['network_ready']
    assert frozen['provider_compatibility'] == 'not_live_verified'
    assert policy.result_template()['usage'] is None


@pytest.mark.parametrize('field', ['model', 'input', 'max_output_tokens', 'text', 'store', 'truncation'])
def test_changed_model_prompt_source_schema_or_settings_are_rejected(field):
    plan, wire, sources = inputs()
    modified = policy.request(wire)
    modified[field] = 'changed'
    with pytest.raises(ValueError, match='differs from frozen'):
        policy.guard_request(policy.payload(modified), wire, sources, plan)


def test_actual_provider_envelope_byte_ceiling(monkeypatch):
    plan, wire, sources = inputs()
    monkeypatch.setattr(policy, 'MAX_BYTES', 10)
    with pytest.raises(ValueError, match='envelope exceeds'):
        policy.guard_request(policy.payload(policy.request(wire)), wire, sources, plan)


@pytest.mark.parametrize('present', [0, 2, 6])
def test_complete_partial_and_abstention_keep_source_and_usage(present):
    _, wire, sources = inputs()
    result = policy.inspect_response(envelope(reply(wire, present)), wire, sources)
    assert result['evaluation']['scientific_acceptance'] == 'not_evaluated'
    assert result['metadata']['usage'] == {'fixture_tokens': 7}
    assert len(result['resolved']) == 6
    for field in result['resolved']:
        for evidence in field['evidence']:
            source = next(s for s in sources if s.region_id == evidence['region_id'])
            assert source.page_text[evidence['start']:evidence['end']] == evidence['quote']


@pytest.mark.parametrize('kind', ['missing_topic', 'duplicate_topic', 'inconsistent_outcome', 'nonpresent_evidence',
    'foreign_citation', 'bibliography', 'invented_quote', 'ambiguous_quote', 'duplicate_quote', 'whitespace'])
def test_invalid_reply_or_unsupported_evidence_fails(kind):
    _, wire, sources = inputs()
    value = reply(wire)
    item = value['fields'][0]
    if kind == 'missing_topic':
        value['fields'].pop()
    elif kind == 'duplicate_topic':
        value['fields'][-1]['topic'] = item['topic']
    elif kind == 'inconsistent_outcome':
        value['outcome'] = 'abstention'
    elif kind == 'nonpresent_evidence':
        item['status'] = 'unsupported'
    elif kind in ('foreign_citation', 'bibliography'):
        item['evidence'][0]['citation_id'] = 'foreign' if kind == 'foreign_citation' else 'B1'
    elif kind == 'invented_quote':
        item['evidence'][0]['quote'] = 'not in source'
    elif kind == 'ambiguous_quote':
        item['evidence'][0]['quote'] = 'heating'
    elif kind == 'duplicate_quote':
        item['evidence'].append(copy.deepcopy(item['evidence'][0]))
    else:
        item['evidence'][0]['quote'] = ' \n'
    with pytest.raises(ValueError):
        policy.inspect_response(envelope(value), wire, sources)


def test_duplicate_json_keys_and_incomplete_envelopes_fail():
    _, wire, sources = inputs()
    with pytest.raises(ValueError, match='Duplicate'):
        policy.parse_reply('{"outcome":"abstention","outcome":"answer_proposal"}')
    with pytest.raises(ValueError, match='Duplicate'):
        policy.inspect_response(b'{"status":"completed","status":"incomplete"}', wire, sources)
    with pytest.raises(ValueError, match='not successfully completed'):
        policy.inspect_response(envelope(reply(wire), status='incomplete'), wire, sources)


@pytest.fixture
def admission(tmp_path):
    pdf = tmp_path / 'source.pdf'
    method = context.START + '\n' + BODY + context.END + '\nUnrelated WAXD source.'
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
    context.prepare(stage46, tmp_path / 'context-prepared')
    context.execute(tmp_path / 'context-prepared', tmp_path / 'context-run')
    admission_run.prepare(tmp_path / 'context-run', tmp_path / 'admission-prepared')
    admission_run.execute(tmp_path / 'admission-prepared', tmp_path / 'admission-run')
    return tmp_path / 'admission-run'


def test_frozen_lifecycle_and_offline_inspection_preserve_raw_errors_and_usage(admission, tmp_path, monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **kw: pytest.fail('Network forbidden'))
    prepared, run = tmp_path / 'prepared', tmp_path / 'run'
    runner.prepare(admission, prepared)
    summary = runner.execute(prepared, run)
    assert summary['model_calls'] == 0 and not summary['network_ready']
    assert not (run / 'response.bin').exists()
    assert context.read(run / 'result_template.json')['status'] == 'not_executed'
    outputs = [tmp_path / 'export1', tmp_path / 'export2']
    for target in outputs:
        runner.execute(run, target, export=True)
    assert {p.relative_to(outputs[0]): p.read_bytes() for p in outputs[0].rglob('*') if p.is_file()} == {
        p.relative_to(outputs[1]): p.read_bytes() for p in outputs[1].rglob('*') if p.is_file()}
    wire = context.read(admission / 'packet/wire.json')
    raw = envelope(reply(wire))
    response = tmp_path / 'constructed-response.bin'
    response.write_bytes(raw)
    result = runner.inspect_offline(run, response, tmp_path / 'inspection')
    assert result['origin'] == 'offline_supplied_response'
    assert result['status'] == 'offline_integrity_valid'
    assert result['model_calls_by_this_tool'] == 0
    assert (tmp_path / 'inspection/response.bin').read_bytes() == raw
    assert context.read(tmp_path / 'inspection/response_metadata.json')['usage'] == {'fixture_tokens': 7}
    response.write_bytes(b'\xffmalformed bytes')
    result = runner.inspect_offline(run, response, tmp_path / 'invalid-inspection')
    assert result['status'] == 'offline_response_invalid'
    assert (tmp_path / 'invalid-inspection/response.bin').read_bytes() == response.read_bytes()
    assert context.read(tmp_path / 'invalid-inspection/response_metadata.json') == {}
    assert not (tmp_path / 'invalid-inspection/reply.json').exists()
    with pytest.raises(ValueError, match='inside the frozen'):
        runner.inspect_offline(run, response, run / 'new-inspection')
    with pytest.raises(FileExistsError):
        runner.execute(prepared, run)
    (run / 'request.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(run, tmp_path / 'bad-export', export=True)


def test_frozen_contract_budget_and_html_escaping(admission, tmp_path):
    prepared = tmp_path / 'prepared'
    runner.prepare(admission, prepared)
    value = context.read(prepared / 'contract.json')
    report = {'request': {}, 'summary': {}}
    value['question'] = '<script>alert(1)</script>'
    rendered = runner.render(value, report, {})
    assert '&lt;script&gt;' in rendered and '<script>alert(1)</script>' not in rendered
    value['budget']['maximum_transport_attempts'] = 2
    (prepared / 'contract.json').write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='changed'):
        runner.execute(prepared, tmp_path / 'run')
