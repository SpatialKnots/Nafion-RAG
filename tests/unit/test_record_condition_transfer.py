"""Constructed transfer/accounting tests; not independent scientific annotations."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from app.records.condition_scope import source_events
from app.records.condition_transfer import block_source, build_packet, execute_packet, packet_inventory, registered_units
from app.records.condition_transfer_export import prepare_transfer, run_transfer
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_table_relations import source_fixture


def fixtures(pdf_path='/constructed/storage.pdf', pdf_hash='a' * 64):
    template = source_fixture()[0].regions[0].model_dump()
    groups = [('Электропроводность измеряли методом импедансной спектроскопии.\n',),
              ('Ionic conductivity was measured.\n', 'Samples were dried at 80°C.\n', 'No other text'),
              ('Электропроводность измеряли методом импедансной спектроскопии.\n', 'Обрезанное предложение')]
    sources, pages, declarations, documents = {}, [], [], []
    for index, blocks in enumerate(groups, 1):
        article_id = str(UUID(int=index))
        text = ''.join(blocks)
        data = {**template, 'article_id': article_id, 'page_number': 1, 'original_pdf_path': str(pdf_path),
                'layer_pdf_path': str(pdf_path), 'original_pdf_sha256': pdf_hash, 'layer_pdf_sha256': pdf_hash,
                'start': 0, 'end': len(text), 'quote': text, 'page_text': text,
                'quote_sha256': text_hash(text), 'page_text_sha256': text_hash(text)}
        data['region_id'] = source_identity(data)
        source = SourceRegion.model_validate(data)
        sources[article_id, 1] = source
        task_id = str(UUID(int=1 if index == 1 else 2))
        role = 'proposed_supplement' if index == 3 else 'primary'
        cursor, registry = 0, []
        for number, block in enumerate(blocks):
            registry.append({'block_number': number, 'page_start': cursor, 'page_end': cursor + len(block),
                             'bbox': [0, number * 20, 500, number * 20 + 10]})
            cursor += len(block)
        pages.append({'article_id': article_id, 'page_number': 1, 'parent_region_id': source.region_id, 'page_text': text,
            'task_id': task_id, 'planning_state': 'deferred_page' if index < 3 else 'planned_with_explicit_context_states',
            'diagnostics': ['constructed_layout_risk'] if index < 3 else [],
            'mapping': {'article_id': article_id, 'page': 1, 'layer_id': str(source.text_layer_id), 'text_sha256': text_hash(text),
                'selected_pdf_sha256': pdf_hash, 'diagnostic': None, 'blocks': registry}})
        declarations.append({'article_id': article_id, 'role': role, 'bundle': article_id + '.json',
            'original_pdf_path': str(pdf_path), 'original_pdf_sha256': pdf_hash, 'pages': [{'page_number': 1}]})
        documents.append({'article_id': article_id, 'title': 'Constructed <script> source ' + str(index)})
    scope = {'documents': documents, 'tasks': [
        {'task_id': str(UUID(int=1)), 'exposure': 'development_exposed', 'documents': declarations[:1]},
        {'task_id': str(UUID(int=2)), 'exposure': 'development_exposed', 'documents': declarations[1:]}]}
    control = sources[str(UUID(int=1)), 1]
    return scope, {'pages': pages}, sources, control, [e.model_dump(mode='json') for e in source_events(control)]


def packet():
    return build_packet(*fixtures())


def test_full_scope_excludes_control_task_keeps_supplement_and_every_no_keyword_block():
    prepared = packet()
    assert prepared['inventory'] == {'primary_task_groups': 1, 'source_documents': 2, 'source_pages': 2,
        'registered_blocks': 5, 'probe_units': 5, 'deferred_mapping_pages': 0, 'historically_deferred_layout_pages': 1,
        'document_roles': {'primary': 1, 'proposed_supplement': 1}}
    assert all(p['article_id'] != str(UUID(int=1)) for p in prepared['pages'])
    assert prepared['pages'][0]['diagnostics'] == ['constructed_layout_risk']
    assert prepared['scientific_admission'] == 'not_evaluated'


def test_raw_transfer_preserves_english_abstentions_russian_cue_and_clipped_text_separately_from_control():
    result = execute_packet(packet())
    assert result['summary']['unit_outcomes'] == {'no_literal_cue': 4, 'literal_cue_observed': 1}
    assert result['summary']['separate_control_events'] == 1
    assert result['summary']['source_events'] == 5
    assert result['summary']['event_kinds'] == {'unclassified': 4, 'measurement_protocol': 1}
    assert result['summary']['event_states'] == {'unsupported_clause': 2, 'incomplete_source': 2, 'complete_clause_proposal': 1}
    assert result['summary']['new_measurement_records'] == result['summary']['new_model_calls'] == 0


def test_derived_source_preserves_exact_unicode_page_layer_and_pdf_identities():
    prepared = packet()
    page = prepared['pages'][1]
    parent = SourceRegion.model_validate(page['source'])
    source = block_source(parent, page['units'][1])
    assert source.quote == 'Обрезанное предложение'
    assert source.page_text[source.start:source.end] == source.quote
    assert source.original_pdf_sha256 == parent.original_pdf_sha256
    assert source.text_layer_id == parent.text_layer_id
    assert parent.quote == page['source']['quote']


@pytest.mark.parametrize('variant', ['gap', 'overlap', 'duplicate', 'invalid_bbox', 'infinite_bbox', 'negative_number',
                                     'incomplete_coverage', 'mapping_diagnostic', 'missing_mapping'])
def test_unproven_mapping_retains_full_page_and_defers_all_units(variant):
    scope, windows, sources, control, events = fixtures()
    page = windows['pages'][1]
    blocks = page['mapping']['blocks']
    if variant == 'gap':
        blocks[1]['page_start'] += 1
    elif variant == 'overlap':
        blocks[1]['page_start'] -= 1
    elif variant == 'duplicate':
        blocks[1]['block_number'] = blocks[0]['block_number']
    elif variant == 'invalid_bbox':
        blocks[0]['bbox'][2] = 0
    elif variant == 'infinite_bbox':
        blocks[0]['bbox'][1] = float('inf')
    elif variant == 'negative_number':
        blocks[0]['block_number'] = -1
    elif variant == 'incomplete_coverage':
        blocks.pop()
    elif variant == 'mapping_diagnostic':
        page['mapping']['diagnostic'] = 'constructed_unproven_mapping'
    else:
        page.pop('mapping')
    prepared = build_packet(scope, windows, sources, control, events)
    retained = prepared['pages'][0]
    assert retained['source']['quote'] == page['page_text']
    assert retained['probe_diagnostics'] and not retained['units']
    assert prepared['inventory']['source_pages'] == 2 and prepared['inventory']['deferred_mapping_pages'] == 1
    assert execute_packet(prepared)['summary']['executed_units'] == 2


@pytest.mark.parametrize('variant', ['missing_page', 'duplicate_page', 'wrong_source', 'foreign_mapping', 'unregistered_source',
                                     'duplicate_declaration', 'no_control_task'])
def test_frozen_page_and_document_identity_failures_are_not_hidden(variant):
    scope, windows, sources, control, events = fixtures()
    if variant == 'missing_page':
        windows['pages'].pop()
    elif variant == 'duplicate_page':
        windows['pages'].append(windows['pages'][1])
    elif variant == 'wrong_source':
        windows['pages'][1]['parent_region_id'] = 'f' * 64
    elif variant == 'foreign_mapping':
        windows['pages'][1]['mapping']['article_id'] = str(UUID(int=99))
    elif variant == 'unregistered_source':
        del sources[str(UUID(int=2)), 1]
    elif variant == 'duplicate_declaration':
        scope['tasks'][1]['documents'].append(scope['tasks'][1]['documents'][0])
    else:
        scope['tasks'].pop(0)
    with pytest.raises(ValueError):
        build_packet(scope, windows, sources, control, events)


@pytest.mark.parametrize('variant', ['inventory', 'duplicate_unit', 'lost_unit', 'unit_text', 'control_drift', 'version'])
def test_prepared_packet_or_control_drift_stops_execution(variant):
    prepared = packet()
    if variant == 'inventory':
        prepared['inventory']['probe_units'] -= 1
    elif variant == 'duplicate_unit':
        prepared['pages'][0]['units'][1] = prepared['pages'][0]['units'][0]
    elif variant == 'lost_unit':
        prepared['pages'][0]['units'].pop()
    elif variant == 'unit_text':
        prepared['pages'][0]['units'][0]['source']['text'] = 'Changed text'
    elif variant == 'control_drift':
        prepared['expected_control_events'][0]['diagnostic'] = 'Changed expected control'
    else:
        prepared['version'] = 'other'
    with pytest.raises(ValueError):
        execute_packet(prepared)


def storage_parents(tmp_path):
    pdf = tmp_path / 'constructed-storage.pdf'
    pdf.write_bytes(b'Constructed checksum storage fixture, not experimental PDF evidence.')
    scope, windows, sources, control, events = fixtures(pdf, file_hash(pdf))
    stage18, stage19, stage25 = [tmp_path / name for name in ('scope', 'windows', 'control')]
    for directory in (stage18, stage19, stage25):
        directory.mkdir()
    for task in scope['tasks']:
        for declaration in task['documents']:
            source = sources[declaration['article_id'], 1]
            bundle = CandidateBundle(run_id=UUID(int=100), created_at=datetime(2026, 1, 1, tzinfo=UTC),
                producer='constructed_transfer_fixture', regions=(source,))
            path = stage18 / declaration['bundle']
            path.write_text(bundle.model_dump_json(), encoding='utf-8')
            declaration['sha256'] = file_hash(path)
    (stage18 / 'report.json').write_text(json.dumps(scope, ensure_ascii=False), encoding='utf-8')
    (stage19 / 'report.json').write_text(json.dumps(windows, ensure_ascii=False), encoding='utf-8')
    (stage25 / 'source_events.json').write_text(json.dumps({'events': events}, ensure_ascii=False), encoding='utf-8')
    (stage25 / 'parent_report.json').write_text(json.dumps({'sources': {control.region_id: control.model_dump(mode='json')}},
                                                       ensure_ascii=False), encoding='utf-8')
    rule = Path('app/records/condition_scope.py').resolve()
    for directory, version in ((stage18, 'records_article_scope_v0.1'), (stage19, 'records_article_windows_v0.1'),
                               (stage25, 'records_condition_scope_v0.1')):
        manifest = {'version': version, 'inputs': {str(pdf.resolve()): file_hash(pdf)},
            'code': {str(rule): file_hash(rule)}, 'outputs': {p.name: file_hash(p) for p in directory.iterdir()}}
        (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return stage18, stage19, stage25


def test_preparation_does_not_execute_rules_and_exports_are_exclusive_deterministic_and_escaped(tmp_path):
    stage18, stage19, stage25 = storage_parents(tmp_path)
    prepared = tmp_path / 'prepared'
    with patch('app.records.condition_transfer.source_events', side_effect=AssertionError('Preparation ran rules')):
        summary = prepare_transfer(stage18, stage19, stage25, prepared, source_root=Path.cwd())
    assert summary['probe_units'] == 5
    first, second = tmp_path / 'first', tmp_path / 'second'
    result = run_transfer(prepared, first)
    run_transfer(prepared, second)
    assert result['control_replay_exact']
    assert (first / 'prepared_packet.json').read_bytes() == (prepared / 'packet.json').read_bytes()
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    html = (first / 'review.html').read_text(encoding='utf-8')
    assert html.count('class="page"') == 2 and html.count('class="unit"') == 5
    assert '&lt;script&gt;' in html and 'Constructed <script>' not in html and '<form' not in html
    with pytest.raises(FileExistsError):
        run_transfer(prepared, first)
    with pytest.raises(FileExistsError):
        prepare_transfer(stage18, stage19, stage25, prepared, source_root=Path.cwd())


@pytest.mark.parametrize('variant', ['input_drift', 'rule_hash', 'version', 'populated_bundle', 'pdf_not_bound'])
def test_frozen_parent_code_source_and_manifest_failures_stop_preparation(tmp_path, variant):
    stage18, stage19, stage25 = storage_parents(tmp_path)
    manifest_path = stage25 / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    if variant == 'input_drift':
        (stage25 / 'parent_report.json').write_bytes(b'changed')
    elif variant == 'rule_hash':
        manifest['code'][str(Path('app/records/condition_scope.py').resolve())] = 'f' * 64
    elif variant == 'version':
        manifest['version'] = 'other'
    elif variant == 'pdf_not_bound':
        for directory in (stage18, stage19, stage25):
            path = directory / 'manifest.json'
            data = json.loads(path.read_bytes())
            data['inputs'] = {}
            path.write_text(json.dumps(data), encoding='utf-8')
        manifest['inputs'] = {}
    else:
        bundle_path = next(p for p in stage18.glob('*.json') if p.name not in {'manifest.json', 'report.json'})
        data = json.loads(bundle_path.read_bytes())
        data['records'] = [{'invalid_constructed_record': True}]
        bundle_path.write_text(json.dumps(data), encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        prepare_transfer(stage18, stage19, stage25, tmp_path / 'prepared', source_root=Path.cwd())


@pytest.mark.parametrize('variant', ['packet_hash', 'phase', 'frozen_rule', 'code_changed'])
def test_execution_requires_unchanged_preparation_and_frozen_code(tmp_path, variant):
    stage18, stage19, stage25 = storage_parents(tmp_path)
    prepared = tmp_path / 'prepared'
    prepare_transfer(stage18, stage19, stage25, prepared, source_root=Path.cwd())
    manifest_path = prepared / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    if variant == 'packet_hash':
        (prepared / 'packet.json').write_bytes(b'changed')
    elif variant == 'phase':
        manifest['phase'] = 'executed'
    elif variant == 'code_changed':
        manifest['code'][str(Path('app/records/condition_transfer.py').resolve())] = 'f' * 64
    else:
        path = prepared / 'packet.json'
        data = json.loads(path.read_bytes())
        data['frozen_rule']['sha256'] = 'f' * 64
        path.write_text(json.dumps(data), encoding='utf-8')
        manifest['outputs']['packet.json'] = file_hash(path)
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        run_transfer(prepared, tmp_path / 'run')


def test_missing_or_empty_source_page_stays_declared_without_synthetic_units():
    scope, windows, sources, control, events = fixtures()
    del sources[str(UUID(int=2)), 1]
    windows['pages'][1]['page_text'] = None
    prepared = build_packet(scope, windows, sources, control, events)
    assert prepared['pages'][0]['source'] is None and prepared['pages'][0]['probe_diagnostics']
    assert execute_packet(prepared)['summary']['source_pages'] == 2


def test_packet_control_task_cannot_be_included_even_if_inventory_is_recomputed():
    prepared = copy.deepcopy(packet())
    prepared['pages'][0]['task_id'] = prepared['excluded_task_ids'][0]
    with pytest.raises(ValueError):
        packet_inventory(prepared)


def test_wrong_registry_identity_fails_instead_of_becoming_a_deferred_mapping():
    _, windows, sources, _, _ = fixtures()
    page = windows['pages'][1]
    page['mapping']['text_sha256'] = 'f' * 64
    with pytest.raises(ValueError):
        registered_units(page, sources[page['article_id'], 1])
