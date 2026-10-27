"""Constructed source/reference counterexamples, never independent scientific gold."""

import copy
import json
import socket
from dataclasses import asdict, make_dataclass
from uuid import UUID

import pytest

from app.evaluation.context_risks import canonical
from app.generation.sample_identifiers import audit_identifiers, build_catalog, mentions, validate_catalog
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_condition_applicability import runner_fixture as previous_fixture
from tests.unit.test_record_table_relations import source_fixture


def supplement(number='2', *, shared=False, article=None, pdf=None):
    bundle, page, _, _, _ = source_fixture(shared=shared)
    source = bundle.regions[0]
    data = source.model_dump(mode='json')
    caption = f'Table {number}. Printed sample table\n'
    start = source.end
    text = source.page_text[:start] + caption + source.page_text[start:]
    data.update(article_id=article or str(UUID(int=1)), page_text=text, page_text_sha256=text_hash(text),
        end=start + len(caption), quote=text[source.start:start + len(caption)],
        quote_sha256=text_hash(text[source.start:start + len(caption)]))
    if pdf:
        data.update(original_pdf_path=str(pdf), layer_pdf_path=str(pdf),
            original_pdf_sha256=file_hash(pdf), layer_pdf_sha256=file_hash(pdf))
    data['region_id'] = source_identity(data)
    source = SourceRegion.model_validate(data)
    page = copy.deepcopy(page)
    page.update(article_id=str(source.article_id), page_text=text, page_text_sha256=source.page_text_sha256,
        original_pdf_sha256=source.original_pdf_sha256)
    page['source_gaps']['lines'].append({'block_number': 99, 'page_start': start, 'page_end': start + len(caption),
        'text': caption, 'text_sha256': text_hash(caption), 'bbox': [0, 0, 200, 8]})
    group = page['protected_groups'][0]
    group['block_numbers'].append(99)
    group['caption_blocks'] = [99]
    group['page_ranges'].append([start, start + len(caption)])
    return {'tables': [{'source': source.model_dump(mode='json'), 'page': page}]}


def parents(raw='Sample 2 in Table 2.', *, anchor='', guards=False, origin_state='unknown', article=None, pdf_hash=None):
    source = {'article_id': article or str(UUID(int=1)), 'original_pdf_sha256': pdf_hash or 'a' * 64,
        'page': 1, 'text_layer': 'original', 'text_layer_id': str(UUID(int=2)), 'parent_region_id': 'p'}
    text = raw + ('\n' + anchor if anchor else '')
    context = {'region_id': 'n', 'start': 0, 'end': len(raw), 'text': raw}
    row = {'block_ref': 1, 'node_ref': 'N1', 'node_id': 'n', 'selected': True, 'source': source,
        'source_type': 'constructed', 'start': 0, 'end': len(text), 'text': text, 'text_sha256': text_hash(text),
        'events': [{'event_id': 'e', 'context': context, 'original_guards': ['guard'] if guards else [],
            'original_boundary_diagnostics': [], 'origin_state': origin_state, 'section_kind_proposal': 'unknown'}]}
    common = {'rows': [row], 'selection_changed': False, 'network_ready': False,
        'wire_sha256_unchanged': 'frozen_wire', 'blocking_reasons': ['old_refusal'], 'question': 'Question'}
    return ({**copy.deepcopy(common), 'version': 'condition_applicability_audit_v0.1'},
        {**copy.deepcopy(common), 'version': 'source_origin_audit_v0.1'})


def audit(raw='Sample 2 in Table 2.', *, catalog=None, **kwargs):
    catalog = catalog or build_catalog(supplement())
    kwargs.setdefault('pdf_hash', catalog['tables'][0]['original_pdf_sha256'])
    args = parents(raw, **kwargs)
    return audit_identifiers(*args, catalog), catalog, args


def bindings(result):
    return result['rows'][0]['events'][0]['bindings']


def test_exact_sample_table_figure_and_unexpanded_list_spans():
    raw = 'Sample 02 in Table 2; samples 1–3; образец 2, рис. 3; образцов 4 и 5; sample 1-3.'
    hits = mentions(raw, 8)
    assert [h['identifier'] for h in hits['samples']] == ['02', '2']
    assert len(hits['sample_lists_or_ranges']) == 3
    for group in hits.values():
        assert all(raw[h['start'] - 8:h['end'] - 8] == h['text'] for h in group)


def test_catalog_reuses_all_rows_and_printed_semantics_without_model_history():
    catalog = build_catalog(supplement())
    assert len(catalog['tables'][0]['rows']) == 4
    assert not catalog['historical_model_candidates_applied']
    validate_catalog(catalog)
    assert catalog['tables'][0]['semantic_scope'] == 'printed_plasticiser_column_not_membrane_or_measurement_environment'


def test_same_event_table_scope_links_exact_row_only():
    result, _, _ = audit('Sample 4 in Table 2.')
    binding = bindings(result)[0]
    assert binding['state'] == 'literal_row_identity_proposal'
    assert binding['candidates'][0]['row']['printed_plasticiser_composition']['text'] == 'SL'
    assert binding['sample_identity'] == binding['per_result_method_applicability'] == 'not_established'
    assert not binding['condition_transfer_performed']


def test_numbering_anchor_is_required_without_explicit_table_reference():
    result, _, _ = audit('Sample 2.')
    assert bindings(result)[0]['state'] == 'unresolved'
    result, _, _ = audit('Sample 2.', anchor='Sample numbering follows Table 2.')
    assert bindings(result)[0]['state'] == 'literal_row_identity_proposal'
    assert bindings(result)[0]['scope_basis'] == 'article_numbering_anchor'


@pytest.mark.parametrize('raw,kwargs,reason', [
    ('Sample 2 in Table 1.', {}, 'missing_or_multiple_same_article_sample_rows'),
    ('Sample 02 in Table 2.', {}, 'missing_or_multiple_same_article_sample_rows'),
    ('Sample 9 in Table 2.', {}, 'missing_or_multiple_same_article_sample_rows'),
    ('Sample 2 in Table 2.', {'article': str(UUID(int=99))}, 'missing_or_multiple_same_article_sample_rows'),
    ('Sample 2 in Table 2.', {'pdf_hash': 'b' * 64}, 'missing_or_multiple_same_article_sample_rows'),
    ('Sample 2 in Table 2.', {'guards': True}, 'original_guards_or_boundaries_preserved'),
    ('Sample 2 in Table 2.', {'origin_state': 'reported_work_cue_proposal'}, 'reported_cited_or_ambiguous_origin'),
    ('Sample 2 and sample 3 in Table 2.', {}, 'multiple_samples_in_event_do_not_identify_one_measurement'),
])
def test_wrong_missing_foreign_reported_and_mixed_references_abstain(raw, kwargs, reason):
    result, _, _ = audit(raw, **kwargs)
    assert bindings(result) and reason in bindings(result)[0]['abstention_reasons']
    assert bindings(result)[0]['state'] != 'literal_row_identity_proposal'


def test_repeated_ids_in_two_tables_need_unique_explicit_scope():
    tables = supplement()['tables'] + supplement('3')['tables']
    catalog = build_catalog({'tables': tables})
    result, _, _ = audit('Sample 2 in Table 2 and Table 3.', catalog=catalog)
    assert len(bindings(result)[0]['candidates']) == 2
    assert bindings(result)[0]['state'] == 'unresolved_with_row_candidate'
    result, _, _ = audit('Sample 2 in Table 3.', catalog=catalog)
    assert bindings(result)[0]['state'] == 'literal_row_identity_proposal'


def test_same_table_duplicate_row_and_shared_layout_abstain():
    registered = supplement()
    catalog = build_catalog({'tables': registered['tables'] * 2})
    result, _, _ = audit(catalog=catalog)
    assert len(bindings(result)[0]['candidates']) == 2
    result, _, _ = audit('Sample 3 in Table 2.', catalog=build_catalog(supplement(shared=True)))
    assert 'sample_row_layout_or_printed_composition_unresolved' in bindings(result)[0]['abstention_reasons']


def test_catalog_forgery_and_parent_changes_are_visible_errors():
    result, catalog, args = audit()
    before = copy.deepcopy(args)
    assert not result['selection_changed'] and result['blocking_reasons'] == args[0]['blocking_reasons']
    assert args == before
    catalog['tables'][0]['rows'][0]['identifier'] = 'forged'
    with pytest.raises(ValueError, match='exact row label'):
        audit_identifiers(*args, catalog)
    args[1]['rows'][0]['text'] += 'forged'
    with pytest.raises(ValueError, match='parent block'):
        audit_identifiers(*args, build_catalog(supplement()))


def runner_fixture(tmp_path, monkeypatch):
    from app.evaluation import sample_identifiers_run as runner
    from app.records.extraction import write_json

    previous, prepared, _, _, pdf = previous_fixture(tmp_path, monkeypatch)
    parent = tmp_path / 'stage44'
    previous.run(prepared, parent)
    report = json.loads((parent / 'report.json').read_bytes())
    first = json.loads((parent / report['results'][0]['applicability_file']).read_bytes())
    article = first['rows'][0]['source']['article_id']
    registered = supplement(article=article, pdf=pdf)
    history = tmp_path / 'history'
    history.mkdir()
    write_json(history / 'report.json', {'source_only_test': True})
    monkeypatch.setattr(runner, 'source_supplement', lambda h, w: (registered,
        {str((h / 'report.json').resolve()): file_hash(h / 'report.json')}))
    checks = tmp_path / 'identifier_checks.json'
    write_json(checks, {'version': 'sample_identifier_checks_v0.1',
        'origin': 'assistant_source_development_before_new_identifier_outcomes', 'independent_human_confirmation': False,
        'parent_report_sha256': file_hash(parent / 'report.json'), 'history_report_sha256': file_hash(history / 'report.json'),
        'cases': [{'id': row['id'], 'task_id': row['id'], 'kind': 'unchanged_source_and_refusals'} for row in report['results']]})
    destination = tmp_path / 'prepared45'
    runner.prepare(parent, history, history, checks, destination)
    return runner, destination, parent, checks, pdf


def test_offline_run_and_two_exports_preserve_all_parents_and_supplement(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Identifier tests forbid network connections')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    runner, prepared, parent, _, pdf = runner_fixture(tmp_path, monkeypatch)
    checksum = file_hash(pdf)
    captured, first, second = [tmp_path / name for name in ('run45', 'review45', 'repeat45')]
    result = runner.execute(prepared, captured)
    assert result['checks_passed'] == result['questions'] == 4
    assert result['model_calls'] == result['network_ready'] == result['retrieval_calls'] == 0
    assert runner.execute(captured, first, export=True) == runner.execute(captured, second, export=True) == result
    for p in captured.rglob('*'):
        if p.is_file():
            assert p.read_bytes() == (first / p.relative_to(captured)).read_bytes() == (second / p.relative_to(captured)).read_bytes()
    old, new = [json.loads((p / 'report.json').read_bytes()) for p in (parent, captured)]
    for a, b in zip(old['results'], new['results'], strict=True):
        for key in runner.FILES:
            assert (parent / a[key]).read_bytes() == (captured / b[key]).read_bytes()
    assert file_hash(pdf) == checksum
    with pytest.raises(FileExistsError):
        runner.execute(prepared, captured)


@pytest.mark.parametrize('variant', ['code', 'source', 'checks', 'pdf', 'supplement'])
def test_frozen_drift_fails_before_output(tmp_path, monkeypatch, variant):
    runner, prepared, parent, checks, pdf = runner_fixture(tmp_path, monkeypatch)
    if variant == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        report = json.loads((parent / 'report.json').read_bytes())
        row = next(r for r in report['results'] if r['id'] == 'method')
        target = {'source': parent / row['applicability_file'], 'checks': checks, 'pdf': pdf,
            'supplement': prepared / 'supplement.json'}[variant]
        assert target.is_file()
        target.write_bytes(b'drift')
    out = tmp_path / 'rejected45'
    with pytest.raises(ValueError):
        runner.execute(prepared, out)
    assert not out.exists()


def test_html_escapes_source_and_separates_supplement():
    from app.evaluation.sample_identifiers_run import FILES, render

    result, catalog, _ = audit('Sample 2 in Table 2. <script>alert(1)</script>')
    source = catalog['tables'][0]['source']
    result['rows'][0]['source']['parent_region_id'] = 'p'
    row = {'id': 'q', **{k: 'q/' + k + '.json' for k in FILES}, 'identifiers_file': 'q/identifiers.json'}
    diagnostic = {'parent': {'audit': {'pages': [{'source': {**source, 'region_id': 'p'}}]}}}
    text = render({'version': 'test', 'summary': {}, 'input_snapshot': {}, 'results': [row]}, {'q': result},
        {'q': {'diagnostics_file': canonical(diagnostic).encode()}}, catalog)
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in text and '<script>alert(1)</script>' not in text
    assert 'data-supplement' in text and 'metadata_review.html' in text and 'file:///' in text and '<form' not in text


def test_catalog_reference_spans_are_bound_before_outcomes():
    from app.evaluation.sample_identifiers_run import assess_catalog

    registered = supplement()
    catalog = build_catalog(registered)
    table = catalog['tables'][0]
    row = table['rows'][1]
    checks = {'catalog_checks': [{'id': 'row2', 'region_id': table['source']['region_id'], 'table_identifier': '2',
        'sample_identifier': '2', 'expected': {key: {k: row[key][k] for k in ('start', 'end', 'text')}
            for key in ('sample', 'printed_plasticiser_composition', 'printed_composition_header', 'printed_basis')}}]}
    assert assess_catalog(checks, registered) == []
    assert assess_catalog(checks, registered, catalog) == [{'id': 'row2', 'passed': True}]
    checks['catalog_checks'][0]['expected']['sample']['text'] = 'forged'
    with pytest.raises(ValueError, match='exact source span'):
        assess_catalog(checks, registered)


def test_source_only_recapture_reports_old_runtime_drift_but_requires_exact_sources(tmp_path, monkeypatch):
    from app.evaluation import sample_identifiers_run as runner
    from app.evaluation.context_windows import RegisteredBlocks
    from app.records.extraction import write_json

    pdf = tmp_path / 'source.pdf'
    pdf.write_bytes(b'constructed hash-bound PDF fixture; extraction is mocked below')
    registered = supplement(pdf=pdf)['tables'][0]
    source, page = registered['source'], registered['page']
    mapping = RegisteredBlocks(source['article_id'], source['page_number'], source['text_layer_id'],
        source['page_text_sha256'], str(pdf.resolve()), source['layer_pdf_sha256'], ())
    page['mapping'] = asdict(mapping)
    gaps_type = make_dataclass('ConstructedGaps', [('text_geometry_proven', bool), ('lines', list)])
    observed = []

    def read_blocks(*args):
        observed.append('blocks')
        return mapping

    def read_lines(*args):
        observed.append('lines')
        return gaps_type(True, page['source_gaps']['lines'])

    monkeypatch.setattr(runner, 'read_registered_blocks', read_blocks)
    monkeypatch.setattr(runner, 'read_source_gaps', read_lines)
    history, windows = tmp_path / 'history', tmp_path / 'windows'
    history.mkdir()
    windows.mkdir()
    runtime = tmp_path / 'pyproject.toml'
    runtime.write_text('old runtime', encoding='utf-8')
    digest = file_hash(runtime)
    runtime.write_text('current runtime', encoding='utf-8')
    write_json(windows / 'report.json', {'pages': [page]})
    write_json(history / 'report.json', {'sources': {source['region_id']: source},
        'relation_map': {'source_region_id': source['region_id']}})
    write_json(history / 'manifest.json', {'version': 'records_table_relations_v0.1', 'inputs': {
        str(runtime.resolve()): digest, str(pdf.resolve()): file_hash(pdf),
        str((windows / 'report.json').resolve()): file_hash(windows / 'report.json')},
        'code': {}, 'outputs': {'report.json': file_hash(history / 'report.json')}})
    result, bindings = runner.source_supplement(history, windows)
    assert result['historical_full_run_replayed'] is False
    assert result['current_pdf_text_blocks_and_lines_reverified'] is True
    assert [x['path'] for x in result['historical_binding_mismatches']] == [str(runtime.resolve())]
    assert bindings[str(runtime.resolve())] == file_hash(runtime) and observed == ['blocks', 'lines']
    (windows / 'report.json').write_bytes(b'changed geometry')
    with pytest.raises(ValueError, match='historical hash'):
        runner.source_supplement(history, windows)
