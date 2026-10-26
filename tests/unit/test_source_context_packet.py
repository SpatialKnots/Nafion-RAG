"""Source/dependency preservation checks, not scientific answer-accuracy labels."""

import copy
import json
from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from app.evaluation.context_risks import audit_context_risks, canonical
from app.generation.block_context import build_block_context
from app.generation.source_context_packet import PARENT_VERSION, build_source_packet, expand_context, validate_packet
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_context_risks import asset, parent_fixture, real_parent, visual


def envelope(preparation):
    return {'version': PARENT_VERSION, 'preparation': preparation, 'audit': audit_context_risks(preparation),
        'generation_performed': False, 'external_request_constructed': False, 'network_ready': False}


def packet_fixture(tmp_path, **kwargs):
    preparation, region = parent_fixture(tmp_path, **kwargs)
    parent = envelope(preparation)
    return build_source_packet(parent), parent, region


def test_every_original_context_expands_exactly_and_parent_stays_immutable(tmp_path):
    packet, parent, region = packet_fixture(tmp_path)
    before = copy.deepcopy(parent)
    for page in parent['audit']['pages']:
        for window in page['windows']:
            assert expand_context(packet, window['context_id']) == window['quote']
    assert packet['parent'] == parent == before
    validate_packet(json.loads(canonical(packet)))
    assert not packet['network_ready'] and not packet['generation_performed'] and not packet['external_request_constructed']
    assert packet['scientific_admission'] == 'not_evaluated'
    assert region.original_pdf_path not in canonical(packet['wire'])
    assert packet['byte_ceiling'] == 100000


def test_split_method_and_continuation_keep_interleaved_formula_blocks_together(tmp_path):
    blocks = ['Background.\n', 'Conductivity was measured after attaining\n', 'x\n', 'a/b\n', '= z\n',
        'thermal equilibrium.\n', 'Final complete text.\n']
    packet, parent, _ = packet_fixture(tmp_path, blocks=blocks)
    by_id = {n['id']: n for n in packet['wire']['nodes']}
    assert any({1, 2, 3, 4, 5} <= {by_id[n]['block_number'] for n in unit}
        for unit in packet['wire']['co_preservation_units'])
    assert not any({1, 5} <= set(w['block_numbers']) for p in parent['audit']['pages'] for w in p['windows'])
    assert all(g['scientific_relation'] == 'not_established' for g in packet['wire']['dependencies'])


def test_protected_header_rows_footnote_and_intervening_blocks_are_one_unit(tmp_path):
    packet, _, _ = packet_fixture(tmp_path, protected=[1, 3, 5])
    by_id = {n['id']: n for n in packet['wire']['nodes']}
    groups = [g for g in packet['wire']['dependencies'] if g['kind'] == 'protected_source_group']
    assert groups and {1, 2, 3, 4, 5} <= {by_id[n]['block_number'] for n in groups[0]['nodes']}
    assert any(set(groups[0]['nodes']) <= set(unit) for unit in packet['wire']['co_preservation_units'])


def test_same_text_at_different_offsets_is_not_deduplicated(tmp_path):
    packet, _, _ = packet_fixture(tmp_path, blocks=['Conductivity was measured.\n'] * 3)
    nodes = packet['wire']['nodes']
    assert len(nodes) == 3 and len({n['node_id'] for n in nodes}) == 3
    assert len({n['text'] for n in nodes}) == 1
    assert packet['assembled_complete_pages']
    assert 'complete_source_page_or_assembled_coverage' in packet['blocking_reasons']


def test_all_source_events_negation_citation_and_preparation_scope_are_preserved(tmp_path):
    blocks = ['Background.\n', 'Conductivity was not measured [12].\n',
        'Samples were prepared in argon.\n', 'Measurements were performed at 25 C.\n', 'Unfinished qualifier']
    packet, parent, _ = packet_fixture(tmp_path, blocks=blocks)
    original = {b['block_number']: b['events'] for b in parent['preparation']['pages'][0]['blocks']}
    for node in packet['wire']['nodes']:
        assert node['events'] == original[node['block_number']]
    guarded = [e for n in packet['wire']['nodes'] for e in n['events'] if e['block_guards']]
    assert guarded and all(e['scientific_support'] == 'not_evaluated' for e in guarded)
    assert any(e['proposed_kind'] == 'preparation_procedure' for n in packet['wire']['nodes'] for e in n['events'])


def test_unknown_visual_assets_are_retained_even_outside_window_geometry(tmp_path):
    packet, parent, _ = packet_fixture(tmp_path, assets=[asset((20, 1, 30, 3))])
    assert packet['wire']['pages'][0]['visual_registry']['assets'] == parent['audit']['pages'][0]['visual_registry']['assets']
    assert packet['wire']['contexts'][0]['asset_relations'][0]['relation'] == 'outside_selected_geometry_relevance_unknown'
    assert not packet['network_ready']


def test_no_query_anchor_keeps_empty_packet_and_complete_local_parent(tmp_path):
    packet, parent, _ = packet_fixture(tmp_path, question='Who are the authors?')
    assert not packet['wire']['nodes'] and not packet['wire']['contexts']
    assert packet['parent'] == parent and 'no_registered_context_nodes' in packet['blocking_reasons']
    assert all(b['state'] == 'not_selected_retained_in_local_parent'
        for p in packet['wire']['pages'] for b in p['block_accounting'])


def test_old_refusals_and_missing_qualifiers_never_become_allowances(tmp_path):
    packet, parent, _ = packet_fixture(tmp_path, baseline_allowed=False)
    assert set(parent['preparation']['blocking_reasons']) <= set(packet['blocking_reasons'])
    assert 'baseline_insufficient_evidence' in packet['blocking_reasons'] and not packet['network_ready']


def test_oversize_text_is_kept_without_clipping_or_ceiling_change(tmp_path):
    blocks = ['Conductivity was measured. ' + 'unbroken text ' * 12000 + '\n', 'Final statement.\n']
    packet, _, _ = packet_fixture(tmp_path, blocks=blocks)
    assert packet['wire_bytes'] > packet['byte_ceiling'] == 100000
    assert 'source_packet_over_existing_byte_ceiling' in packet['blocking_reasons']
    assert any(n['text'] == blocks[0] for n in packet['wire']['nodes'])


@pytest.mark.parametrize('change', ['text', 'reference', 'order', 'dependency', 'source', 'event', 'blocker', 'wire_hash'])
def test_output_mutation_and_foreign_references_fail_visible_validation(tmp_path, change):
    packet, _, _ = packet_fixture(tmp_path, protected=[2, 3, 4])
    if change == 'text':
        packet['wire']['nodes'][0]['text'] += 'altered'
    elif change == 'reference':
        packet['wire']['contexts'][0]['nodes'][0] = 'foreign'
    elif change == 'order':
        packet['wire']['contexts'][0]['nodes'].reverse()
    elif change == 'dependency':
        packet['wire']['dependencies'][0]['nodes'].pop()
    elif change == 'source':
        packet['wire']['pages'][0]['text_layer_id'] = str(uuid4())
    elif change == 'event':
        packet['wire']['nodes'][0]['events'] = []
    elif change == 'blocker':
        packet['blocking_reasons'] = []
    else:
        packet['wire_sha256'] = '0' * 64
    with pytest.raises(ValueError):
        validate_packet(packet)


@pytest.mark.parametrize('flag', ['network_ready', 'generation_performed', 'external_request_constructed'])
def test_generation_parent_is_rejected(tmp_path, flag):
    _, parent, _ = packet_fixture(tmp_path)
    parent[flag] = True
    with pytest.raises(ValueError, match='no-generation'):
        build_source_packet(parent)


def test_unproven_mapping_has_no_atomic_source_claims(tmp_path):
    from app.evaluation.context_windows import RegisteredBlocks, TextBlock
    from app.records.article_windows import plan_page

    preparation, region = parent_fixture(tmp_path)
    raw = preparation['pages'][0]['plan']['mapping']
    mapping = RegisteredBlocks(raw['article_id'], raw['page'], raw['layer_id'], raw['text_sha256'],
        raw['selected_pdf_path'], raw['selected_pdf_sha256'], tuple(TextBlock(**b) for b in raw['blocks']), 'constructed_unproven')
    plan = plan_page(region, mapping, [])
    plan['source_gaps'] = visual(region, proven=False)
    parent = envelope(build_block_context(preparation['baseline'], {region.region_id: plan}))
    packet = build_source_packet(parent)
    assert not packet['wire']['nodes'] and packet['parent'] == parent
    assert all(b['state'] == 'unproven_mapping_full_page_retained_in_local_parent'
        for b in packet['wire']['pages'][0]['block_accounting'])


def native_two_pages(tmp_path, *, foreign_article=False, mixed_layer=False, only_first=False):
    preparation, template = parent_fixture(tmp_path)
    path = tmp_path / 'two-pages.pdf'
    with fitz.open() as document:
        for lines in [['Background.', 'Conductivity was measured after attaining'],
                      ['thermal equilibrium.', 'Conductivity measurements were repeated.']]:
            page = document.new_page()
            for i, line in enumerate(lines):
                page.insert_text((40, 60 + 40 * i), line)
        texts = [p.get_text('text') for p in document]
        document.save(path)
    checksum = file_hash(path)
    regions = []
    baseline = preparation['baseline']
    baseline['sources'] = {'pages': {}, 'chunk_layers': {}}
    original = baseline['evidence'][0]
    baseline['evidence'] = []
    for i, raw_text in enumerate(texts[:1] if only_first else texts):
        raw = template.model_dump()
        raw.update(page_number=i + 1, original_pdf_path=str(path), layer_pdf_path=str(path), original_pdf_sha256=checksum,
            layer_pdf_sha256=checksum, text_layer_id=uuid4(), page_text=raw_text, page_text_sha256=text_hash(raw_text),
            quote=raw_text, quote_sha256=text_hash(raw_text), start=0, end=len(raw_text))
        if i and foreign_article:
            raw['article_id'] = uuid4()
        if i and mixed_layer:
            raw['text_layer'] = 'ocr'
        raw['region_id'] = source_identity(raw)
        region = SourceRegion.model_validate(raw)
        regions.append(region)
        chunk = str(uuid4())
        baseline['sources']['pages'][region.region_id] = region.model_dump(mode='json')
        baseline['sources']['chunk_layers'][chunk] = region.text_layer
        baseline['article_metadata'][str(region.article_id)] = {'authors': None, 'year': None}
        baseline['evidence'].append({**original, 'citation_id': 'E' + str(i + 1), 'chunk_id': chunk,
            'article_id': str(region.article_id), 'page_start': i + 1, 'page_end': i + 1, 'text': raw_text})
    return envelope(build_block_context(baseline)), path


@pytest.mark.parametrize('foreign_article,mixed_layer', [(False, False), (True, False), (False, True)])
def test_actual_pdf_cross_page_scope_never_borrows_another_article_or_layer(tmp_path, foreign_article, mixed_layer):
    parent, path = native_two_pages(tmp_path, foreign_article=foreign_article, mixed_layer=mixed_layer)
    before = file_hash(path)
    packet = build_source_packet(parent)
    cross = [d for d in packet['wire']['dependencies'] if d['kind'] == 'unresolved_cross_page_boundary']
    assert bool(cross) is (not foreign_article and not mixed_layer)
    assert all(d['details']['table_continuation'] == 'not_established' for d in cross)
    assert file_hash(path) == before and not packet['network_ready']


def test_missing_physical_next_page_is_diagnostic_and_not_fetched(tmp_path):
    parent, _ = native_two_pages(tmp_path, only_first=True)
    packet = build_source_packet(parent)
    assert any(d['state'] == 'missing_registered_neighbor' and d['neighbor_page'] == 2
        for p in packet['wire']['pages'] for d in p['open_boundaries'])
    assert 'unresolved_context_page_boundaries' in packet['blocking_reasons']


def test_native_pdf_packet_reconstruction_does_not_mutate_pdf(tmp_path):
    preparation, _ = real_parent(tmp_path)
    parent = envelope(preparation)
    path = preparation['baseline']['sources']['pages']['page']['original_pdf_path']
    before = file_hash(Path(path))
    packet = build_source_packet(parent)
    assert packet['original_windows'] > 0
    validate_packet(packet)
    assert file_hash(Path(path)) == before


def runner_fixture(tmp_path, monkeypatch):
    from app.evaluation import source_context_packet_run as runner
    from app.records.condition_transfer_export import read_frozen
    from app.records.extraction import write_json

    preparation, pdf = real_parent(tmp_path)
    parent = envelope(preparation)
    native, metadata = tmp_path / 'native', tmp_path / 'metadata'
    native.mkdir()
    metadata.mkdir()
    rows = []
    for name in ('method', 'table', 'guard', 'missing'):
        folder = native / name
        folder.mkdir()
        write_json(folder / 'response.json', parent)
        rows.append({'id': name, 'response': parent})
    write_json(native / 'report.json', {'results': rows})
    write_json(native / 'manifest.json', {'version': PARENT_VERSION, 'phase': 'read_only_risk_api_smoke',
        'inputs': {str(pdf): file_hash(pdf)}, 'code': {},
        'outputs': {p.relative_to(native).as_posix(): file_hash(p) for p in native.rglob('*.json')}})
    source = next(iter(preparation['baseline']['sources']['pages'].values()))
    metadata_row = {'article_id': source['article_id'], 'title': 'Constructed example',
        'proposal': {'sources': {'original_pdf_path': str(pdf), 'regions': [source]},
            'projection': {'after_values': dict.fromkeys(('authors', 'journal', 'year'))},
            'extracted': {'fields': {f: {'status': 'not_found', 'value': None, 'candidates': []}
                for f in ('authors', 'journal', 'year')}}}, 'historical_tac': {'sections': []}}
    write_json(metadata / 'report.json', {'phase': 'applied_metadata_proposals', 'summary': {}, 'articles': [metadata_row]})
    write_json(metadata / 'manifest.json', {'version': 'registered_tac_metadata_v0.1', 'phase': 'applied_metadata_proposals',
        'inputs': {str(pdf): file_hash(pdf)}, 'code': {}, 'outputs': {'report.json': file_hash(metadata / 'report.json')}})
    challenges = tmp_path / 'challenges.json'
    write_json(challenges, {'version': 'source_context_retention_challenges_v0.1',
        'origin': 'assistant_source_development_before_new_packet_outcomes', 'independent_human_confirmation': False,
        'parent_report_sha256': file_hash(native / 'report.json'),
        'visual_evidence': {'path': str(pdf), 'sha256': file_hash(pdf)},
        'cases': [{'id': r['id'], 'task_id': r['id'], 'kind': 'no_refusal_upgrade'} for r in rows]})

    def archived(directory, archive, *, source_root):
        manifest, bindings = read_frozen(directory, PARENT_VERSION, source_root)
        return manifest, bindings, []

    monkeypatch.setattr(runner, 'read_archived', archived)
    prepared = tmp_path / 'prepared'
    runner.prepare(native, tmp_path / 'unused_constructed_archive', metadata, challenges, prepared)
    return runner, prepared, native, metadata, challenges, pdf


def test_frozen_native_pipeline_exports_exactly_without_sources_or_database_mutation(tmp_path, monkeypatch):
    runner, prepared, _, _, _, pdf = runner_fixture(tmp_path, monkeypatch)
    before = file_hash(pdf)
    captured, first, second = [tmp_path / n for n in ('captured', 'first', 'second')]
    result = runner.run(prepared, captured)
    assert result['questions'] == result['retention_challenges_passed'] == 4
    assert result['database_access'] is False and result['model_calls'] == result['retrieval_calls'] == 0
    assert runner.export(captured, first) == runner.export(captured, second) == result
    for path in captured.rglob('*'):
        if path.is_file():
            name = path.relative_to(captured)
            assert path.read_bytes() == (first / name).read_bytes() == (second / name).read_bytes()
    metadata_html = (captured / 'metadata_review.html').read_text(encoding='utf-8')
    assert 'href="metadata.json"' in metadata_html and 'href="report.json"' not in metadata_html
    assert file_hash(pdf) == before
    with pytest.raises(FileExistsError):
        runner.run(prepared, captured)


@pytest.mark.parametrize('variant', ['challenge', 'source', 'native', 'code'])
def test_frozen_pipeline_rejects_drift_before_creating_output(tmp_path, monkeypatch, variant):
    runner, prepared, native, _, challenges, pdf = runner_fixture(tmp_path, monkeypatch)
    target = {'challenge': challenges, 'source': pdf, 'native': native / 'method/response.json'}.get(variant)
    if variant == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        target.write_bytes(b'changed')
    output = tmp_path / 'rejected'
    with pytest.raises(ValueError):
        runner.run(prepared, output)
    assert not output.exists()


def test_packet_html_keeps_exact_escaped_contexts_search_and_companion_tac_link(tmp_path):
    from app.evaluation.source_context_packet_run import render

    packet, _, _ = packet_fixture(tmp_path, blocks=['Conductivity <script>alert(1)</script> was measured.\n'])
    report = {'summary': {}, 'results': [{'id': 'example', 'packet_file': 'example/packet.json',
        'expanded_file': 'example/expanded_contexts.json'}]}
    page = render(report, {'example': packet})
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page and '<script>alert(1)</script>' not in page
    assert 'type="search"' in page and 'metadata_review.html' in page and '<form' not in page
    assert page.count('<article data-query>') == 1 and 'file:///' in page


def test_retention_challenge_foreign_span_fails_before_scoring(tmp_path):
    from app.evaluation.source_context_packet_run import validate_challenges
    from app.records.extraction import write_json

    _, parent, region = packet_fixture(tmp_path)
    path = tmp_path / 'parent.json'
    write_json(path, parent)
    references = {'version': 'source_context_retention_challenges_v0.1',
        'origin': 'assistant_source_development_before_new_packet_outcomes', 'independent_human_confirmation': False,
        'cases': [{'id': 'wrong', 'task_id': 'one', 'kind': 'one_co_preservation_unit',
            'parent_region_id': region.region_id, 'source': {'article_id': str(region.article_id)},
            'required_blocks': [{'block_number': 3, 'start': -1, 'end': 1, 'quote': 'wrong', 'text_sha256': '0' * 64}]}]}
    with pytest.raises(ValueError, match='range differs'):
        validate_challenges([{'id': 'one', 'response_path': str(path)}], references)
