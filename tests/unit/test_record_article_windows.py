"""Constructed bounded-context/source integrity cases, not scientific measurements."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from app.evaluation.context_windows import RegisteredBlocks, TextBlock
from app.evaluation.layout_groups import ProtectedGroup
from app.records.article_scope import export_article_scope
from app.records.article_windows import export_article_windows, plan_page
from app.records.article_windows_html import render_plan
from app.records.pilot import PilotDocument, source_content, write_pilot_packet
from app.records.schema import CandidateBundle, SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_pilot import document, profile

ROOT = Path(__file__).resolve().parents[2]


def page_fixture(tmp_path, blocks=None):
    blocks = blocks or [f'Synthetic paragraph {i}. Complete statement with words.\n' for i in range(7)]
    doc = document(tmp_path, ''.join(blocks))
    region = doc.bundle.regions[0]
    cursor = 0
    registry = []
    for i, text in enumerate(blocks):
        registry.append(TextBlock(cursor, cursor + len(text), (10., 10. + 20 * i, 500., 25. + 20 * i), i))
        cursor += len(text)
    mapping = RegisteredBlocks(str(region.article_id), 1, str(region.text_layer_id), region.page_text_sha256,
                               region.layer_pdf_path, region.layer_pdf_sha256, tuple(registry))
    return region, mapping


def group(mapping, indices):
    selected = [mapping.blocks[i] for i in indices]
    return ProtectedGroup('synthetic_protected_table', mapping.article_id, mapping.page, mapping.layer_id,
                          tuple(b.block_number for b in selected), (selected[0].block_number,),
                          tuple((b.page_start, b.page_end) for b in selected), (1., 1., 500., 500.), ())


def test_every_block_has_one_core_and_neighbors_do_not_create_extra_measurements(tmp_path):
    region, mapping = page_fixture(tmp_path)
    planned = plan_page(region, mapping, [])
    accounted = planned['block_accounting']
    assert [b['block_number'] for b in accounted] == list(range(7))
    assert len({b['block_number'] for b in accounted}) == 7
    assert planned['scientific_extraction'] == 'not_run'
    for context in planned['contexts']:
        assert region.quote[context['start']:context['end']] == context['quote']
        assert context['state'] == 'bounded_context_proposal'
        assert context['dispatch_status'] == 'not_dispatched_offline_only'
        assert context['scientific_adequacy'] == 'not_established'


def test_noncontiguous_protected_members_keep_intervening_blocks_and_context_expands_whole_group(tmp_path):
    region, mapping = page_fixture(tmp_path)
    planned = plan_page(region, mapping, [group(mapping, [2, 4])])
    assert planned['protected_block_intervals'] == [(2, 4)]
    middle = [b for b in planned['block_accounting'] if b['block_number'] in [2, 3, 4]]
    assert len({b['core_context_id'] for b in middle}) == 1
    protected_start, protected_end = mapping.blocks[2].page_start, mapping.blocks[4].page_end
    for context in planned['contexts']:
        if context['start'] < protected_end and context['end'] > protected_start:
            assert context['start'] <= protected_start and context['end'] >= protected_end


def test_overlapping_groups_merge_before_core_partition(tmp_path):
    region, mapping = page_fixture(tmp_path)
    planned = plan_page(region, mapping, [group(mapping, [1, 2]), group(mapping, [2, 4])])
    assert planned['protected_block_intervals'] == [(1, 4)]
    assert len(planned['block_accounting']) == 7


@pytest.mark.parametrize('text,diagnostic', [
    ('Table 1. Synthetic unresolved rows\n', 'caption_table_or_figure_boundaries_unresolved'),
    ('* Synthetic footnote without established table\n', 'unprotected_footnote_or_note_boundary'),
    ('Synthetic damaged unit \ue001\n', 'damaged_or_private_use_formula_text'),
    ('1\n2\n3\n4\n5\n6\n', 'numeric_layout_headers_rows_or_footnotes_unresolved'),
])
def test_unresolved_structural_risk_defers_whole_page_without_dropping_text(tmp_path, text, diagnostic):
    region, mapping = page_fixture(tmp_path, ['Synthetic ordinary prose.\n', text, 'Last ordinary statement.\n'])
    planned = plan_page(region, mapping, [])
    assert planned['planning_state'] == 'deferred_page'
    assert diagnostic in planned['diagnostics']
    assert planned['contexts'] == []
    assert planned['deferred_characters'] == len(region.quote)
    assert len(planned['block_accounting']) == 3


def test_protected_group_does_not_mask_damaged_scientific_notation(tmp_path):
    region, mapping = page_fixture(tmp_path, ['First prose.\n', 'Table 1. unit \ue001\n', '10 20\n', 'Last prose.\n'])
    planned = plan_page(region, mapping, [group(mapping, [1, 2])])
    assert planned['planning_state'] == 'deferred_page'
    assert 'damaged_or_private_use_formula_text' in planned['diagnostics']


def test_full_page_guard_checks_plain_text_despite_json_newline_escaping(tmp_path):
    region, mapping = page_fixture(tmp_path, ['First text.\n', 'Second text.\n'])
    planned = plan_page(region, mapping, [])
    assert len(planned['contexts']) == 1  # Identical windows retain two explicit core units.
    assert len(planned['contexts'][0]['core_units']) == 2
    assert planned['contexts'][0]['diagnostics'] == ['complete_source_page_guard']
    assert all(b['state'] == 'deferred_context' for b in planned['block_accounting'])


def test_oversized_context_is_retained_and_deferred_without_clipping(tmp_path):
    region, mapping = page_fixture(tmp_path)
    planned = plan_page(region, mapping, [], max_chars=10)
    assert all(c['state'] == 'deferred_context' for c in planned['contexts'])
    assert all(len(c['quote']) > 10 for c in planned['contexts'])
    assert len(planned['block_accounting']) == 7


@pytest.mark.parametrize('bad_map', ['mismatch', 'gap', 'invalid_bbox', 'extraction_drift', 'duplicate_block'])
def test_foreign_or_unproven_block_maps_cannot_yield_bounded_contexts(tmp_path, bad_map):
    region, mapping = page_fixture(tmp_path)
    if bad_map == 'mismatch':
        with pytest.raises(ValueError, match='source identity'):
            plan_page(region, replace(mapping, layer_id=str(uuid4())), [])
        return
    if bad_map == 'gap':
        mapping = replace(mapping, blocks=(replace(mapping.blocks[0], page_start=1), *mapping.blocks[1:]))
    elif bad_map == 'invalid_bbox':
        mapping = replace(mapping, blocks=(replace(mapping.blocks[0], bbox=(float('nan'), 1., 2., 3.)), *mapping.blocks[1:]))
    elif bad_map == 'extraction_drift':
        mapping = replace(mapping, diagnostic='registered_page_text_differs_from_current_pdf_extraction')
    else:
        mapping = replace(mapping, blocks=(replace(mapping.blocks[0], block_number=1), *mapping.blocks[1:]))
    planned = plan_page(region, mapping, [])
    assert planned['planning_state'] == 'deferred_page' and not planned['contexts']
    assert planned['page_text'] == region.quote


@pytest.mark.parametrize('change', ['foreign_page', 'wrong_range'])
def test_protected_group_must_bind_exact_registered_source(tmp_path, change):
    region, mapping = page_fixture(tmp_path)
    proposed = group(mapping, [1, 2])
    proposed = replace(proposed, page=2) if change == 'foreign_page' else replace(proposed, page_ranges=((0, 1),))
    with pytest.raises(ValueError, match='different registered page|exact registered blocks'):
        plan_page(region, mapping, [proposed])


def real_scope(tmp_path, second_page_text=None):
    pdf = tmp_path / 'source.pdf'
    with fitz.open() as output:
        page = output.new_page()
        for i in range(7):
            page.insert_text((40, 50 + i * 65), f'Synthetic paragraph {i}. Complete ordinary source text.', fontsize=10)
        if second_page_text is not None:
            page = output.new_page()
            if second_page_text:
                page.insert_text((40, 50), second_page_text, fontsize=10)
        output.save(pdf)
    with fitz.open(pdf) as document_pdf:
        all_text = [page.get_text('text') for page in document_pdf]
        raw = all_text[0]
    checksum = file_hash(pdf)
    # Use the standard source fixture for stable contract fields, then bind the real PDF.
    directory = tmp_path / 'fixture'
    directory.mkdir()
    doc = document(directory, raw)
    data = doc.bundle.regions[0].model_dump()
    data.update(original_pdf_path=str(pdf), original_pdf_sha256=checksum, layer_pdf_path=str(pdf), layer_pdf_sha256=checksum)
    data['region_id'] = source_identity(data)
    regions = []
    for number, page_text in enumerate(all_text, 1):
        if page_text:
            values = data | {'page_number': number, 'page_text': page_text, 'page_text_sha256': text_hash(page_text),
                             'start': 0, 'end': len(page_text), 'quote': page_text, 'quote_sha256': text_hash(page_text)}
            values['region_id'] = source_identity(values)
            regions.append(SourceRegion.model_validate(values))
    region = regions[0]
    bundle = CandidateBundle(run_id=doc.bundle.run_id, created_at=doc.bundle.created_at, producer='synthetic', regions=tuple(regions))
    doc = PilotDocument(region.article_id, 'Synthetic <script>unsafe</script>', None, str(pdf), checksum, len(all_text),
                        tuple(range(1, len(all_text) + 1)), bundle,
                        tuple(f'empty_selected_page:{i}' for i, text in enumerate(all_text, 1) if not text))
    prof = tmp_path / 'profile.json'
    prof.write_text(json.dumps(profile(doc)), encoding='utf-8')
    baseline = tmp_path / 'baseline.json'
    baseline.write_text(json.dumps({'source_fingerprint': 'a' * 64}), encoding='utf-8')
    protocol = tmp_path / 'protocol.md'
    protocol.write_text('Constructed data only.', encoding='utf-8')
    packet = tmp_path / 'packet'
    write_pilot_packet((doc,), prof, packet, protocol_path=protocol, baseline_manifest_path=baseline, source_root=ROOT)
    content = source_content((doc,))
    fingerprint = text_hash(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    sidecar = tmp_path / 'screening.json'
    sidecar.write_text(json.dumps({'source_fingerprint': fingerprint, 'author': 'Constructed assistant fixture',
        'scope': 'Li-Nafion conductivity; preserve author property wording', 'documents': [{
        'article_id': str(region.article_id), 'status': 'proposed_primary', 'rationale': 'Synthetic source task.',
        'inspected_pages': [1], 'evidence': [{'region_id': region.region_id, 'start': 0, 'end': 10, 'quote': raw[:10]}]}]}),
        encoding='utf-8')
    scope = tmp_path / 'scope'
    export_article_scope(packet, sidecar, scope, source_root=ROOT)
    return scope, pdf


def test_real_pdf_offline_exports_repeat_exactly_with_source_only_slices(tmp_path):
    scope, _ = real_scope(tmp_path)
    a, b = tmp_path / 'a', tmp_path / 'b'
    result = export_article_windows(scope, a, source_root=ROOT)
    export_article_windows(scope, b, source_root=ROOT)
    def artifacts(root):
        return {p.relative_to(root).as_posix(): file_hash(p) for p in root.rglob('*') if p.is_file()}
    assert artifacts(a) == artifacts(b)
    assert result['summary']['pdf_pages'] == 1
    assert result['summary']['accounted_blocks'] == result['summary']['registered_blocks'] == 7
    assert result['summary']['bounded_context_proposals'] > 0
    for path in (a / 'contexts').glob('*.json'):
        bundle = CandidateBundle.model_validate_json(path.read_bytes())
        assert not bundle.records and len(bundle.regions) == 1
        region = bundle.regions[0]
        assert region.page_text[region.start:region.end] == region.quote
    with pytest.raises(FileExistsError):
        export_article_windows(scope, a, source_root=ROOT)


def test_guard_checks_complete_other_source_pages_in_full_scope(tmp_path):
    scope, _ = real_scope(tmp_path, second_page_text='Synthetic paragraph 0. Complete ordinary source text.')
    result = export_article_windows(scope, tmp_path / 'out', source_root=ROOT)
    foreign_matches = [c for p in result['pages'] if p['page_number'] == 1 for c in p['contexts']
                       if any(m['page'] == 2 for m in c['complete_page_matches_across_full_scope'])]
    assert foreign_matches
    assert all(c['state'] == 'deferred_context' and 'bundle' not in c for c in foreign_matches)
    assert all('complete_source_page_guard_across_full_scope' in c['diagnostics'] for c in foreign_matches)


def test_empty_original_page_is_retained_with_source_link_and_diagnostic(tmp_path):
    scope, pdf = real_scope(tmp_path, second_page_text='')
    result = export_article_windows(scope, tmp_path / 'out', source_root=ROOT)
    empty = result['pages'][1]
    assert result['summary']['pdf_pages'] == 2
    assert empty['page_number'] == 2 and empty['planning_state'] == 'deferred_page'
    assert empty['diagnostics'] == ['empty_selected_text']
    assert Path(empty['original_pdf_path']) == pdf
    rendered = (tmp_path / 'out/review.html').read_text(encoding='utf-8')
    assert pdf.as_uri() + '#page=2' in rendered


def test_input_drift_during_planning_leaves_no_success_manifest(tmp_path, monkeypatch):
    import app.records.article_windows as planner

    scope, _ = real_scope(tmp_path)
    original = planner.plan_page

    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        path = scope / 'report.json'
        path.write_bytes(path.read_bytes() + b' ')
        return result

    monkeypatch.setattr(planner, 'plan_page', altered)
    with pytest.raises(ValueError, match='Source/input changed during'):
        export_article_windows(scope, tmp_path / 'out', source_root=ROOT)
    assert not (tmp_path / 'out/manifest.json').exists()


@pytest.mark.parametrize('target', ['pdf', 'report', 'bundle', 'escape'])
def test_export_rejects_source_drift_and_artifact_path_escape(tmp_path, target):
    scope, pdf = real_scope(tmp_path)
    if target == 'escape':
        manifest = json.loads((scope / 'manifest.json').read_bytes())
        manifest['outputs']['../source.pdf'] = file_hash(pdf)
        (scope / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    else:
        path = pdf if target == 'pdf' else scope / 'report.json' if target == 'report' else next((scope / 'tasks').rglob('*.json'))
        path.write_bytes(path.read_bytes() + b'tamper')
    with pytest.raises(ValueError, match='changed|escapes'):
        export_article_windows(scope, tmp_path / 'out', source_root=ROOT)


def test_html_keeps_deferred_pages_and_escapes_raw_source(tmp_path):
    region, mapping = page_fixture(tmp_path, ['<script>unsafe</script>\n', 'Second ordinary text.\n'])
    planned = plan_page(region, mapping, [])
    report = {'version': 'synthetic', 'source_fingerprint': 'a' * 64, 'policy': {}, 'summary': {}, 'limitations': [], 'pages': [planned]}
    rendered = render_plan(report)
    assert '<script>unsafe</script>' not in rendered
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in rendered
    assert 'complete_source_page_guard' in rendered
    assert Path(region.original_pdf_path).as_uri() + '#page=1' in rendered
