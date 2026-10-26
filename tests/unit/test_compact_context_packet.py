"""Exact-source, refusal and diagnostic retention; no scientific accuracy labels."""

import copy
import json

import pytest

from app.evaluation.context_risks import canonical
from app.generation.compact_context_packet import build_compact_packet, expand_compact_context, validate_compact_packet
from app.generation.source_context_packet import build_source_packet, expand_context
from app.records.sources import file_hash
from tests.unit.test_source_context_packet import native_two_pages, packet_fixture, runner_fixture


def test_compact_roundtrip_retains_every_window_and_local_diagnostics(tmp_path):
    diagnostic, _, region = packet_fixture(tmp_path, protected=[1, 3, 5])
    before = copy.deepcopy(diagnostic)
    result = build_compact_packet(diagnostic)
    wire = json.loads(canonical(result['wire']))
    for i, old in enumerate(diagnostic['wire']['contexts'], 1):
        assert expand_compact_context(wire, i) == expand_context(diagnostic, old['context_id'])
    assert diagnostic == before
    assert len(wire['dependencies']) == len(diagnostic['wire']['dependencies'])
    assert {tuple(u) for u in wire['co_preservation_units']} == {
        tuple(int(n[1:]) for n in u) for u in diagnostic['wire']['co_preservation_units']}
    assert result['wire_bytes'] == len(canonical(wire).encode('utf-8')) < diagnostic['wire_bytes']
    assert region.original_pdf_path not in canonical(wire)
    assert not any(result[f] for f in ('generation_performed', 'external_request_constructed', 'network_ready'))
    validate_compact_packet(result, diagnostic)


def test_guard_and_preparation_flags_are_exposed_without_duplicate_quotes(tmp_path):
    blocks = ['Background.\n', 'Conductivity was not measured [12].\n',
        'Samples were prepared in argon.\n', 'Measurements were performed at 25 C.\n', 'Unfinished qualifier']
    diagnostic, _, _ = packet_fixture(tmp_path, blocks=blocks)
    result = build_compact_packet(diagnostic)
    flags = result['wire']['flags']
    assert 'guard:negation_in_block' in flags
    assert 'guard:reported_work_or_citation_in_block' in flags
    assert 'unconfirmed_kind:preparation_procedure' in flags
    for block, original in zip(result['wire']['blocks'], diagnostic['wire']['nodes'], strict=True):
        assert block[5] == original['text']
    assert all(e['scientific_support'] == 'not_evaluated' for n in diagnostic['wire']['nodes'] for e in n['events'])


def test_identical_quotes_with_distinct_offsets_stay_separate_and_full_page_blocked(tmp_path):
    diagnostic, _, _ = packet_fixture(tmp_path, blocks=['Conductivity was measured.\n'] * 3)
    result = build_compact_packet(diagnostic)
    blocks = result['wire']['blocks']
    assert len(blocks) == len({b[3] for b in blocks}) == 3 and len({b[5] for b in blocks}) == 1
    assert result['assembled_complete_pages'] == diagnostic['assembled_complete_pages']
    assert result['decoded_complete_page_matches']
    assert 'complete_source_page_or_assembled_coverage' in result['blocking_reasons']
    assert not result['network_ready']


def test_empty_question_selection_keeps_full_parent_locally_and_refuses(tmp_path):
    diagnostic, parent, _ = packet_fixture(tmp_path, question='Who are the authors?')
    result = build_compact_packet(diagnostic)
    assert not result['wire']['blocks'] and not result['wire']['contexts']
    assert diagnostic['parent'] == parent
    assert 'no_registered_context_nodes' in result['blocking_reasons']
    assert not result['network_ready']


def test_old_insufficiency_and_size_blockers_cannot_be_upgraded_by_compaction(tmp_path):
    diagnostic, _, _ = packet_fixture(tmp_path, baseline_allowed=False)
    result = build_compact_packet(diagnostic)
    assert set(diagnostic['blocking_reasons']) <= set(result['blocking_reasons'])
    assert 'baseline_insufficient_evidence' in result['blocking_reasons']
    assert result['compact_byte_check_passed'] and not result['network_ready']


def test_text_over_ceiling_is_never_clipped_to_pass(tmp_path):
    text = 'Conductivity was measured. ' + 'unbroken text ' * 9000 + '\n'
    diagnostic, _, _ = packet_fixture(tmp_path, blocks=[text, 'Complete tail.\n'])
    result = build_compact_packet(diagnostic)
    assert result['wire_bytes'] > result['byte_ceiling'] == 100000
    assert not result['compact_byte_check_passed']
    assert 'source_packet_over_existing_byte_ceiling' in result['wire']['inherited_blocking_reasons']
    assert 'compact_packet_over_existing_byte_ceiling' in result['blocking_reasons']
    assert result['wire']['blocks'][0][5] == text


@pytest.mark.parametrize('mixed_layer', [False, True])
def test_cross_page_dependency_scope_and_pdf_bytes_are_unchanged(tmp_path, mixed_layer):
    parent, pdf = native_two_pages(tmp_path, mixed_layer=mixed_layer)
    checksum = file_hash(pdf)
    diagnostic = build_source_packet(parent)
    result = build_compact_packet(diagnostic)
    cross = 'unresolved_cross_page_boundary' in result['wire']['dependency_kinds']
    assert cross is (not mixed_layer)
    assert len(result['wire']['dependencies']) == len(diagnostic['wire']['dependencies'])
    assert file_hash(pdf) == checksum


@pytest.mark.parametrize('change', ['text', 'order', 'reference', 'flags', 'dependency', 'unit', 'source',
    'binding', 'size', 'blockers', 'network', 'extra'])
def test_mutated_projection_cannot_pass_diagnostic_validation(tmp_path, change):
    diagnostic, _, _ = packet_fixture(tmp_path, protected=[1, 3, 5])
    result = build_compact_packet(diagnostic)
    wire = result['wire']
    if change == 'text':
        wire['blocks'][0][5] += ' changed'
    elif change == 'order':
        wire['contexts'][0][1].reverse()
    elif change == 'reference':
        wire['contexts'][0][1][0] = 10000
    elif change == 'flags':
        wire['flags'] = []
    elif change == 'dependency':
        wire['dependencies'] = []
    elif change == 'unit':
        wire['co_preservation_units'] = []
    elif change == 'source':
        wire['documents'][0]['text_layer'] = 'foreign'
    elif change == 'binding':
        wire['local_diagnostics_canonical_sha256'] = '0' * 64
    elif change == 'size':
        result['byte_ceiling'] += 1
    elif change == 'blockers':
        result['blocking_reasons'] = []
    elif change == 'network':
        wire['network_ready'] = True
    else:
        wire['unregistered'] = True
    with pytest.raises(ValueError, match='projection'):
        validate_compact_packet(result, diagnostic)


@pytest.mark.parametrize('ref', [0, -1, 100000, True, '1'])
def test_invalid_context_reference_has_visible_failure(tmp_path, ref):
    diagnostic, _, _ = packet_fixture(tmp_path)
    with pytest.raises(ValueError):
        expand_compact_context(build_compact_packet(diagnostic)['wire'], ref)


def compact_fixture(tmp_path, monkeypatch):
    from app.evaluation import compact_context_run as runner

    old, prepared, _, _, challenges, pdf = runner_fixture(tmp_path, monkeypatch)
    captured = tmp_path / 'old_captured'
    old.run(prepared, captured)
    new_prepared = tmp_path / 'new_prepared'
    runner.prepare(captured, challenges, new_prepared)
    return runner, new_prepared, captured, challenges, pdf


def test_frozen_pipeline_preserves_diagnostic_bytes_and_repeats_export_exactly(tmp_path, monkeypatch):
    runner, prepared, parent, _, pdf = compact_fixture(tmp_path, monkeypatch)
    checksum = file_hash(pdf)
    output, first, second = [tmp_path / n for n in ('compact_run', 'first', 'second')]
    result = runner.run(prepared, output)
    assert result['questions'] == result['retention_challenges_passed'] == 4
    assert result['network_ready'] == result['retrieval_calls'] == result['model_calls'] == 0
    assert not result['database_access']
    assert runner.export(output, first) == runner.export(output, second) == result
    for p in output.rglob('*'):
        if p.is_file():
            name = p.relative_to(output)
            assert p.read_bytes() == (first / name).read_bytes() == (second / name).read_bytes()
    for folder in ('method', 'table', 'guard', 'missing'):
        assert (output / folder / 'diagnostics.json').read_bytes() == (parent / folder / 'packet.json').read_bytes()
        packet = json.loads((output / folder / 'packet.json').read_bytes())
        assert (output / folder / 'wire.json').stat().st_size == packet['wire_bytes']
    page = (output / 'review.html').read_text(encoding='utf-8')
    assert page.count('<article data-query>') == 4 and 'method/wire.json' in page and 'type="search"' in page
    metadata = (output / 'metadata_review.html').read_text(encoding='utf-8')
    assert 'href="metadata.json"' in metadata and 'href="report.json"' not in metadata
    assert file_hash(pdf) == checksum
    with pytest.raises(FileExistsError):
        runner.run(prepared, output)


@pytest.mark.parametrize('variant', ['diagnostics', 'source', 'challenge', 'code', 'plan'])
def test_frozen_drift_is_rejected_before_output(tmp_path, monkeypatch, variant):
    runner, prepared, parent, challenges, pdf = compact_fixture(tmp_path, monkeypatch)
    paths = {'diagnostics': parent / 'method/packet.json', 'source': pdf,
        'challenge': challenges, 'plan': prepared / 'plan.json'}
    if variant == 'code':
        monkeypatch.setattr(runner, 'CODE', (*runner.CODE, 'README.md'))
    else:
        paths[variant].write_bytes(b'drift')
    output = tmp_path / 'rejected'
    with pytest.raises(ValueError):
        runner.run(prepared, output)
    assert not output.exists()
