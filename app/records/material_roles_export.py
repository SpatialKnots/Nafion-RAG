"""Immutable parent import and separate material/environment-role HTML/JSON artifacts."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.records.extraction import write_json
from app.records.material_roles import ROLE_NAMES, VERSION, RoleProjection, project_roles
from app.records.multi_run import _safe, verify_hashes
from app.records.schema import SourceRegion
from app.records.sources import file_hash
from app.records.table_cells import build_cell_ledger
from app.records.table_relations import relation_map
from app.records.table_relations_export import reconcile_history

CODE = ("app/records/material_roles.py", "app/records/material_roles_export.py", "scripts/records_material_roles.py",
        "tests/unit/test_record_material_roles.py", "docs/records/material_roles_protocol_v0.1.md")
LABELS = {"plasticiser_components": "Компоненты пластификатора", "plasticiser_composition": "Состав пластификатора",
          "plasticiser_basis": "Основание состава", "membrane_composition": "Состав мембраны",
          "measurement_environment": "Среда измерения"}


def load_role_parent(directory: Path, windows: Path) -> tuple[dict[str, Any], bytes, dict[str, SourceRegion], dict[str, str]]:
    directory = directory.resolve()
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["version"] != "records_table_relations_v0.1":
        raise ValueError("Material roles require a frozen stage23 relation audit")
    bindings = manifest["inputs"] | manifest["code"] | {str(manifest_path): file_hash(manifest_path)}
    bindings.update({str(_safe(directory, name)): expected for name, expected in manifest["outputs"].items()})
    verify_hashes(bindings)
    raw = (directory / "report.json").read_bytes()
    parent: dict[str, Any] = json.loads(raw)
    if parent["version"] != manifest["version"]:
        raise ValueError("Material-role parent report version differs from its manifest")
    if (len(parent["slots"]) != parent["summary"]["logical_slots"]
            or len(parent["candidates"]) != parent["summary"]["candidate_versions"]):
        raise ValueError("Material-role parent inventory differs from declared scope")
    reconcile_history({"slots": parent["slots"]}, parent["candidates"])
    sources = {key: SourceRegion.model_validate(value) for key, value in parent["sources"].items()}
    for key, source in sources.items():
        if key != source.region_id or bindings.get(str(Path(source.original_pdf_path).resolve())) != source.original_pdf_sha256:
            raise ValueError("Material-role source PDF identity is not in frozen parent bindings")
    geometry_path = (windows / "report.json").resolve()
    if str(geometry_path) not in bindings:
        raise ValueError("Material-role table geometry is not bound by the parent audit")
    geometry = json.loads(geometry_path.read_bytes())
    table = sources[parent["relation_map"]["source_region_id"]]
    page = next(p for p in geometry["pages"] if p["article_id"] == str(table.article_id) and p["page_number"] == table.page_number)
    ledger = build_cell_ledger(page, table)
    ledger["slots"] = parent["slots"]
    if relation_map(page, ledger, table) != parent["relation_map"]:
        raise ValueError("Material-role relation context differs from regenerated source geometry")
    return parent, raw, sources, bindings


def role_summary(projections: list[RoleProjection]) -> dict[str, Any]:
    by_role = {name: dict(Counter(r.status for p in projections for r in p.roles if r.role == name)) for name in ROLE_NAMES}
    mappings = Counter(f'{b.source_field} -> {r.role}' for p in projections for r in p.roles for b in r.bindings)
    kinds = Counter(b.match_kind for p in projections for r in p.roles for b in r.bindings)
    return {"candidate_versions": len(projections), "unique_candidate_cells": len({p.cell_id for p in projections}),
            "roles": by_role, "legacy_field_role_bindings": dict(mappings), "binding_match_kinds": dict(kinds),
            "unassigned_selections": sum(len(p.unassigned_selections) for p in projections),
            "missing_legacy_selections": sum(len(p.missing_source_fields) for p in projections),
            "new_model_calls": 0, "scientific_precision": None, "scientific_recall": None,
            "scientific_admission": "not_evaluated"}


def render_roles(parent: dict[str, Any], projections: list[RoleProjection], summary: dict[str, Any]) -> str:
    def details(label: str, value: Any) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    by_id = {str(p.record_id): p for p in projections}
    sources = ''.join('<p><a href="' + html.escape(Path(s["original_pdf_path"]).resolve().as_uri(), quote=True)
                      + f'#page={s["page_number"]}">Исходный PDF, стр. {s["page_number"]}</a></p>'
                      + details('Точный исходный текст · ' + s["region_id"], s["quote"]) for s in parent["sources"].values())
    rows = []
    for slot in parent["slots"]:
        articles = []
        for row in [c for c in parent["candidates"] if c["cell_id"] == slot["cell_id"]]:
            projection = by_id[row["record_id"]]
            role_rows = []
            for role in projection.roles:
                text = ' · '.join(b.selected.text for b in role.bindings) if role.bindings else role.status
                role_rows.append('<tr class="role"><th>' + html.escape(LABELS[role.role]) + '</th><td>' + html.escape(text)
                                 + '<p>' + html.escape(role.status) + '</p>'
                                 + details('Источники роли и диагностика', role.model_dump(mode="json")) + '</td></tr>')
            old_fields = {name: row["candidate"][name] for name in ("medium", "medium_composition", "composition_basis")}
            links = ' · '.join('<a href="' + html.escape(Path(path).resolve().as_uri(), quote=True) + '">'
                               + html.escape(name) + '</a>' for name, path in row["artifacts"].items())
            articles.append('<article class="projection"><h3>' + html.escape(row["stage"] + ' · ' + row["record_id"])
                            + '</h3><table>' + ''.join(role_rows) + '</table>'
                            + details('Исходные поля без изменений', old_fields)
                            + details('Полная проекция, missing и unassigned', projection.model_dump(mode="json"))
                            + details('Прежний кандидат и аудит', row) + links + '</article>')
        value = slot["value"]["text"] if slot["value"] else 'unresolved'
        rows.append('<tr class="source-slot"><td>' + str(slot["row"]) + '</td><td>' + html.escape(slot["header"]["text"])
                    + '</td><td>' + html.escape(value) + '<p>' + html.escape(slot["source_state"]) + '</p>'
                    + details('Позиция источника и прежняя история', slot) + '</td><td>'
                    + ''.join(articles) + ('Кандидатов нет; исходное состояние сохранено.' if not articles else '') + '</td></tr>')
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>ARIADNE — роли состава и среды</title><style>body{font:15px system-ui;margin:24px;color:#18342d}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bccbc4;padding:10px;vertical-align:top}'
            'td{max-width:65ch}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:50vh;overflow:auto}'
            'article{border-bottom:2px solid #8eaaa0}input{padding:8px;width:65%}[hidden]{display:none!important}</style>'
            '<h1>Роли состава и среды</h1><p>Предложения по буквальным меткам источника. '
            'Научное подтверждение не выполнено. Прежние кандидаты сохранены, новых model calls нет.</p>'
            + details('Версия и итоги — не метрики научной точности', {"version": VERSION, "summary": summary})
            + '<p><a href="parent_report.json">Прежний отчёт без изменений</a> · '
            '<a href="report.json">Проекции JSON</a> · <a href="role_schema.json">Схема ролей</a></p>'
            + '<details><summary>Исходные контексты и PDF</summary>' + sources + '</details>'
            + '<label>Поиск <input id="q" type="search"></label><p id="count"></p><table><thead><tr>'
            '<th>Образец</th><th>Колонка</th><th>Значение и источник</th><th>Все версии и роли</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table><script>'
            'const rows=[...document.querySelectorAll("tr.source-slot")];function filter(){'
            'const q=document.getElementById("q").value.toLocaleLowerCase();let n=0;'
            'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
            'document.getElementById("count").textContent=n+" / "+rows.length;}'
            'document.getElementById("q").addEventListener("input",filter);filter();</script></html>\n')


def export_material_roles(parent_directory: Path, windows: Path, output: Path, *, source_root: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    parent, raw, sources, bindings = load_role_parent(parent_directory, windows)
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in CODE}
    verify_hashes(bindings | code)
    projections = [project_roles(row, sources, parent["relation_map"]["cells"][row["cell_id"]]) for row in parent["candidates"]]
    summary = {"logical_slots": len(parent["slots"]), **role_summary(projections)}
    report = {"version": VERSION, "parent_report": "parent_report.json",
              "parent_report_sha256": file_hash(parent_directory / "report.json"),
              "parent_manifest_sha256": file_hash(parent_directory / "manifest.json"), "summary": summary,
              "projections": [p.model_dump(mode="json") for p in projections]}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    (output / "parent_report.json").write_bytes(raw)
    write_json(output / "report.json", report)
    write_json(output / "role_schema.json", RoleProjection.model_json_schema())
    (output / "review.html").write_text(render_roles(parent, projections, summary), encoding="utf-8")
    verify_hashes(bindings | code)
    write_json(output / "manifest.json", {"version": VERSION, "inputs": bindings, "code": code,
                                           "outputs": {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return summary
