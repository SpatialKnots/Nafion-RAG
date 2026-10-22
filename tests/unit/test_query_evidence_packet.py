"""Constructed query/source closure cases; no independent scientific labels or network."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from app.evaluation.answer_trace import PreparationComplete
from app.evaluation.query_packet import aligned_pages, build_packet
from app.evaluation.query_packet_run import QUESTIONS, CaptureOnlyProvider, export, load, prepare
from app.generation.providers import Evidence
from app.records.protocol_association import AssociationReply
from app.records.protocol_association_run import load as load_associations
from app.records.protocol_association_run import run as run_associations
from app.records.schema import SourceRegion, source_identity, text_hash
from app.records.sources import file_hash
from tests.unit.test_record_protocol_association import case, native, reply, storage


def full_page(c):
    data = c['source'].copy()
    data.update(start=0, end=len(data['page_text']), quote=data['page_text'], quote_sha256=text_hash(data['page_text']))
    data['region_id'] = source_identity(data)
    return SourceRegion.model_validate(data)


def evidence(c, text=None, citation='E1'):
    s = c['source']
    return Evidence(citation, s['article_id'], str(UUID(int=60)), 'Constructed <script> title', None,
                    s['page_number'], s['page_number'], 'body', s['quote'] if text is None else text,
                    1.0, 'constructed_exact', {}, {})


def packet(c, e=None, model_reply=None, **kwargs):
    e = evidence(c) if e is None else e
    return build_packet('Constructed question about conductivity?', [e], {e.chunk_id: c['source']['text_layer']},
                        [(c, reply(c) if model_reply is None else model_reply)], page_sources={e.chunk_id: [full_page(c)]}, **kwargs)


def test_full_block_in_baseline_keeps_every_original_field_and_adds_offsets_without_duplicate_text():
    c = case()
    e = evidence(c, full_page(c).page_text)
    original = asdict(e)
    p = packet(c, e)
    assert p['baseline_evidence'] == [original] and not p['attachments']
    assert p['contexts'][0]['state'] == 'full_block_already_in_baseline'
    assert p['contexts'][0]['context_citation_id'] == 'E1'
    assert p['baseline_items_preserved'] == 1 and p['added_characters'] == 0
    assert p['wire']['evidence'][0]['text'] == e.text
    assert p['scientific_admission'] == 'not_evaluated'
    assert asdict(e) == original


def test_partial_baseline_gets_whole_block_including_unsupported_clipped_tail_and_old_guards():
    c = case('Conductivity was not measured. Unsupported clipped qualifier')
    e = evidence(c, c['sentences'][0]['span']['text'])
    p = packet(c, e, reply(c, 'unknown'))
    assert p['attachments'][0]['text'] == c['source']['quote']
    assert p['attachments'][0]['citation_id'] == 'P1'
    assert p['contexts'][0]['resolved_proposals'][0]['proposal']['property_kind'] == 'unknown'
    assert p['contexts'][0]['sentences'] == c['sentences']
    assert p['contexts'][0]['sentences'][-1]['stage27_event']['state'] == 'incomplete_source'
    assert p['wire']['unverified_association_contexts'][0]['stage27_diagnostics'][0]['guards']


def test_attached_citation_ids_do_not_collide_and_unicode_offsets_restore_exact_text():
    c = case('Through-plane lithium conductivity was measured at 25 ◦C. Clipped tail')
    e = evidence(c, c['sentences'][0]['span']['text'], citation='P1')
    p = packet(c, e)
    assert p['attachments'][0]['citation_id'] == 'P2'
    ctx = p['contexts'][0]
    for original, offsets in zip(c['sentences'], ctx['sentence_offsets_in_context_evidence'], strict=True):
        assert p['attachments'][0]['text'][offsets['start']:offsets['end']] == original['span']['text']
    assert ctx['source']['start'] == 17


@pytest.mark.parametrize('variant', ['article', 'page', 'layer', 'missing_layer', 'missing_registry', 'layer_id',
                                     'pdf_hash', 'page_text_drift', 'derived', 'partial_target'])
def test_unproven_binding_preserves_baseline_without_attaching_or_fuzzy_matching(variant):
    c = case()
    e, layer = evidence(c), c['source']['text_layer']
    page = full_page(c)
    if variant == 'article':
        e = replace(e, article_id=str(UUID(int=999)))
    elif variant == 'page':
        e = replace(e, page_start=e.page_start + 1, page_end=e.page_end + 1)
    elif variant == 'layer':
        layer = 'ocr'
    elif variant == 'derived':
        e = replace(e, source_type='table_derived')
    elif variant == 'partial_target':
        e = replace(e, text=e.text.replace('was measured', 'was  measured'))
    elif variant in {'layer_id', 'pdf_hash', 'page_text_drift'}:
        data = page.model_dump()
        if variant == 'layer_id':
            data['text_layer_id'] = UUID(int=999)
        elif variant == 'pdf_hash':
            data.update(original_pdf_sha256='f' * 64, layer_pdf_sha256='f' * 64)
        else:
            text = data['page_text'] + ' Changed page.'
            data.update(page_text=text, quote=text, page_text_sha256=text_hash(text), quote_sha256=text_hash(text), end=len(text))
        data['region_id'] = source_identity(data)
        page = SourceRegion.model_validate(data)
    layers = {} if variant == 'missing_layer' else {e.chunk_id: layer}
    sources = {} if variant == 'missing_registry' else {e.chunk_id: [page]}
    p = build_packet('Question?', [e], layers, [(c, reply(c))], page_sources=sources)
    assert p['baseline_evidence'] == [asdict(e)] and not p['contexts'] and not p['attachments']
    assert p['diagnostics'][0]['state'] == 'not_anchored'


def test_repeated_sentence_on_multiple_pages_is_not_assigned_to_an_arbitrary_occurrence():
    c = case()
    first = full_page(c)
    data = first.model_dump()
    data['page_number'] += 1
    data['region_id'] = source_identity(data)
    second = SourceRegion.model_validate(data)
    e = replace(evidence(c), text=first.page_text.strip() + '\n' + second.page_text.strip(), page_end=second.page_number)
    assert len(aligned_pages(e, [first, second], first.text_layer)) == 2
    p = build_packet('Question?', [e], {e.chunk_id: first.text_layer}, [(c, reply(c))],
                     page_sources={e.chunk_id: [first, second]})
    assert not p['contexts']
    assert 'target_occurrence_ambiguous_in_baseline' in p['diagnostics'][0]['reasons']


def test_multpage_registry_gap_never_guesses_where_a_target_occurs():
    c = case()
    e = replace(evidence(c), page_end=c['source']['page_number'] + 1)
    p = packet(c, e)
    assert not p['contexts'] and p['baseline_evidence'][0]['text'] == e.text


def test_unknown_no_cue_and_unmatched_queries_do_not_drop_baseline_evidence():
    c = case()
    e = replace(evidence(c), text='Unrelated raw source without a literal cue.')
    p = packet(c, e)
    assert p['baseline_items_preserved'] == 1 and p['wire']['evidence'][0]['text'] == e.text
    assert not p['contexts']
    empty = build_packet('Question?', [], {}, [(c, reply(c))])
    assert empty['wire']['evidence'] == [] and not empty['contexts']


@pytest.mark.parametrize('variant', ['duplicate_citations', 'empty_citation', 'duplicate_cases', 'foreign_reference'])
def test_packet_contract_errors_are_not_silently_repaired(variant):
    c, e = case(), evidence(case())
    cases, items = [(c, reply(c))], [e]
    if variant == 'duplicate_citations':
        items.append(e)
    elif variant == 'empty_citation':
        items[0] = replace(e, citation_id='')
    elif variant == 'duplicate_cases':
        cases.append((c, reply(c)))
    else:
        data = reply(c).model_dump(mode='json')
        data['associations'][0]['method_sentence_ids'] = ['foreign']
        cases = [(c, AssociationReply.model_validate(data))]
    with pytest.raises(ValueError):
        build_packet('Question?', items, {e.chunk_id: c['source']['text_layer']}, cases,
                     page_sources={e.chunk_id: [full_page(c)]})


def test_byte_budget_marks_full_packet_without_truncation_and_wire_omits_local_paths():
    c, e = case(), evidence(case())
    p = packet(c, e, max_bytes=1)
    assert p['budget_status'] == 'over_budget' and p['wire_bytes'] > 1
    assert p['wire']['evidence'][0]['text'] == e.text
    wire = json.dumps(p['wire'], ensure_ascii=False)
    assert c['source']['original_pdf_path'] not in wire
    assert 'original_pdf_path' not in wire and 'layer_pdf_path' not in wire
    assert p['contexts'][0]['source']['original_pdf_path'] == c['source']['original_pdf_path']
    with pytest.raises(ValueError):
        packet(c, max_bytes=0)


def test_capture_only_provider_never_delegates_to_network_generation():
    with patch('app.generation.providers.OpenAIAnswerProvider.generate', side_effect=AssertionError('Network generation called')):
        with pytest.raises(PreparationComplete):
            CaptureOnlyProvider().generate('Question?', [evidence(case())])


def prepared_storage(tmp_path):
    association_prepared = storage(tmp_path)
    plan, _ = load_associations(association_prepared)
    responses = [(native(c), 'constructed') for c in plan['cases']]
    run_dir = tmp_path / 'association_run'
    with patch('app.records.protocol_association_run.send_openai_request', side_effect=responses):
        run_associations(association_prepared, run_dir, api_key='constructed-test-only')
    output = tmp_path / 'packet_prepared'
    with patch('app.evaluation.query_packet_run.answer_question', side_effect=AssertionError('Preparation captured database')):
        summary = prepare(association_prepared, run_dir, output)
    assert summary['new_model_calls'] == 0 and summary['questions'] == 4
    return output


def captured_storage(tmp_path, prepared):
    plan, _ = load(prepared)
    c = plan['associations'][0]['case']
    page = full_page(c)
    e = evidence(c, page.page_text)
    rows = [{**q, 'baseline_status': 'insufficient_evidence' if i == 3 else 'context_prepared_before_generation',
             'trace': {'evidence': [asdict(e)], 'metadata': {'constructed_trace': True}},
             'sources': {'chunk_layers': {e.chunk_id: page.text_layer}, 'pages': {'page': page.model_dump(mode='json')},
                         'diagnostics': [], 'chunks': {}},
             'current_prompt': CaptureOnlyProvider()._user_prompt(q['question'], [e])}
            for i, q in enumerate(plan['questions'])]
    directory = tmp_path / 'captured'
    directory.mkdir()
    (directory / 'capture.json').write_text(json.dumps({'version': plan['version'], 'queries': rows}), encoding='utf-8')
    (directory / 'manifest.json').write_text(json.dumps({'version': plan['version'],
        'phase': 'read_only_current_context_captured', 'inputs': {}, 'code': {},
        'outputs': {'capture.json': file_hash(directory / 'capture.json')}}), encoding='utf-8')
    return directory


def test_frozen_export_preserves_all_queries_gates_and_baseline_and_is_exclusive_deterministic_and_escaped(tmp_path):
    prepared = prepared_storage(tmp_path)
    captured = captured_storage(tmp_path, prepared)
    first, repeat = tmp_path / 'first', tmp_path / 'repeat'
    summary = export(prepared, captured, first)
    export(prepared, captured, repeat)
    assert summary['questions'] == 4 and summary['baseline_evidence_items'] == 4
    assert summary['new_model_calls'] == summary['network_eligible_packets'] == 0
    for p in first.iterdir():
        assert p.read_bytes() == (repeat / p.name).read_bytes()
    rows = json.loads((first / 'report.json').read_bytes())['queries']
    assert all(r['trace']['evidence'] == r['packet']['baseline_evidence'] for r in rows)
    assert rows[-1]['baseline_status'] == 'insufficient_evidence'
    assert all(r['packet']['scope']['candidate_complete_pages'] for r in rows)
    html = (first / 'review.html').read_text(encoding='utf-8')
    assert html.count('class="query"') == 4 and 'id="q"' in html and '<form' not in html
    assert '&lt;script&gt;' in html and 'Constructed <script>' not in html
    with pytest.raises(FileExistsError):
        export(prepared, captured, first)


@pytest.mark.parametrize('variant', ['phase', 'code', 'question', 'method', 'input'])
def test_frozen_plan_drift_stops_before_current_context_capture(tmp_path, variant):
    prepared = prepared_storage(tmp_path)
    path = prepared / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    if variant == 'phase':
        manifest['phase'] = 'captured'
    elif variant == 'code':
        manifest['code'][str(Path('app/evaluation/query_packet.py').resolve())] = 'f' * 64
    elif variant == 'input':
        manifest['inputs'][str(Path('app/records/protocol_association.py').resolve())] = 'f' * 64
    else:
        p = prepared / 'plan.json'
        plan = json.loads(p.read_bytes())
        if variant == 'question':
            plan['questions'][0]['question'] = 'Changed question'
        else:
            plan['method'] = 'exact'
        p.write_text(json.dumps(plan), encoding='utf-8')
        manifest['outputs']['plan.json'] = file_hash(p)
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        load(prepared)


@pytest.mark.parametrize('variant', ['hash', 'phase', 'lost_query'])
def test_export_rejects_changed_or_incomplete_current_context_capture(tmp_path, variant):
    prepared = prepared_storage(tmp_path)
    captured = captured_storage(tmp_path, prepared)
    path = captured / 'manifest.json'
    manifest = json.loads(path.read_bytes())
    if variant == 'hash':
        (captured / 'capture.json').write_bytes(b'changed')
    elif variant == 'phase':
        manifest['phase'] = 'other'
    else:
        p = captured / 'capture.json'
        data = json.loads(p.read_bytes())
        data['queries'].pop()
        p.write_text(json.dumps(data), encoding='utf-8')
        manifest['outputs']['capture.json'] = file_hash(p)
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        export(prepared, captured, tmp_path / 'no_export')


def test_input_objects_are_not_mutated_by_packet_assembly():
    c = case('Conductivity was measured. Remaining clipped source')
    before = copy.deepcopy(c)
    packet(c, evidence(c, c['sentences'][0]['span']['text']))
    assert c == before
    assert len(QUESTIONS) == 4


def test_missing_page_registry_remains_network_ineligible_even_without_a_complete_page_match(tmp_path):
    prepared = prepared_storage(tmp_path)
    captured = captured_storage(tmp_path, prepared)
    p = captured / 'capture.json'
    data = json.loads(p.read_bytes())
    data['queries'][0]['sources']['pages'] = {}
    p.write_text(json.dumps(data), encoding='utf-8')
    m = captured / 'manifest.json'
    manifest = json.loads(m.read_bytes())
    manifest['outputs']['capture.json'] = file_hash(p)
    m.write_text(json.dumps(manifest), encoding='utf-8')
    output = tmp_path / 'no_registry_export'
    export(prepared, captured, output)
    row = json.loads((output / 'report.json').read_bytes())['queries'][0]
    assert not row['packet']['scope']['candidate_complete_pages']
    assert not row['packet']['scope']['page_registry_proven'] and not row['packet']['scope']['network_eligible']
    assert row['packet']['baseline_evidence'] == row['trace']['evidence']
