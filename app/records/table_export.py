"""Read-only comparative proposal export with exact inputs and versioned checks."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import platform
from collections import Counter
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

from app.records.checks import VERSION as CHECKS_VERSION
from app.records.checks import check_bundle
from app.records.review import observations_for_review
from app.records.schema import CandidateBundle, RecordCandidate
from app.records.sources import file_hash

VERSION = "records_comparative_export_v0.1"
_CODE_PATHS = (
    "app/records/checks.py", "app/records/table_export.py", "app/records/schema.py", "app/records/readiness.py",
    "app/records/review.py", "app/records/sources.py", "scripts/records_table.py", "pyproject.toml",
)
LIMITATIONS = (
    "Development proposals only: all records need review; scientific admission and Li-ion confirmation are not established.",
    "Scope is the declared saved bundles, not all eligible records in an article or corpus; empty bundles are not verified negatives.",
    "Exact evidence and PDF hashes do not validate OCR, numerical meaning, units, sample/condition linkage or scientific comparability.",
    "PDF bytes are verified; current database text/layer selection and historical model execution are not revalidated.",
    "Rows are not deduplicated across runs/publications and must not be counted as independent measurements.",
    "CSV formula-like cells have a declared display prefix; exact raw text and nested evidence remain in JSON/input copies.",
    "This exporter neither extracts new records nor stores human decisions; it makes no model/API/database call.",
)


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _pdf_link(path: str, page: int, label: str) -> str:
    return f'<a href="{_escape(Path(path).resolve().as_uri())}#page={page}">{_escape(label)}</a>'


def _record_details(record: RecordCandidate, checks: dict[str, Any]) -> str:
    fields = "".join(
        f"<tr><td>{_escape(name)}</td><td>{_escape(obs.status)}</td>"
        f"<td><pre>{_escape(obs.raw_text if obs.raw_text is not None else '—')}</pre></td>"
        f"<td><pre>{_escape(obs.note or '')}</pre></td>"
        f"<td><pre>{_escape(_json([span.model_dump(mode='json') for span in obs.evidence]))}</pre></td></tr>"
        for name, obs in observations_for_review(record)
    )
    return (
        '<details><summary>Все поля, точные evidence и проверки</summary>'
        '<table><thead><tr><th>Поле</th><th>Status</th><th>Raw text</th><th>Примечание</th><th>Evidence</th></tr></thead>'
        f'<tbody>{fields}</tbody></table><h4>Linkage proposals</h4><pre>'
        f'{_escape(_json([link.model_dump(mode="json") for link in record.linkage]))}</pre>'
        f'<h4>Checks: {CHECKS_VERSION}</h4><pre>{_escape(_json(checks))}</pre></details>'
    )


def render_table(report: dict[str, Any]) -> str:
    bodies = []
    for case in report["cases"]:
        bundle = CandidateBundle.model_validate(case["candidate_bundle"])
        sources = []
        for region in bundle.regions:
            sources.append(
                '<details><summary>'
                f'{_escape(region.article_id)}, PDF page {region.page_number}, layer {_escape(region.text_layer)}'
                '</summary><p>'
                + _pdf_link(region.original_pdf_path, region.page_number, "Original PDF") + " · "
                + _pdf_link(region.layer_pdf_path, region.page_number, "Selected layer PDF")
                + f'</p><pre>{_escape(_json(region.model_dump(mode="json")))}</pre></details>'
            )
        heading = (
            '<tr><td colspan="11"><strong>' + _escape(case["case_id"]) + '</strong>: '
            + _escape(case["input"]["path"]) + f' · records={len(bundle.records)}'
            + '<details><summary>Входной снимок и полный source context</summary><pre>'
            + _escape(_json({key: case[key] for key in ("input", "run_id", "producer")}))
            + '</pre>' + "".join(sources) + '</details></td></tr>'
        )
        rows = []
        for record, item in zip(bundle.records, case["records"], strict=True):
            observations = dict(observations_for_review(record))
            cells = "".join(
                f'<td><pre>{_escape(observations[name].raw_text if observations[name].raw_text is not None else "—")}</pre>'
                f'<small>{_escape(observations[name].status)}</small></td>'
                for name in ("sample_label", "property_name", "value.raw_value", "value.raw_unit", "temperature",
                             "medium", "medium_composition", "method")
            )
            used_regions = {span.region_id for span in record.evidence_spans()}
            links = "<br>".join(
                _pdf_link(region.original_pdf_path, region.page_number, f"PDF p.{region.page_number}")
                for region in bundle.regions if region.region_id in used_regions
            )
            rows.append(
                '<tr>' + cells + f'<td>{_escape(item["checks"]["technical_outcome"])}<br>needs_review</td>'
                + f'<td>{links}</td><td><p>Record: {_escape(record.record_id)}<br>'
                + f'Run: {_escape(bundle.run_id)}<br>Representation: {_escape(record.value.representation)}</p>'
                + _record_details(record, item["checks"]) + '</td></tr>'
            )
        if not rows:
            rows.append('<tr><td colspan="11">Нет предложенных записей. Это не подтверждённый отрицательный результат.</td></tr>')
        bodies.append('<tbody data-case="true">' + heading + "".join(rows) + '</tbody>')
    limits = "".join(f"<li>{_escape(item)}</li>" for item in report["limitations"])
    return (
        '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>Li-Nafion — proposed comparative records</title><style>'
        'body{font:15px system-ui;margin:24px;color:#172334;background:#f7f9fc}'
        'table{border-collapse:collapse;width:100%;background:white}th,td{border:1px solid #ccd4df;padding:8px;vertical-align:top}'
        'th{background:#e6edf7;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0;max-width:100%}'
        'details{margin:8px 0}summary{cursor:pointer}small{color:#4d5c70}input{padding:10px;width:min(650px,90%)}'
        '.scroll{overflow-x:auto}.notice{background:#fff3d4;padding:14px;border-left:4px solid #ac7210}'
        '</style><h1>Li-Nafion: сравнительная таблица предложенных записей</h1>'
        f'<p>Export: {VERSION} · Checks: {CHECKS_VERSION}</p>'
        '<p class="notice">Все записи: needs_review. Scientific admission: not_evaluated. '
        'Точные цитаты и успешные технические проверки не подтверждают научную правильность.</p>'
        f'<p>Область: {report["summary"]["input_bundles"]} входных снимка; '
        f'{report["summary"]["records"]} предложенных записей. '
        f'Неполные: {report["summary"]["incomplete"]}; unresolved: {report["summary"]["unresolved"]}.</p>'
        '<p><a href="table.json">Полный JSON / evidence</a> · <a href="table.csv">CSV</a> · '
        '<a href="manifest.json">Manifest</a></p><label>Поиск по входам, полям и источникам '
        '<input id="search" type="search" placeholder="Образец, значение, метод, диагностика"></label>'
        '<p id="visible" aria-live="polite"></p><div class="scroll"><table><thead><tr>'
        + "".join(f'<th>{name}</th>' for name in ("Образец", "Свойство", "Значение", "Единица", "Температура",
                    "Среда", "Состав среды", "Метод", "Статус", "Источник", "Подробности"))
        + '</tr></thead>' + "".join(bodies) + '</table></div><h2>Ограничения</h2><ul>' + limits + '</ul>'
        '<script>const search=document.getElementById("search");'
        'function filter(){const q=search.value.toLocaleLowerCase();let n=0;'
        'document.querySelectorAll("tbody[data-case]").forEach(b=>{'
        'b.hidden=!b.textContent.toLocaleLowerCase().includes(q);if(!b.hidden)n++;});'
        'document.getElementById("visible").textContent="Видимых входных снимков: "+n;}'
        'search.addEventListener("input",filter);filter();</script></html>\n'
    )


def _csv(report: dict[str, Any]) -> str:
    rows: list[dict[str, str]] = []
    for index, case in enumerate(report["cases"]):
        bundle = CandidateBundle.model_validate(case["candidate_bundle"])
        for record_index, (record, item) in enumerate(zip(bundle.records, case["records"], strict=True)):
            row = {
                "case_id": case["case_id"], "input_sha256": case["input"]["sha256"], "run_id": str(bundle.run_id),
                "record_id": str(record.record_id), "article_id": str(record.article_id),
                "technical_outcome": item["checks"]["technical_outcome"], "review_state": record.review_state,
                "scientific_admission": "not_evaluated", "li_ion_confirmation": record.li_ion_confirmation,
                "representation": record.value.representation,
                "evidence_json_pointer": f"table.json#/cases/{index}/records/{record_index}",
            }
            for name, obs in observations_for_review(record):
                row[name] = obs.raw_text or ""
                row[f"{name}.status"] = obs.status
            escaped = []
            for key, value in row.items():
                if value[:1] in {"\t", "\r", "\n"} or value.lstrip()[:1] in {"=", "+", "-", "@"}:
                    row[key] = "'" + value
                    escaped.append(key)
            row["csv_escaped_columns"] = json.dumps(escaped)
            rows.append(row)
    buffer = io.StringIO(newline="")
    # Also provide a meaningful CSV for a declared scope containing no records.
    columns = list(rows[0]) if rows else ["case_id", "record_id", "review_state", "scientific_admission", "evidence_json_pointer",
                                         "csv_escaped_columns"]
    writer = csv.DictWriter(buffer, fieldnames=columns, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _verify_snapshots(snapshots: dict[Path, str]) -> None:
    for path, expected in snapshots.items():
        if file_hash(path) != expected:
            raise ValueError(f"File checksum mismatch: {path}")


def export_table(inputs: Sequence[Path], output_dir: Path, *, source_root: Path) -> dict[str, Any]:
    """Export a complete caller-declared saved scope. Fail before output on invalid input."""
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    paths = [path.resolve() for path in inputs]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("At least one input is required; duplicate input paths are forbidden")
    snapshots: dict[Path, str] = {}
    code = {name: file_hash(source_root / name) for name in _CODE_PATHS}
    snapshots.update({(source_root / name).resolve(): digest for name, digest in code.items()})
    cases: list[dict[str, Any]] = []
    raw_inputs: list[bytes] = []
    input_hashes: set[str] = set()
    pdfs: dict[Path, str] = {}
    for index, path in enumerate(paths):
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest in input_hashes:
            raise ValueError(f"Duplicate input bytes: {path}")
        input_hashes.add(digest)
        snapshots[path] = digest
        bundle = CandidateBundle.model_validate_json(raw)
        checks = check_bundle(bundle)
        for region in bundle.regions:
            for stored_path, expected in ((region.original_pdf_path, region.original_pdf_sha256),
                                          (region.layer_pdf_path, region.layer_pdf_sha256)):
                pdf_path = Path(stored_path).resolve()
                if pdf_path in pdfs and pdfs[pdf_path] != expected:
                    raise ValueError(f"Conflicting PDF checksum declarations: {pdf_path}")
                pdfs[pdf_path] = expected
        cases.append({
            "case_id": f"C{index + 1}", "run_id": str(bundle.run_id), "producer": bundle.producer,
            "input": {"path": str(path), "sha256": digest, "bytes": len(raw), "copy": f"inputs/{index + 1:04d}.json"},
            "candidate_bundle": bundle.model_dump(mode="json"),
            "records": [{"candidate": record.model_dump(mode="json"), "checks": check.model_dump(mode="json")}
                        for record, check in zip(bundle.records, checks, strict=True)],
        })
        raw_inputs.append(raw)
    for path, digest in pdfs.items():
        if path in snapshots and snapshots[path] != digest:
            raise ValueError(f"Conflicting file identity: {path}")
        snapshots[path] = digest
    _verify_snapshots(snapshots)
    outcomes = Counter(item["checks"]["technical_outcome"] for case in cases for item in case["records"])
    report = {
        "version": VERSION, "checks_version": CHECKS_VERSION, "scope_basis": "caller_declared_saved_bundles",
        "summary": {"input_bundles": len(cases), "empty_bundles": sum(not case["records"] for case in cases),
                    "records": sum(outcomes.values()), "incomplete": outcomes["incomplete"], "unresolved": outcomes["unresolved"],
                    "scientific_admission": "not_evaluated"},
        "cases": cases, "limitations": list(LIMITATIONS),
    }
    contents = {"table.json": _json(report), "table.csv": _csv(report), "review.html": render_table(report)}
    manifest: dict[str, Any] = {
        "version": VERSION, "checks_version": CHECKS_VERSION,
        "inputs": [case["input"] for case in cases],
        "pdfs": [{"path": str(path), "sha256": digest} for path, digest in sorted(pdfs.items())],
        "code": code, "python": platform.python_version(), "pydantic": version("pydantic"),
        "limitations": list(LIMITATIONS),
    }
    _verify_snapshots(snapshots)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "inputs").mkdir()
    for case, raw in zip(cases, raw_inputs, strict=True):
        with (output_dir / case["input"]["copy"]).open("xb") as stream:
            stream.write(raw)
    for name, content in contents.items():
        with (output_dir / name).open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
    _verify_snapshots(snapshots)
    manifest["outputs"] = {path.relative_to(output_dir).as_posix(): file_hash(path)
                           for path in sorted(output_dir.rglob("*")) if path.is_file()}
    with (output_dir / "manifest.json").open("x", encoding="utf-8", newline="") as stream:
        stream.write(_json(manifest))
    return report
