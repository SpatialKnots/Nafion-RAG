"""Verified frozen-parent import and deterministic condition-scope review artifacts."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.records.condition_scope import VERSION, ConditionProjection, SourceEvent, project_conditions, source_events
from app.records.extraction import write_json
from app.records.material_roles import project_roles
from app.records.material_roles_export import load_role_parent, role_summary
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash

CODE = ("app/records/condition_scope.py", "app/records/condition_scope_export.py", "scripts/records_condition_scope.py",
        "tests/unit/test_record_condition_scope.py", "docs/records/condition_scope_protocol_v0.1.md")


def load_condition_parent(directory: Path, relations: Path, windows: Path
                          ) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes, dict[str, SourceRegion], dict[str, str]]:
    manifest_path = directory.resolve() / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['version'] != 'records_material_roles_v0.1':
        raise ValueError('Condition scopes require frozen stage24 material roles')
    bindings = manifest['inputs'] | manifest['code'] | {str(manifest_path): file_hash(manifest_path)}
    bindings.update({str(_safe(directory, name)): value for name, value in manifest['outputs'].items()})
    verify_hashes(bindings)
    parent, raw, sources, old_bindings = load_role_parent(relations, windows)
    if any(bindings.get(name) != value for name, value in old_bindings.items()):
        raise ValueError('Condition parent does not bind its complete relation/source history')
    material_raw = (directory / 'report.json').read_bytes()
    material = json.loads(material_raw)
    if (material['version'] != manifest['version'] or (directory / 'parent_report.json').read_bytes() != raw
            or material['parent_report_sha256'] != file_hash(relations / 'report.json')
            or material['parent_manifest_sha256'] != file_hash(relations / 'manifest.json')):
        raise ValueError('Condition parent report/copy identity differs from frozen relations')
    proposals = [project_roles(row, sources, parent['relation_map']['cells'][row['cell_id']]) for row in parent['candidates']]
    if (material['projections'] != [p.model_dump(mode='json') for p in proposals]
            or material['summary'] != {'logical_slots': len(parent['slots']), **role_summary(proposals)}):
        raise ValueError('Frozen material roles differ from regenerated projections/summary')
    for row in parent['candidates']:
        artifact = json.loads(Path(row['artifacts']['candidates.json']).read_bytes())
        if row['candidate'] != next(c for c in artifact['records'] if c['record_id'] == row['record_id']):
            raise ValueError('Condition candidate differs from original native artifact')
    return parent, material, raw, material_raw, sources, bindings


def condition_summary(projections: list[ConditionProjection], events: tuple[SourceEvent, ...]) -> dict[str, Any]:
    return {'candidate_versions': len(projections), 'unique_candidate_cells': len({p.cell_id for p in projections}),
            'selected_statuses': dict(Counter(s.status for p in projections for s in p.selections)),
            'field_scope_bindings': dict(Counter(f'{s.source_field} -> {s.scope}' for p in projections for s in p.selections if s.scope)),
            'missing_legacy_selections': sum(len(p.missing_source_fields) for p in projections),
            'source_event_states': dict(Counter(e.state for e in events)),
            'source_event_kinds': dict(Counter(e.kind for e in events)),
            'measurement_environment_unknown': len(projections), 'equilibration_completion_unknown': len(projections),
            'new_model_calls': 0, 'scientific_precision': None, 'scientific_recall': None, 'scientific_admission': 'not_evaluated'}


def render_conditions(parent: dict[str, Any], material: dict[str, Any], projections: list[ConditionProjection],
                      catalog: dict[str, Any], summary: dict[str, Any]) -> str:
    def detail(label: str, value: Any) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    by_id = {str(p.record_id): p for p in projections}
    old_roles = {p['record_id']: p for p in material['projections']}
    rows = []
    for slot in parent['slots']:
        articles = []
        for row in [c for c in parent['candidates'] if c['cell_id'] == slot['cell_id']]:
            projection = by_id[row['record_id']]
            selected = ''.join('<tr class="selection"><td>' + html.escape(s.source_field) + '</td><td>'
                + html.escape(s.selected.text) + '</td><td>' + html.escape(s.scope or s.status)
                + detail('Источник, границы и диагностика', s.model_dump(mode='json')) + '</td></tr>' for s in projection.selections)
            links = ' · '.join('<a href="' + html.escape(Path(path).resolve().as_uri(), quote=True) + '">'
                               + html.escape(name) + '</a>' for name, path in row['artifacts'].items())
            articles.append('<article class="projection"><h3>' + html.escape(row['stage'] + ' · ' + row['record_id'])
                + '</h3><table><thead><tr><th>Старое поле</th><th>Выбранный текст</th><th>Роль / статус</th></tr></thead><tbody>'
                + selected + '</tbody></table><p>Среда измерения: unknown. Достижение равновесия: unknown. '
                'Применимость к результату: not_evaluated.</p>'
                + detail('Проекция и исходные пропуски', projection.model_dump(mode='json'))
                + detail('Прежние роли состава', old_roles[row['record_id']]) + detail('Прежний кандидат и аудит', row)
                + links + '</article>')
        rows.append('<tr class="source-slot"><td>' + str(slot['row']) + '</td><td>' + html.escape(slot['header']['text'])
            + '</td><td>' + html.escape(slot['value']['text'] if slot['value'] else slot['source_state'])
            + detail('Исходная позиция', slot) + '</td><td>' + ''.join(articles)
            + ('Без кандидатов; исходное состояние сохранено.' if not articles else '') + '</td></tr>')
    sources = ''.join('<p><a href="' + html.escape(Path(s['original_pdf_path']).resolve().as_uri(), quote=True)
        + f'#page={s["page_number"]}">Исходный PDF, стр. {s["page_number"]}</a></p>'
        + detail('Точный исходный текст · ' + s['region_id'], s['quote']) for s in parent['sources'].values())
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>ARIADNE — подготовка и условия измерения</title><style>body{font:15px system-ui;margin:24px;color:#18342d}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bccbc4;padding:8px;vertical-align:top}'
        'td{max-width:65ch}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:50vh;overflow:auto}'
        'article{border-bottom:2px solid #8eaaa0}input{padding:8px;width:65%}[hidden]{display:none!important}</style>'
        '<h1>Подготовка, кондиционирование и условия измерения</h1><p>Отдельные предложения по буквальным '
        'границам источника. Научная подтверждённость и применимость не установлены. Новых model calls нет.</p>'
        + detail('Версия и итоги — не научные метрики', {'version': VERSION, 'summary': summary})
        + '<p><a href="report.json">Проекции JSON</a> · <a href="parent_report.json">Прежний аудит</a> · '
        '<a href="material_roles_report.json">Прежние роли состава</a> · <a href="scope_schema.json">Схема</a> · '
        '<a href="source_events.json">Каталог фрагментов</a></p>'
        + detail('Все фрагменты методики, неподдержанные и обрезанные границы', catalog)
        + '<details><summary>Исходные тексты и PDF</summary>' + sources + '</details>'
        + '<label>Поиск <input id="q" type="search"></label><p id="count"></p><table><thead><tr>'
        '<th>Образец</th><th>Колонка</th><th>Значение и источник</th><th>Все версии</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table><script>const rows=[...document.querySelectorAll("tr.source-slot")];'
        'function filter(){const q=document.getElementById("q").value.toLocaleLowerCase();let n=0;'
        'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
        'document.getElementById("count").textContent=n+" / "+rows.length;}'
        'document.getElementById("q").addEventListener("input",filter);filter();</script></html>\n')


def export_condition_scope(directory: Path, relations: Path, windows: Path, output: Path, *, source_root: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    parent, material, raw, material_raw, sources, bindings = load_condition_parent(directory, relations, windows)
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in CODE}
    verify_hashes(bindings | code)
    table_id = parent['relation_map']['source_region_id']
    events = tuple(e for key, source in sources.items() if key != table_id for e in source_events(source))
    slots = {s['cell_id']: s for s in parent['slots']}
    projections = [project_conditions(row, sources, slots[row['cell_id']], table_id, events) for row in parent['candidates']]
    summary = {'logical_slots': len(parent['slots']), **condition_summary(projections, events)}
    catalog = {'version': VERSION, 'events': [e.model_dump(mode='json') for e in events],
               'parent_method_source_diagnostics': parent['method_source_diagnostics'],
               'scope': 'Source opportunities only; not inherited by candidates or scientific applicability.'}
    report = {'version': VERSION, 'material_parent_sha256': file_hash(directory / 'report.json'),
              'relation_parent_sha256': file_hash(relations / 'report.json'), 'summary': summary,
              'projections': [p.model_dump(mode='json') for p in projections]}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'parent_report.json').write_bytes(raw)
    (output / 'material_roles_report.json').write_bytes(material_raw)
    write_json(output / 'report.json', report)
    write_json(output / 'source_events.json', catalog)
    write_json(output / 'scope_schema.json', ConditionProjection.model_json_schema())
    (output / 'review.html').write_text(render_conditions(parent, material, projections, catalog, summary), encoding='utf-8')
    verify_hashes(bindings | code)
    write_json(output / 'manifest.json', {'version': VERSION, 'inputs': bindings, 'code': code,
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return summary
