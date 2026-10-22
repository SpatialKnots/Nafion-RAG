"""Constructed source geometry checks, not independent scientific annotations."""

import copy
import json
from pathlib import Path

import fitz
import pytest

from app.evaluation.context_risks import VERSION, audit_context_risks, canonical
from app.evaluation.context_risks_run import prepare, render, run, summarize
from app.evaluation.source_gaps import VERSION as VISUAL_VERSION
from app.generation.block_context import build_block_context
from app.records.article_windows import plan_page
from app.records.schema import source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_block_preparation import fixture


def visual(region, assets=None, proven=True):
    return {'version': VISUAL_VERSION, 'article_id': str(region.article_id), 'page': region.page_number,
        'layer_id': str(region.text_layer_id), 'text_layer': region.text_layer, 'text_sha256': region.page_text_sha256,
        'original_pdf_path': region.layer_pdf_path, 'original_pdf_sha256': region.layer_pdf_sha256,
        'selected_pdf_path': region.layer_pdf_path, 'selected_pdf_sha256': region.layer_pdf_sha256,
        'coordinate_system': 'unrotated_selected_pdf_pymupdf_points', 'text_geometry_proven': proven,
        'assets': assets or [], 'diagnostics': []}


def asset(box, valid=True, identifier='image0'):
    return {'asset_id': identifier, 'kind': 'raster_image', 'bbox': box, 'geometry_valid': valid,
            'metadata': {}, 'text_overlap': 'none', 'overlapping_line_indices': []}


def parent_fixture(tmp_path, assets=None, **kwargs):
    baseline, plans, region = fixture(tmp_path, **kwargs)
    next(iter(plans.values()))['source_gaps'] = visual(region, assets)
    return build_block_context(baseline, plans), region


@pytest.mark.parametrize('box,relation', [
    ((20, 72, 30, 74), 'intersects_selected_or_protected_geometry'),
    ((20, 1, 30, 3), 'outside_selected_geometry_relevance_unknown'),
    ((500, 70, 500, 70), 'intersects_selected_or_protected_geometry'),
    ((20, 70, 20, 70), 'intersects_selected_or_protected_geometry'),
])
def test_asset_geometry_near_distant_touching_and_degenerate_keeps_relevance_unknown(tmp_path, box, relation):
    parent, _ = parent_fixture(tmp_path, [asset(box)])
    original = copy.deepcopy(parent)
    audit = audit_context_risks(parent)
    window = audit['pages'][0]['windows'][0]
    assert window['asset_relations'] == [{'asset_id': 'image0', 'relation': relation}]
    assert window['state'] == 'diagnostic_window_not_candidate'
    assert parent == original and not audit['selection_changed'] and not audit['admission_changed']
    assert not audit['scientific_exclusion_proven'] and not audit['network_ready']
    assert audit['parent_blocking_reasons'] == parent['blocking_reasons']


@pytest.mark.parametrize('variant', ['invalid', 'unproven', 'registry_diagnostic', 'nonfinite'])
def test_unknown_visual_geometry_never_becomes_distant_exclusion(tmp_path, variant):
    parent, region = parent_fixture(tmp_path)
    planned = parent['pages'][0]['plan']
    raw = visual(region, [asset((20, 1, 30, 3), valid=variant != 'invalid')], proven=variant != 'unproven')
    if variant == 'nonfinite':
        raw['assets'][0]['bbox'] = (float('nan'), 1, 30, 3)
    if variant == 'registry_diagnostic':
        raw['diagnostics'] = ['constructed_unknown_geometry']
    planned['source_gaps'] = raw
    parent = build_block_context(parent['baseline'], {region.region_id: planned})
    audit = audit_context_risks(parent)
    assert audit['pages'][0]['windows'][0]['asset_relations'][0]['relation'] == 'unknown_geometry'


@pytest.mark.parametrize('through_json', [False, True])
def test_protected_geometry_enclosure_reaches_asset_outside_selected_block_boxes(tmp_path, through_json):
    parent, _ = parent_fixture(tmp_path, [asset((2, 400, 4, 402))], protected=[2, 3, 4])
    if through_json:
        parent = json.loads(canonical(parent))
    page = audit_context_risks(parent)['pages'][0]
    window = page['windows'][0]
    assert window['block_numbers'] == [1, 2, 3, 4, 5]
    assert window['asset_relations'][0]['relation'] == 'intersects_selected_or_protected_geometry'
    assert window['protected_groups'] == ['synthetic_protected_table']


@pytest.mark.parametrize('text,kind', [
    ('Table 1. Unresolved caption.\n', 'caption_table_or_figure_boundaries_unresolved'),
    ('* Unresolved footnote.\n', 'note_or_footnote_lexical_trigger'),
    ('Damaged formula \ue001.\n', 'damaged_or_private_use_formula_text'),
    ('1\n2\n3\n4\n5\n6\n', 'numeric_layout_headers_rows_or_footnotes_unresolved'),
])
def test_distant_text_trigger_keeps_exact_evidence_and_unknown_extent(tmp_path, text, kind):
    blocks = [text, 'Background one.\n', 'Background two.\n', 'Conductivity was measured.\n',
              'Background four.\n', 'Background five.\n', 'Background six.\n']
    parent, region = parent_fixture(tmp_path, blocks=blocks)
    page = audit_context_risks(parent)['pages'][0]
    trigger = next(t for t in page['text_triggers'] if t['kind'] == kind)
    assert region.page_text[trigger['start']:trigger['end']] == trigger['quote'] == text
    assert trigger['quote_sha256'] == text_hash(text)
    assert trigger['extent'] == 'trigger_block_only_semantic_extent_unknown'
    window = next(w for w in page['windows'] if 3 in w['core_blocks'])
    assert window['trigger_relations'][0]['relation'] == 'outside_selected_text_extent_unknown'
    assert page['parent_diagnostics'] == parent['pages'][0]['diagnostics']
    assert not page['scientific_exclusion_proven']


def test_numeric_page_aggregate_not_reproduced_per_block_remains_unlocalized(tmp_path):
    parent, _ = parent_fixture(tmp_path, blocks=['1\n', '2\n', '3\n', 'Conductivity.\n', '4\n', '5\n', '6\n'])
    page = audit_context_risks(parent)['pages'][0]
    assert not page['text_triggers']
    assert 'numeric_layout_headers_rows_or_footnotes_unresolved' in page['unlocalized_page_diagnostics']


def test_same_closure_as_old_planner_including_noncontiguous_protection(tmp_path):
    parent, _ = parent_fixture(tmp_path, protected=[2, 4])
    old = parent['proposals'][0]['context']
    new = audit_context_risks(parent)['pages'][0]['windows'][0]
    assert (new['start'], new['end'], new['quote']) == (old['start'], old['end'], old['quote'])


def test_no_literal_anchor_preserves_empty_selection(tmp_path):
    parent, _ = parent_fixture(tmp_path, question='DSC?')
    page = audit_context_risks(parent)['pages'][0]
    assert not page['windows'] and not page['retained_core_block_numbers']


def test_unproven_mapping_has_no_diagnostic_window(tmp_path):
    parent, region = parent_fixture(tmp_path)
    raw = parent['pages'][0]['plan']['mapping']
    from app.evaluation.context_windows import RegisteredBlocks, TextBlock
    mapping = RegisteredBlocks(raw['article_id'], raw['page'], raw['layer_id'], raw['text_sha256'],
        raw['selected_pdf_path'], raw['selected_pdf_sha256'], tuple(TextBlock(**b) for b in raw['blocks']), 'constructed_unproven')
    planned = plan_page(region, mapping, [])
    planned['source_gaps'] = visual(region, proven=False)
    parent = build_block_context(parent['baseline'], {region.region_id: planned})
    page = audit_context_risks(parent)['pages'][0]
    assert page['mapping_unproven'] and not page['windows']


def test_complete_page_union_and_old_refusal_not_upgraded(tmp_path):
    parent, _ = parent_fixture(tmp_path, blocks=[f'Conductivity sample {i}.\n' for i in range(7)], baseline_allowed=False)
    audit = audit_context_risks(parent)
    assert audit['pages'][0]['diagnostic_windows_assemble_complete_page']
    assert audit['parent_assembled_complete_pages'] == parent['assembled_complete_pages']
    assert 'baseline_insufficient_evidence' in audit['parent_blocking_reasons']
    assert 'complete_source_page_or_assembled_coverage' in audit['parent_blocking_reasons']
    assert not audit['network_ready'] and not audit['external_request_constructed'] and not audit['generation_performed']


@pytest.mark.parametrize('field', ['article_id', 'page', 'text_layer', 'text_sha256', 'selected_pdf_sha256', 'coordinate_system'])
def test_foreign_visual_source_identity_is_rejected(tmp_path, field):
    parent, region = parent_fixture(tmp_path)
    planned = parent['pages'][0]['plan']
    planned['source_gaps'][field] = 'foreign'
    parent = build_block_context(parent['baseline'], {region.region_id: planned})
    with pytest.raises(ValueError, match='source identity'):
        audit_context_risks(parent)


def test_parent_output_drift_and_generation_flags_are_rejected(tmp_path):
    parent, _ = parent_fixture(tmp_path)
    parent['wire_bytes'] += 1
    with pytest.raises(ValueError, match='replay'):
        audit_context_risks(parent)
    parent['network_ready'] = True
    with pytest.raises(ValueError, match='no-generation'):
        audit_context_risks(parent)


def real_parent(tmp_path):
    baseline, _, template = fixture(tmp_path)
    path = tmp_path / 'native.pdf'
    with fitz.open() as document:
        page = document.new_page()
        for i in range(7):
            page.insert_text((40, 40 + i * 50), 'Conductivity was measured.' if i == 3 else f'Background item {i}.')
        page.draw_line((10, 10), (20, 10))
        document.save(path)
        text = page.get_text('text')
    checksum = file_hash(path)
    raw = template.model_dump()
    raw.update(original_pdf_path=str(path), layer_pdf_path=str(path), original_pdf_sha256=checksum,
        layer_pdf_sha256=checksum, page_text=text, page_text_sha256=text_hash(text), quote=text,
        quote_sha256=text_hash(text), start=0, end=len(text))
    raw['region_id'] = source_identity(raw)
    region = type(template).model_validate(raw)
    baseline['sources']['pages'] = {'page': region.model_dump(mode='json')}
    baseline['evidence'][0]['text'] = text
    return build_block_context(baseline), path


def prepared_fixture(tmp_path):
    parent, pdf = real_parent(tmp_path)
    native = tmp_path / 'response.json'
    native.write_text(canonical(parent), encoding='utf-8')
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    plan = {'version': VERSION, 'tasks': [{'id': 'constructed', 'response_path': str(native)}], 'historical_source_mappings': []}
    (prepared / 'plan.json').write_text(canonical(plan), encoding='utf-8')
    manifest = {'version': VERSION, 'phase': 'prepared_before_risk_audit', 'inputs': {str(native): file_hash(native),
        str(pdf): file_hash(pdf)}, 'code': {}, 'outputs': {'plan.json': file_hash(prepared / 'plan.json')}}
    (prepared / 'manifest.json').write_text(canonical(manifest), encoding='utf-8')
    return prepared, parent, pdf


def test_real_pdf_frozen_run_replays_and_exports_deterministically_without_mutation(tmp_path):
    prepared, parent, pdf = prepared_fixture(tmp_path)
    before = file_hash(pdf)
    first, second = tmp_path / 'run1', tmp_path / 'run2'
    result = run(prepared, first)
    assert result == run(prepared, second)
    assert result['queries'] == 1 and result['retrieval_calls'] == result['generative_api_calls'] == 0
    assert file_hash(pdf) == before
    for name in ['report.json', 'review.html', 'manifest.json']:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert canonical(parent) == (tmp_path / 'response.json').read_text(encoding='utf-8')
    with pytest.raises(FileExistsError):
        run(prepared, first)


def test_frozen_parent_mutation_fails_before_output(tmp_path):
    prepared, _, _ = prepared_fixture(tmp_path)
    (tmp_path / 'response.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError):
        run(prepared, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_selected_pdf_drift_fails_even_if_binding_is_missing_in_constructed_manifest(tmp_path):
    prepared, _, pdf = prepared_fixture(tmp_path)
    manifest_path = prepared / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    del manifest['inputs'][str(pdf)]
    manifest_path.write_text(canonical(manifest), encoding='utf-8')
    pdf.write_bytes(b'not a PDF')
    with pytest.raises(ValueError, match='hash'):
        run(prepared, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_html_full_text_escaping_scope_and_parent_links(tmp_path):
    parent, _ = parent_fixture(tmp_path, blocks=['Background.\n', 'Background.\n', 'Background.\n',
        'Conductivity <script>alert(1)</script>.\n', 'Background.\n', 'Background.\n', 'Background.\n'])
    results = [{'id': '<script>', 'parent_response_path': str(tmp_path / 'response.json'), 'audit': audit_context_risks(parent)}]
    summary = summarize(results)
    page = render({'summary': summary, 'results': results})
    assert '<script>alert(1)</script>' not in page
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page
    assert 'type="search"' in page and '<table>' in page and '<form' not in page
    assert Path(parent['baseline']['sources']['pages']['page']['original_pdf_path']).as_uri() in page
    assert (tmp_path / 'response.json').as_uri() in page
    assert summary['page_occurrences'] == 1 and not summary['scientific_exclusion_proven']


@pytest.mark.parametrize('variant', ['valid', 'unbound', 'duplicate', 'different_native', 'wrong_phase'])
def test_prepare_binds_all_native_results_and_rejects_scope_drift(tmp_path, monkeypatch, variant):
    import app.evaluation.context_risks_run as runner
    parent, _ = parent_fixture(tmp_path)
    directory = tmp_path / 'native'
    (directory / 'query').mkdir(parents=True)
    response = directory / 'query' / 'response.json'
    response.write_text(canonical(parent), encoding='utf-8')
    rows = [{'id': 'query', 'response': parent}]
    if variant == 'duplicate':
        rows *= 2
    if variant == 'different_native':
        response.write_text('{}', encoding='utf-8')
    (directory / 'report.json').write_text(canonical({'results': rows}), encoding='utf-8')
    bindings = {str(response.resolve()): file_hash(response)} if variant != 'unbound' else {}
    bindings[str((directory / 'report.json').resolve())] = file_hash(directory / 'report.json')
    manifest = {'version': runner.PARENT_VERSION,
        'phase': 'wrong' if variant == 'wrong_phase' else 'read_only_block_api_smoke'}
    monkeypatch.setattr(runner, 'read_archived', lambda *args, **kwargs: (manifest, bindings, []))
    monkeypatch.setattr(runner, 'CODE', ())
    output = tmp_path / 'prepared'
    if variant == 'valid':
        assert prepare(directory, tmp_path / 'snapshot', output)['queries'] == 1
        frozen = json.loads((output / 'plan.json').read_bytes())
        assert frozen['tasks'] == [{'id': 'query', 'response_path': str(response.resolve())}]
        with pytest.raises(FileExistsError):
            prepare(directory, tmp_path / 'snapshot', output)
    else:
        with pytest.raises(ValueError):
            prepare(directory, tmp_path / 'snapshot', output)
        assert not output.exists()
