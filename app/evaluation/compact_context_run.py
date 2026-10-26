"""Frozen offline compact projection, exact diagnostics and deterministic review."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from app.evaluation.context_risks import canonical
from app.evaluation.source_context_packet_run import CODE as PARENT_CODE
from app.evaluation.source_context_packet_run import (
    assess_challenges,
    read,
    validate_native,
    validate_tac,
)
from app.evaluation.source_context_packet_run import render as render_diagnostics
from app.generation.compact_context_packet import VERSION, build_compact_packet, validate_compact_packet
from app.generation.source_context_packet import VERSION as PARENT_VERSION
from app.generation.source_context_packet import expand_context, validate_packet
from app.metadata.bridge_run import render as render_metadata
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import _safe, verify_hashes
from app.records.sources import file_hash

CODE = (*PARENT_CODE, 'app/generation/compact_context_packet.py', 'app/evaluation/compact_context_run.py',
    'scripts/compact_context_packet.py', 'tests/unit/test_compact_context_packet.py',
    'docs/records/compact_context_packet_protocol_v0.1.md')
PREPARED = 'prepared_before_compact_projection'
CAPTURED = 'offline_compact_context_review'


def prepare(parent: Path, challenges: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(parent, PARENT_VERSION, Path.cwd())
    if manifest['phase'] != 'offline_source_packet_review':
        raise ValueError('Compact projection requires complete frozen stage37 results')
    if bindings.get(str(challenges.resolve())) != file_hash(challenges):
        raise ValueError('Compact retention challenges absent from parent bindings')
    report = read(parent / 'report.json')
    tasks = []
    ids: set[str] = set()
    references = read(challenges)
    for row in report['results']:
        native = _safe(parent, row['packet_file'])
        packet = read(native)
        validate_native(packet['parent'])
        validate_packet(packet)
        scores = assess_challenges(row['id'], packet, references)
        if canonical(scores) != canonical(row['challenges']) or any(not c['passed'] for c in scores):
            raise ValueError('Compact parent retention challenges differ or fail')
        ids.update(e['article_id'] for e in packet['parent']['preparation']['baseline']['evidence'])
        tasks.append({'id': row['id'], 'diagnostics_path': str(native)})
    if len(tasks) != 4 or len({t['id'] for t in tasks}) != 4:
        raise ValueError('Compact projection requires all four distinct frozen questions')
    validate_tac(read(parent / 'metadata.json'), ids)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'tasks': tasks,
        'parent_report': str((parent / 'report.json').resolve()), 'metadata': str((parent / 'metadata.json').resolve()),
        'challenges': str(challenges.resolve())})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': PREPARED, 'inputs': bindings, 'code': code,
        'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(tasks), 'documents': len(ids), 'new_compact_outcomes': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != PREPARED or manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Compact prepared code inventory or phase differs')
    plan = read(prepared / 'plan.json')
    paths = [t['diagnostics_path'] for t in plan['tasks']] + [plan[k] for k in ('parent_report', 'metadata', 'challenges')]
    if plan['version'] != VERSION or any(str(Path(p).resolve()) not in bindings for p in paths):
        raise ValueError('Compact plan references unfrozen inputs or wrong version')
    return plan, bindings


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ('parent_wire_bytes', 'wire_bytes', 'source_text_bytes', 'blocks', 'contexts', 'dependencies')
    return {'questions': len(rows), **{k: sum(r['metrics'][k] for r in rows) for k in keys},
        'compact_byte_checks_passed': sum(r['metrics']['compact_byte_check_passed'] for r in rows),
        'assembled_complete_page_occurrences': sum(r['metrics']['assembled_complete_pages'] for r in rows),
        'baseline_evidence_items_preserved': sum(r['baseline_evidence_items_preserved'] for r in rows),
        'retention_challenges': sum(len(r['challenges']) for r in rows),
        'retention_challenges_passed': sum(c['passed'] for r in rows for c in r['challenges']),
        'network_ready': 0, 'database_access': False, 'retrieval_calls': 0, 'embedding_calls': 0, 'model_calls': 0,
        'scientific_accuracy': None, 'tokens_cost_latency_measured': False}


def save_review(output: Path, report: dict[str, Any], packets: dict[str, dict[str, Any]],
                diagnostics_bytes: dict[str, bytes], metadata: dict[str, Any], bindings: dict[str, str]) -> None:
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    diagnostics = {}
    for row in report['results']:
        identifier = row['id']
        _safe(output, identifier).mkdir()
        packet = packets[identifier]
        raw = diagnostics_bytes[identifier]
        # Preserve the complete native diagnostic file byte-for-byte, including
        # its historical parent; no event/guard/visual information is deleted.
        with _safe(output, row['packet_file']).open('xb') as stream:
            stream.write(raw)
        diagnostic = read(_safe(output, row['packet_file']))
        diagnostics[identifier] = diagnostic
        write_json(_safe(output, row['compact_packet_file']), packet)
        with _safe(output, row['wire_file']).open('xb') as stream:
            stream.write(canonical(packet['wire']).encode('utf-8'))
        write_json(_safe(output, row['expanded_file']), {c['context_id']: expand_context(diagnostic, c['context_id'])
            for c in diagnostic['wire']['contexts']})
    write_json(output / 'report.json', report)
    write_json(output / 'metadata.json', metadata)
    links = '<p>' + ' · '.join('<a href="' + html.escape(r['wire_file']) + '">'
        + html.escape(r['id']) + ': точный компактный JSON</a>' for r in report['results']) + '</p>'
    page = render_diagnostics(report, diagnostics).replace('<h1>Пакет исходного контекста</h1>',
        '<h1>Компактный контекст и полная локальная диагностика</h1><p>' + VERSION + '. '
        'Уменьшение JSON не подтверждает научную полноту или допуск к API. '
        'Ниже полный stage37 с исходной диагностикой; компактные файлы доступны отдельно.</p>' + links, 1)
    (output / 'review.html').write_text(page, encoding='utf-8', newline='\n')
    (output / 'metadata_review.html').write_text(render_metadata(metadata).replace('href="report.json"',
        'href="metadata.json"', 1), encoding='utf-8', newline='\n')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': CAPTURED, 'inputs': bindings, 'code': {},
        'outputs': {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}})


def run(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    references = read(Path(plan['challenges']))
    rows = []
    packets, diagnostics_bytes = {}, {}
    ids: set[str] = set()
    for task in plan['tasks']:
        identifier = task['id']
        path = Path(task['diagnostics_path'])
        diagnostic = read(path)
        validate_native(diagnostic['parent'])
        packet = build_compact_packet(diagnostic)
        packets[identifier], diagnostics_bytes[identifier] = packet, path.read_bytes()
        ids.update(e['article_id'] for e in diagnostic['parent']['preparation']['baseline']['evidence'])
        metrics = {k: packet[k] for k in ('parent_wire_bytes', 'wire_bytes', 'source_text_bytes', 'blocks', 'contexts',
            'dependencies', 'byte_ceiling', 'compact_byte_check_passed')}
        metrics['assembled_complete_pages'] = len(packet['assembled_complete_pages'])
        rows.append({'id': identifier, 'metrics': metrics, 'blocking_reasons': packet['blocking_reasons'],
            'baseline_evidence_items_preserved': diagnostic['baseline_evidence_items_preserved'],
            'challenges': assess_challenges(identifier, diagnostic, references),
            'diagnostics_file_sha256': file_hash(path), 'packet_file': identifier + '/diagnostics.json',
            'compact_packet_file': identifier + '/packet.json', 'wire_file': identifier + '/wire.json',
            'expanded_file': identifier + '/expanded_contexts.json'})
    metadata = read(Path(plan['metadata']))
    validate_tac(metadata, ids)
    report: dict[str, Any] = {'version': VERSION, 'summary': summarize(rows), 'results': rows,
        'input_snapshot': {'parent_report': plan['parent_report'], 'sha256': file_hash(Path(plan['parent_report'])),
            'challenges': plan['challenges'], 'challenges_sha256': file_hash(Path(plan['challenges']))},
        'scope_documents': sorted(ids), 'scientific_admission': 'not_evaluated'}
    save_review(output, report, packets, diagnostics_bytes, metadata, bindings)
    return dict(report['summary'])


def export(captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    manifest, bindings = read_frozen(captured, VERSION, Path.cwd())
    report = read(captured / 'report.json')
    if manifest['phase'] != CAPTURED or report['version'] != VERSION or report['summary'] != summarize(report['results']):
        raise ValueError('Compact captured phase/version/summary differs')
    packets, diagnostics_bytes = {}, {}
    for row in report['results']:
        packet = read(_safe(captured, row['compact_packet_file']))
        diagnostic_path = _safe(captured, row['packet_file'])
        diagnostic = read(diagnostic_path)
        validate_compact_packet(packet, diagnostic)
        if file_hash(diagnostic_path) != row['diagnostics_file_sha256']:
            raise ValueError('Compact full diagnostic byte identity differs')
        if _safe(captured, row['wire_file']).read_bytes() != canonical(packet['wire']).encode('utf-8'):
            raise ValueError('Compact actual wire file differs from measured serialization')
        expected = {c['context_id']: expand_context(diagnostic, c['context_id']) for c in diagnostic['wire']['contexts']}
        if read(_safe(captured, row['expanded_file'])) != expected:
            raise ValueError('Compact expanded context file differs')
        packets[row['id']], diagnostics_bytes[row['id']] = packet, diagnostic_path.read_bytes()
    verify_hashes(bindings)
    save_review(output, report, packets, diagnostics_bytes, read(captured / 'metadata.json'), manifest['inputs'])
    return dict(report['summary'])
