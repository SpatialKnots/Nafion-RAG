"""Frozen offline comparison of a necessary-mention guard; no database or API access."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.evaluation.query_packet_run import load as load_packets
from app.generation.providers import Evidence
from app.generation.query_qualifiers import VERSION, assess_query_qualifiers
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.sources import file_hash

FIXTURE = Path('docs/records/query_qualifiers_cases_v0.1.json')
CODE = ('app/generation/query_qualifiers.py', 'app/evaluation/query_qualifiers_run.py',
        'scripts/query_qualifiers.py', 'tests/unit/test_query_qualifiers.py',
        'docs/records/query_qualifiers_protocol_v0.1.md', str(FIXTURE))


def constructed_evidence(raw: dict[str, Any], index: int) -> Evidence:
    """Explicit synthetic fixture adapter; never creates scientific source records."""
    return Evidence(f'C{index}', raw['article_id'], f'constructed-chunk-{index}', 'Constructed development fixture',
                    None, 1, 1, 'constructed_fixture', raw['text'], 0.0, 'constructed', {}, {})


def validate_cases(cases: list[dict[str, Any]]) -> None:
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Qualifier constructed case IDs must be unique and nonempty')
    for case in cases:
        if (not case['id'].strip() or not case['question'].strip()
                or not isinstance(case['baseline_allowed'], bool) or not isinstance(case['expected_candidate_allowed'], bool)):
            raise ValueError('Qualifier constructed question/decision contract is invalid')
        if case['expected_candidate_allowed'] and not case['baseline_allowed']:
            raise ValueError('Constructed reference cannot upgrade a baseline refusal')


def prepare(packets: Path, captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load_packets(packets)
    manifest, additions = read_frozen(captured, plan['version'], Path.cwd())
    if manifest['phase'] != 'read_only_current_context_captured':
        raise ValueError('Qualifier comparison requires unchanged stage29 context capture')
    if any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Qualifier inherited bindings conflict')
    bindings.update(additions)
    current = json.loads((captured / 'capture.json').read_bytes())
    if [(q['id'], q['question']) for q in current['queries']] != [(q['id'], q['question']) for q in plan['questions']]:
        raise ValueError('Qualifier inherited question inventory differs')
    cases = json.loads(FIXTURE.read_bytes())
    validate_cases(cases)
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'observed_queries': current['queries'], 'constructed_cases': cases,
        'article_metadata': {}, 'article_metadata_status': 'not_captured_in_stage29; no offline invention or new lookup',
        'exposure': 'Exposed observations and developer-authored constructed necessary-mention references; no independent gold.',
        'new_model_calls': 0})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_qualifier_comparison',
        'inputs': bindings, 'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'observed_questions': len(current['queries']), 'constructed_cases': len(cases), 'new_model_calls': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    declared = json.loads((prepared / 'manifest.json').read_bytes())
    hashes: dict[str, str] = {}
    entries = [*declared['inputs'].items(), *declared['code'].items(),
               *((str((prepared / n).resolve()), h) for n, h in declared['outputs'].items())]
    for name, checksum in entries:
        key = str(Path(name).resolve())
        if key in hashes and hashes[key] != checksum:
            raise ValueError('Qualifier frozen manifest has conflicting input/code/output hashes')
        hashes[key] = checksum
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_qualifier_comparison' or 'plan.json' not in manifest['outputs']:
        raise ValueError('Qualifier comparison requires a separately frozen plan')
    if manifest['code'] != {str(Path(n).resolve()): file_hash(Path(n)) for n in CODE}:
        raise ValueError('Qualifier comparison frozen code inventory differs')
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if plan['version'] != VERSION or plan['article_metadata'] != {}:
        raise ValueError('Qualifier comparison version or inherited metadata status differs')
    validate_cases(plan['constructed_cases'])
    return plan, bindings


def export(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    observed, constructed = [], []
    for row in plan['observed_queries']:
        if row['baseline_status'] not in {'context_prepared_before_generation', 'insufficient_evidence'}:
            raise ValueError('Qualifier comparison does not infer allowance from unknown baseline status')
        evidence = [Evidence(**e) for e in row['trace']['evidence']]
        assessment = assess_query_qualifiers(row['question'], evidence,
            baseline_allowed=row['baseline_status'] == 'context_prepared_before_generation', article_metadata=plan['article_metadata'])
        observed.append({'id': row['id'], 'baseline': row, 'assessment': assessment})
    for case in plan['constructed_cases']:
        assessment = assess_query_qualifiers(case['question'], [constructed_evidence(e, i) for i, e in enumerate(case['evidence'], 1)],
            baseline_allowed=case['baseline_allowed'], article_metadata=case.get('article_metadata', {}))
        constructed.append({'id': case['id'], 'reference': case, 'assessment': assessment,
                            'developer_reference_agreement': assessment['candidate_allowed'] == case['expected_candidate_allowed']})
    summary = {'observed_questions': len(observed),
        'baseline_allowed': sum(r['assessment']['baseline_allowed'] for r in observed),
        'candidate_allowed': sum(r['assessment']['candidate_allowed'] for r in observed),
        'baseline_evidence_items_preserved': sum(len(r['baseline']['trace']['evidence']) for r in observed),
        'constructed_cases': len(constructed),
        'constructed_reference_agreements': sum(r['developer_reference_agreement'] for r in constructed),
        'new_model_calls': 0, 'scientific_precision': None, 'scientific_recall': None,
        'scientific_admission': 'not_evaluated', 'runtime_activation': False}
    def detail(label: str, value: Any) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'
    cards = []
    for group, rows in [('observed', observed), ('constructed', constructed)]:
        for row in rows:
            pdfs = ''
            if group == 'observed':
                pdfs = ' '.join('<a href="' + html.escape(Path(r['original_pdf_path']).resolve().as_uri()
                    + '#page=' + str(r['page_number']), quote=True) + '">PDF p.' + str(r['page_number']) + '</a>'
                    for r in row['baseline']['sources']['pages'].values())
            cards.append('<article class="case" data-role="' + group + '"><h2>' + html.escape(row['id']) + '</h2><p>'
                + html.escape(row['assessment']['question']) + '</p>' + pdfs + detail('Проверка уточнений', row['assessment'])
                + detail('Исходный контекст / constructed reference', row.get('baseline', row.get('reference'))) + '</article>')
    html_page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — query qualifiers</title>'
        '<style>body{font:16px system-ui;margin:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        'article{border-top:1px solid #789;padding:12px}input{padding:10px;width:65%}[hidden]{display:none!important}</style>'
        '<h1>Обязательные уточнения запроса</h1><p>' + VERSION + '. Offline development comparison; не научная точность.</p>'
        + detail('Итог', summary) + '<a href="report.json">JSON</a> · <a href="manifest.json">Manifest</a>'
        '<p><label>Поиск <input type="search" id="q"></label></p>' + ''.join(cards)
        + '<script>const rows=[...document.querySelectorAll("article.case")];document.getElementById("q")'
        '.addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();for(const r of rows)'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(q)});</script></html>\n')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', {'version': VERSION, 'summary': summary, 'observed': observed, 'constructed': constructed})
    (output / 'review.html').write_text(html_page, encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_qualifier_comparison', 'inputs': bindings, 'code': {},
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return summary
