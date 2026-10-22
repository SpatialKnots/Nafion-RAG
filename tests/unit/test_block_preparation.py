"""Constructed whole-block preservation and API checks; not scientific answer references."""

import copy
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import fitz
import pytest

from app.evaluation.block_run import read_archived
from app.generation import block_routes as routes
from app.generation.block_context import VERSION, build_block_context, full_coverage, page_plan
from app.generation.preparation import VERSION as BASELINE_VERSION
from app.generation.providers import Evidence
from app.records.article_windows import plan_page
from app.records.schema import source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_answer_preparation import client as preparation_client_fixture
from tests.unit.test_record_article_windows import group, page_fixture

client = preparation_client_fixture

def fixture(tmp_path, blocks=None, question='Conductivity?', baseline_allowed=True, protected=None):
    blocks = blocks or ['Background zero.\n', 'Background one.\n', 'Background two.\n',
                        'Conductivity was measured.\n', 'Background four.\n', 'Background five.\n', 'Background six.\n']
    region, mapping = page_fixture(tmp_path, blocks)
    item = Evidence('E1', str(region.article_id), str(UUID(int=60)), 'Constructed <script> title', None, 1, 1,
                    'body', region.page_text, 1.0, 'constructed', {}, {})
    baseline = {'version': BASELINE_VERSION, 'question': question, 'evidence': [asdict(item)],
        'baseline_allowed': baseline_allowed, 'generation_performed': False, 'external_request_constructed': False,
        'blocking_reasons': ['complete_source_pages_retained'] + ([] if baseline_allowed else ['baseline_insufficient_evidence']),
        'sources': {'pages': {'page': region.model_dump(mode='json')}, 'chunk_layers': {item.chunk_id: region.text_layer}},
        'article_metadata': {item.article_id: {'authors': None, 'year': None}}}
    plan = plan_page(region, mapping, [group(mapping, protected)] if protected else [])
    plan.update(source_gaps={'assets': [], 'diagnostics': []}, layout_diagnostics=[], table_diagnostics=[])
    return baseline, {region.region_id: plan}, region


def test_exact_whole_block_neighbors_preserve_baseline_and_unselected_unknown_text(tmp_path):
    baseline, plans, region = fixture(tmp_path)
    original = copy.deepcopy((baseline, plans))
    result = build_block_context(baseline, plans)
    assert result['technical_checks_passed'] and not result['network_ready']
    assert not result['generation_performed'] and not result['external_request_constructed']
    assert result['baseline'] == baseline and (baseline, plans) == original
    assert len(result['proposals']) == 1
    p = result['proposals'][0]
    assert p['source']['quote'] == 'Background two.\nConductivity was measured.\nBackground four.\n'
    assert region.page_text[p['source']['start']:p['source']['end']] == p['source']['quote']
    assert result['pages'][0]['blocks'][0]['state'] == 'not_selected_retained_in_baseline'
    assert result['wire']['evidence'][0]['citation_id'] == 'B1'
    assert region.original_pdf_path not in json.dumps(result['wire'])


def test_actual_pdf_geometry_is_read_without_replacing_text_or_modifying_pdf(tmp_path):
    baseline, _, template = fixture(tmp_path)
    path = tmp_path / 'native_blocks.pdf'
    document = fitz.open()
    page = document.new_page()
    for i in range(7):
        page.insert_text((40, 40 + i * 50), 'Conductivity was measured.' if i == 3 else f'Background item {i}.')
    document.save(path)
    document.close()
    checksum = file_hash(path)
    with fitz.open(path) as document:
        text = document[0].get_text('text')
    data = template.model_dump()
    data.update(original_pdf_path=str(path), layer_pdf_path=str(path), original_pdf_sha256=checksum,
                layer_pdf_sha256=checksum, page_text=text, page_text_sha256=text_hash(text), quote=text,
                quote_sha256=text_hash(text), start=0, end=len(text))
    data['region_id'] = source_identity(data)
    region = type(template).model_validate(data)
    baseline['sources']['pages'] = {'page': region.model_dump(mode='json')}
    baseline['evidence'][0]['text'] = text
    planned = page_plan(region)
    assert len(planned['mapping']['blocks']) == 7
    result = build_block_context(baseline)
    assert result['technical_checks_passed'] and result['proposals']
    assert file_hash(path) == checksum


def test_conditions_guards_and_incomplete_tail_are_retained_without_scientific_repair(tmp_path):
    blocks = ['Background zero.\n', 'Background one.\n', 'Conductivity was not measured [12].\n',
              'Background three.\n', 'Measurements were performed at 25 °C.\n', 'Unfinished qualifier']
    baseline, plans, region = fixture(tmp_path, blocks)
    result = build_block_context(baseline, plans)
    states = result['pages'][0]['blocks']
    assert 'negation_reported_work_or_modality_guard' in states[2]['retention_reasons']
    assert 'finite_condition_or_method_cue' in states[4]['retention_reasons']
    assert 'unproven_sentence_boundary' in states[5]['retention_reasons']
    assert all(states[i]['state'] == 'included_in_candidate' for i in [2, 4, 5])
    for b in states:
        for hit in b['anchor_hits']:
            assert region.page_text[hit['start']:hit['end']] == hit['text']


@pytest.mark.parametrize('through_json', [False, True])
def test_protected_group_is_never_cut_when_core_or_neighbors_overlap_it(tmp_path, through_json):
    baseline, plans, _ = fixture(tmp_path, protected=[2, 3, 4])
    if through_json:
        plans = json.loads(json.dumps(plans))
    result = build_block_context(baseline, plans)
    p = result['proposals'][0]
    blocks = result['pages'][0]['blocks']
    assert p['source']['start'] <= blocks[2]['start'] and p['source']['end'] >= blocks[4]['end']


@pytest.mark.parametrize('variant', ['table', 'visual', 'visual_diagnostic', 'partial_baseline'])
def test_unknown_structure_or_incomplete_page_binding_defers_page_without_deleting_it(tmp_path, variant):
    blocks = None if variant != 'table' else ['Background.\n', 'Table 1. Conductivity values\n', 'Unresolved rows.\n']
    baseline, plans, _ = fixture(tmp_path, blocks)
    plan = next(iter(plans.values()))
    if variant == 'visual':
        plan['source_gaps']['assets'] = [{'kind': 'constructed_image'}]
    elif variant == 'visual_diagnostic':
        plan['source_gaps']['diagnostics'] = ['constructed_geometry_unknown']
    elif variant == 'partial_baseline':
        baseline['evidence'][0]['text'] = 'Conductivity was measured.\n'
    result = build_block_context(baseline, plans)
    assert not result['wire']['evidence'] and not result['technical_checks_passed']
    assert result['baseline'] == baseline
    assert all(b['state'] == 'deferred_page_retained_in_baseline' for b in result['pages'][0]['blocks'])


@pytest.mark.parametrize('field,value', [('article_id', str(UUID(int=50))), ('page', 7), ('layer_id', str(UUID(int=51))),
    ('text_sha256', 'a' * 64), ('selected_pdf_sha256', 'b' * 64), ('selected_pdf_path', 'foreign.pdf')])
def test_foreign_source_mapping_is_not_accepted(tmp_path, field, value):
    baseline, plans, _ = fixture(tmp_path)
    next(iter(plans.values()))['mapping'][field] = value
    with pytest.raises(ValueError, match='page/layer/PDF'):
        build_block_context(baseline, plans)


@pytest.mark.parametrize('variant', ['quote', 'range', 'core', 'mapping_gap'])
def test_supplied_plan_mutation_cannot_silently_change_selection_or_boundaries(tmp_path, variant):
    baseline, plans, _ = fixture(tmp_path)
    plan = next(iter(plans.values()))
    if variant == 'quote':
        plan['contexts'][2]['quote'] += 'repair'
    elif variant == 'range':
        plan['contexts'][2]['start'] += 1
    elif variant == 'core':
        plan['contexts'][2]['core_units'][0]['start'] += 1
    else:
        plan['mapping']['blocks'][0]['page_start'] += 1
    with pytest.raises(ValueError):
        build_block_context(baseline, plans)


@pytest.mark.parametrize('question', ['For Rivera 2019?', 'How were samples prepared?', 'DSC?'])
def test_no_supported_literal_anchor_does_not_pick_generic_first_blocks(tmp_path, question):
    baseline, plans, _ = fixture(tmp_path, question=question)
    result = build_block_context(baseline, plans)
    assert not result['proposals'] and not result['technical_checks_passed']
    assert 'no_supported_block_context' in result['blocking_reasons']


@pytest.mark.parametrize('question,baseline_allowed', [('Conductivity containing hafnium boride?', True), ('Conductivity?', False)])
def test_candidate_cannot_bypass_missing_qualifiers_or_old_rejection(tmp_path, question, baseline_allowed):
    baseline, plans, _ = fixture(tmp_path, question=question, baseline_allowed=baseline_allowed)
    result = build_block_context(baseline, plans)
    assert not result['query_qualifiers']['candidate_allowed'] and not result['technical_checks_passed']
    assert 'candidate_query_qualifier_check_failed' in result['blocking_reasons']


def test_complete_page_split_among_overlapping_windows_is_still_blocked(tmp_path):
    baseline, plans, _ = fixture(tmp_path, ['Conductivity one.\n', 'Conductivity two.\n', 'Conductivity three.\n',
                                          'Conductivity four.\n', 'Conductivity five.\n'])
    result = build_block_context(baseline, plans)
    assert len(result['proposals']) > 1 and result['assembled_complete_pages']
    assert 'complete_source_page_or_assembled_coverage' in result['blocking_reasons']
    assert not result['technical_checks_passed']


@pytest.mark.parametrize('intervals,expected', [([(0, 3), (3, 6)], True), ([(0, 4), (2, 6)], True),
    ([(0, 2), (4, 6)], False), ([], False)])
def test_union_scope_guard_accounts_for_overlap_and_omissions(intervals, expected):
    assert full_coverage('abcdef', intervals) is expected


def test_whitespace_gap_does_not_evade_page_scope_and_invalid_ranges_fail():
    assert full_coverage('ab \n cd', [(0, 2), (5, 7)])
    with pytest.raises(ValueError):
        full_coverage('abc', [(-1, 2)])


def test_oversize_context_is_retained_with_budget_diagnostic(tmp_path):
    baseline, plans, _ = fixture(tmp_path, ['Background.\n', 'Conductivity ' + 'x' * 101000 + '.\n', 'Other.\n'])
    result = build_block_context(baseline, plans)
    assert result['wire_bytes'] > result['byte_ceiling'] and 'candidate_over_byte_budget' in result['blocking_reasons']
    assert 'x' * 101000 in result['wire']['evidence'][0]['text']


def archived_fixture(tmp_path, relative='app/old.py'):
    root = tmp_path / 'repo'
    original = root / relative
    original.parent.mkdir(parents=True)
    original.write_text('old source', encoding='utf-8')
    checksum = file_hash(original)
    snapshot = tmp_path / 'snapshot'
    source = snapshot / 'source' / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(original.read_bytes())
    (snapshot / 'manifest.json').write_text(json.dumps({'files': [{'path': relative, 'size': source.stat().st_size,
        'sha256': checksum}], 'artifacts': {}, 'source_fingerprint': 'constructed-fingerprint'}), encoding='utf-8')
    captured = tmp_path / 'captured'
    captured.mkdir()
    (captured / 'manifest.json').write_text(json.dumps({'inputs': {str(original): checksum}, 'code': {}, 'outputs': {}}), encoding='utf-8')
    return root, original, snapshot, captured


def test_historical_source_rebinding_is_explicit_and_preserves_old_manifest(tmp_path):
    root, original, snapshot, captured = archived_fixture(tmp_path)
    raw_manifest = (captured / 'manifest.json').read_bytes()
    original.write_text('new source', encoding='utf-8')
    _, bindings, mapping = read_archived(captured, snapshot, source_root=root)
    assert mapping[0]['historical_path'] == str(original)
    assert mapping[0]['archived_source_path'] == str(snapshot / 'source' / 'app' / 'old.py')
    assert str(original) not in bindings
    assert (captured / 'manifest.json').read_bytes() == raw_manifest


@pytest.mark.parametrize('variant', ['private', 'archive_corrupt', 'conflict', 'escape'])
def test_archive_cannot_mask_changed_private_inputs_or_corruption(tmp_path, variant):
    root, original, snapshot, captured = archived_fixture(tmp_path, 'data/private.pdf' if variant == 'private' else 'app/old.py')
    if variant == 'archive_corrupt':
        (snapshot / 'source' / 'app' / 'old.py').write_bytes(b'corrupt')
    else:
        original.write_bytes(b'changed')
    manifest = captured / 'manifest.json'
    data = json.loads(manifest.read_bytes())
    if variant == 'conflict':
        data['code'][str(original)] = '0' * 64
    elif variant == 'escape':
        data['outputs']['../outside.json'] = '0' * 64
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        read_archived(captured, snapshot, source_root=root)


def test_block_api_uses_server_preparation_and_never_accepts_client_pdf_paths(client, tmp_path, monkeypatch):
    baseline, plans, _ = fixture(tmp_path)
    result = build_block_context(baseline, plans)
    prepare = Mock(return_value=baseline)
    builder = Mock(return_value=result)
    monkeypatch.setattr(routes, 'prepare_api', prepare)
    monkeypatch.setattr(routes, 'build_block_context', builder)
    response = client.post('/answer/prepare/blocks', json={'question': 'Conductivity?', 'method': 'exact'})
    assert response.status_code == 200 and response.json()['version'] == VERSION
    prepare.assert_called_once()
    builder.assert_called_once_with(baseline)
    assert client.post('/answer/prepare/blocks', json={'question': 'Conductivity?', 'plans': {'pdf': 'private'}}).status_code == 422


def test_block_ui_preserves_scope_and_escapes_question_and_complete_diagnostics(client, tmp_path, monkeypatch):
    baseline, plans, _ = fixture(tmp_path)
    result = build_block_context(baseline, plans)
    result['baseline']['question'] = '<script>untrusted</script>'
    monkeypatch.setattr(routes, 'block_api', Mock(return_value=result))
    response = client.post('/ui/answer/prepare/blocks', data={'question': '<script>query</script>', 'method': 'exact',
        'collection': 'selected-library', 'top_k': '3', 'library_source_id': str(UUID(int=14))})
    assert response.status_code == 200
    assert '&lt;script&gt;query' in response.text and '&lt;script&gt;untrusted' in response.text
    assert '<script>untrusted' not in response.text and 'action="/ui/answer/prepare/blocks"' in response.text
    assert 'value="selected-library"' in response.text and '<option selected>exact</option>' in response.text
    assert 'Генерация отключена' in response.text and 'Оригинальный PDF' in response.text


def test_block_get_inherits_library_cookie_and_has_no_automatic_generation(client):
    client.cookies.set('ariadne_library_id', str(UUID(int=15)))
    response = client.get('/ui/answer/prepare/blocks')
    assert response.status_code == 200 and str(UUID(int=15)) in response.text
    assert 'action="/ui/answer/prepare/blocks"' in response.text


def frozen_fixture(tmp_path):
    from app.evaluation import block_run
    baseline, plans, region = fixture(tmp_path)
    result = build_block_context(baseline, plans)
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    plan = {'version': VERSION, 'questions': [{'id': 'constructed', 'previous_baseline': baseline}],
            'historical_code_mapping': []}
    (prepared / 'plan.json').write_text(json.dumps(plan), encoding='utf-8')
    code = {str(Path(n).resolve()): file_hash(Path(n))
            for n in (*block_run.CODE, *block_run.SUPPORT)}
    (prepared / 'manifest.json').write_text(json.dumps({'version': VERSION, 'phase': 'prepared_before_block_api_smoke',
        'inputs': {region.original_pdf_path: region.original_pdf_sha256}, 'code': code,
        'outputs': {'plan.json': file_hash(prepared / 'plan.json')}}), encoding='utf-8')
    return prepared, result, region


def test_frozen_export_is_exclusive_deterministic_and_preserves_native_block_results(tmp_path):
    from app.evaluation import block_run
    prepared, result, _ = frozen_fixture(tmp_path)
    captured = tmp_path / 'captured'
    captured.mkdir()
    rows = [{'id': 'constructed', 'response': result, 'evidence_identical_to_stage31': True}]
    report = {'version': VERSION, 'summary': block_run.summary(rows), 'results': rows}
    (captured / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    _, bindings = block_run.load(prepared)
    (captured / 'manifest.json').write_text(json.dumps({'version': VERSION, 'phase': 'read_only_block_api_smoke',
        'inputs': bindings, 'code': {}, 'outputs': {'report.json': file_hash(captured / 'report.json')}}), encoding='utf-8')
    first, repeat = tmp_path / 'first', tmp_path / 'repeat'
    block_run.export(prepared, captured, first)
    block_run.export(prepared, captured, repeat)
    assert json.loads((first / 'report.json').read_bytes()) == json.loads((captured / 'report.json').read_bytes())
    assert '&lt;script&gt;' in (first / 'review.html').read_text(encoding='utf-8')
    for p in first.iterdir():
        assert p.read_bytes() == (repeat / p.name).read_bytes()
    with pytest.raises(FileExistsError):
        block_run.export(prepared, captured, first)


@pytest.mark.parametrize('variant', ['phase', 'code', 'private_input', 'conflict', 'plan_hash'])
def test_frozen_current_plan_drift_stops_new_comparison(tmp_path, variant):
    from app.evaluation import block_run
    prepared, _, _ = frozen_fixture(tmp_path)
    path = prepared / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    if variant == 'phase':
        manifest['phase'] = 'other'
    elif variant == 'code':
        manifest['code'] = {}
    elif variant == 'private_input':
        for name in manifest['inputs']:
            manifest['inputs'][name] = '0' * 64
    elif variant == 'conflict':
        manifest['inputs'][next(iter(manifest['code']))] = '0' * 64
    else:
        (prepared / 'plan.json').write_bytes(b'changed')
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        block_run.load(prepared)
