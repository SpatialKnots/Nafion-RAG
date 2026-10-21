"""Offline complete-history relation audit and immutable local HTML/JSON export."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.records.extraction import write_json
from app.records.multi import parse_multi_reply, resolve_multi_reply
from app.records.multi_run import _safe, verify_hashes
from app.records.openai_backend import responses_content
from app.records.schema import CandidateBundle
from app.records.sources import file_hash
from app.records.table_cells import absolute_span, bind_reply
from app.records.table_relations import VERSION, audit_measurement, history_comparisons, relation_map
from app.records.table_remaining import accounting, load_remaining

CODE = ("app/records/table_relations.py", "app/records/table_relations_export.py", "scripts/records_table_relations.py",
        "tests/unit/test_record_table_relations.py", "docs/records/table_relations_protocol_v0.1.md")


def bind_run(directory: Path, bindings: dict[str, str], version: str, *, inherited: bool) -> dict[str, Any]:
    directory = directory.resolve()
    path = directory / "manifest.json"
    digest = file_hash(path)
    if inherited and bindings.get(str(path)) != digest:
        raise ValueError("Audit parent run is not bound by the frozen stage22 preparation")
    manifest = json.loads(path.read_bytes())
    if manifest["version"] != version:
        raise ValueError("Unexpected audit run version")
    bindings[str(path)] = digest
    for name, expected in manifest["artifacts"].items():
        target = str(_safe(directory, name))
        if inherited and bindings.get(target) != expected:
            raise ValueError("Audit parent artifact is not bound by the frozen preparation")
        bindings[target] = expected
    verify_hashes(bindings)
    report: dict[str, Any] = json.loads((directory / "report.json").read_bytes())
    if report["final_source_integrity"]["status"] != "verified" or any(r["status"] != "integrity_valid" for r in report["cases"]):
        raise ValueError("Audit requires completed, integrity-valid input runs")
    return report


def reconcile_history(ledger: dict[str, Any], records: list[dict[str, Any]]) -> None:
    expected = {}
    for cell in ledger["slots"]:
        groups = [("stage20", "kayumov_table", identifier) for identifier in cell["previous_proposals"]]
        groups += [("stage21", p["case_id"], p["record_id"]) for p in cell["new_proposals"]]
        groups += [("stage22", p["case_id"], p["record_id"]) for p in cell["stage22_proposals"]]
        for stage, case, identifier in groups:
            if identifier in expected:
                raise ValueError("Duplicate candidate identity in frozen audit history")
            expected[identifier] = (cell["cell_id"], stage, case)
    actual = {}
    for row in records:
        if row["record_id"] in actual:
            raise ValueError("Duplicate replayed candidate in audit")
        actual[row["record_id"]] = (row["cell_id"], row["stage"], row["case_id"])
    if actual != expected:
        raise ValueError("Replayed audit candidates do not exactly reconcile with all ledger histories")


def render_relations(report: dict[str, Any]) -> str:
    def details(label: str, value: Any) -> str:
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'

    sources = ''.join('<p><a href="' + html.escape(Path(region["original_pdf_path"]).resolve().as_uri(), quote=True)
                      + f'#page={region["page_number"]}">Original PDF p.{region["page_number"]}</a></p>'
                      + details('Exact source · ' + region["region_id"], region["quote"])
                      for region in report["sources"].values())
    rows = []
    for slot in report["slots"]:
        articles = []
        for candidate in [r for r in report["candidates"] if r["cell_id"] == slot["cell_id"]]:
            outcomes = Counter(f["outcome"] for f in candidate["findings"])
            links = ' · '.join('<a href="' + html.escape(Path(path).resolve().as_uri(), quote=True) + '">'
                               + html.escape(name) + '</a>' for name, path in candidate["artifacts"].items())
            articles.append('<article class="candidate"><h3>' + html.escape(candidate["stage"] + ' · ' + candidate["record_id"])
                            + '</h3><p>' + html.escape(json.dumps(dict(outcomes), ensure_ascii=False)) + '</p>' + links
                            + details('New coordinate/cue diagnostics · scientific support not evaluated', candidate["findings"])
                            + details('Unchanged candidate and previous checks', {"candidate": candidate["candidate"],
                                                                                 "checks": candidate["previous_checks"]})
                            + details('Actual token selections', candidate["raw_selection"]) + '</article>')
        value = slot["value"]["text"] if slot["value"] else 'unresolved'
        rows.append('<tr class="slot"><td>' + str(slot["row"]) + '</td><td>' + html.escape(slot["header"]["text"])
                    + '</td><td>' + html.escape(value) + '</td><td>' + html.escape(slot["source_state"])
                    + details('Source geometry / proposed relation context', slot) + '</td><td>'
                    + ''.join(articles) + ('No candidate; source state retained.' if not articles else '') + '</td></tr>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>ARIADNE source relation audit</title><style>body{font:15px system-ui;margin:24px;color:#18342d}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bccbc4;padding:10px;vertical-align:top}'
            'td{max-width:65ch}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:50vh;overflow:auto}'
            'article{border-bottom:2px solid #8eaaa0}input{padding:8px;width:65%}[hidden]{display:none!important}</style>'
            '<h1>Table relation evidence audit</h1><p>Coordinate and literal-cue diagnostics only. '
            'Scientific support remains not evaluated. Previous proposals are preserved; no new model calls.</p>'
            + details('Version / input snapshot / source hashes', {k: report[k] for k in ('version', 'input_snapshot', 'summary')})
            + details('Method source boundary and semantic limits', report["method_source_diagnostics"])
            + details('All candidate versions for revisited cells', report["history_comparisons"])
            + '<details><summary>Exact source contexts and PDF links</summary>' + sources + '</details>'
            + '<label>Search <input id="q" type="search"></label><p id="count"></p><table><thead><tr>'
            '<th>Sample</th><th>Column</th><th>Literal value</th><th>Source state and context</th>'
            '<th>Every candidate version and audit</th></tr></thead><tbody>' + ''.join(rows)
            + '</tbody></table><script>const rows=[...document.querySelectorAll("tr.slot")];'
            'function filter(){const q=document.getElementById("q").value.toLocaleLowerCase();let n=0;'
            'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
            'document.getElementById("count").textContent=n+" / "+rows.length;}'
            'document.getElementById("q").addEventListener("input",filter);filter();</script></html>\n')


def export_relation_audit(prepared: Path, stage22: Path, stage21: Path, stage20: Path, windows: Path,
                          output: Path, *, source_root: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    prepared, stage22, stage21, stage20 = (p.resolve() for p in (prepared, stage22, stage21, stage20))
    _, _, _, bindings = load_remaining(prepared)
    last = bind_run(stage22, bindings, "records_table_remaining_v0.1", inherited=False)
    if last["prepared_manifest_sha256"] != file_hash(prepared / "manifest.json"):
        raise ValueError("Audit run/preparation identity mismatch")
    middle = bind_run(stage21, bindings, "records_table_continuation_v0.1", inherited=True)
    first = bind_run(stage20, bindings, "records_multi_fixed_v0.1", inherited=True)
    ledger = json.loads((stage22 / "ledger.json").read_bytes())
    if accounting(ledger) != last["summary"]["source_accounting"] or ledger["stage22_summary"] != accounting(ledger):
        raise ValueError("Audit final ledger accounting differs from saved run")
    window_path = (windows / "report.json").resolve()
    if str(window_path) not in bindings:
        raise ValueError("Relation audit geometry is not in the frozen source bindings")
    window_report = json.loads(window_path.read_bytes())
    code = {str((source_root / name).resolve()): file_hash(source_root / name) for name in CODE}
    verify_hashes(bindings | code)
    candidates: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    batches = []
    relations: dict[str, Any] | None = None
    for stage, directory, run, table_only in (("stage20", stage20, first, True), ("stage21", stage21, middle, False),
                                               ("stage22", stage22, last, False)):
        for case in run["cases"]:
            if table_only and case["case_id"] != "kayumov_table":
                continue
            batch = directory / case["case_id"]
            bundle = CandidateBundle.model_validate_json((batch / "input.json").read_bytes())
            reply = parse_multi_reply(responses_content((batch / "response.json").read_bytes()))
            restored, unresolved = resolve_multi_reply(bundle, reply)
            saved = CandidateBundle.model_validate_json((batch / "candidates.json").read_bytes())
            if (restored.records != saved.records or restored.regions != saved.regions
                    or unresolved != json.loads((batch / "unresolved.json").read_bytes())
                    or reply.model_dump(mode="json") != json.loads((batch / "reply.json").read_bytes())):
                raise ValueError("Audit native replay differs from saved parent output")
            ids = bind_reply(bundle, reply, ledger, require_method_region=stage != "stage20")
            if stage != "stage20":
                expected = [{"cell_id": identifier, "record_id": str(record.record_id)}
                            for identifier, record in zip(ids, saved.records, strict=True)]
                if expected != json.loads((batch / "cell_bindings.json").read_bytes()):
                    raise ValueError("Audit native cell bindings differ from saved output")
            table = bundle.regions[0]
            if relations is None:
                page = next(p for p in window_report["pages"] if p["article_id"] == str(table.article_id)
                            and p["page_number"] == table.page_number)
                relations = relation_map(page, ledger, table)
            if table.region_id != relations["source_region_id"]:
                raise ValueError("Audit input table context changed between stages")
            sources.update({r.region_id: r.model_dump(mode="json") for r in bundle.regions})
            checks = json.loads((batch / "checks.json").read_bytes())
            for identifier, measurement, record in zip(ids, reply.measurements, saved.records, strict=True):
                prior_checks = [c for c in checks if c["record_id"] == str(record.record_id)]
                if len(prior_checks) != 1:
                    raise ValueError("Missing or repeated previous candidate checks in audit")
                cell = next(s for s in ledger["slots"] if s["cell_id"] == identifier)
                selected = {str(o.field): {"status": o.status, "raw": absolute_span(bundle, o.raw_span) if o.raw_span else None}
                            for o in measurement.observations}
                candidates.append({"record_id": str(record.record_id), "cell_id": identifier, "stage": stage,
                                   "case_id": case["case_id"], "region_ids": [r.region_id for r in bundle.regions],
                                   "candidate": record.model_dump(mode="json"), "raw_selection": measurement.model_dump(mode="json"),
                                   "selected_fields": selected, "previous_checks": prior_checks[0],
                                   "findings": audit_measurement(bundle, measurement, cell, relations),
                                   "scientific_support": "not_evaluated", "artifacts": {
                                       name: str(batch / name) for name in ("input.json", "response.json", "candidates.json")}})
            batches.append({"stage": stage, "case_id": case["case_id"], "records": len(saved.records),
                            "response_sha256": file_hash(batch / "response.json"), "native_replay_equal": True})
    if relations is None:
        raise ValueError("Audit has no table source")
    reconcile_history(ledger, candidates)
    method_paths = [Path(name) for name in bindings if Path(name).name == "method_source.json"
                    and Path(name).parent.name == "prepared_v01"]
    if len(method_paths) != 1:
        raise ValueError("Audit method boundary diagnostics are missing or ambiguous")
    outcomes = Counter(f["outcome"] for c in candidates for f in c["findings"])
    counts = Counter(c["stage"] for c in candidates)
    report = {"version": VERSION, "input_snapshot": {"stage22_prepared_manifest_sha256": file_hash(prepared / "manifest.json"),
                "stage22_run_manifest_sha256": file_hash(stage22 / "manifest.json"), "frozen_bindings": len(bindings)},
              "sources": dict(sorted(sources.items())), "method_source_diagnostics": json.loads(method_paths[0].read_bytes()),
              "relation_map": relations, "batches": batches, "candidates": candidates,
              "slots": [{**s, "relation_context": relations["cells"][s["cell_id"]],
                         "audited_candidate_ids": [c["record_id"] for c in candidates if c["cell_id"] == s["cell_id"]]}
                        for s in ledger["slots"]], "history_comparisons": history_comparisons(candidates),
              "summary": {"logical_slots": len(ledger["slots"]), "candidate_versions": len(candidates),
                          "unique_candidate_cells": len({c["cell_id"] for c in candidates}), "records_per_stage": dict(counts),
                          "replayed_native_batches": len(batches), "diagnostic_outcomes": dict(outcomes),
                          "new_model_calls": 0, "scientific_precision": None, "scientific_recall": None,
                          "scientific_acceptance": "not_evaluated"}}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "report.json", report)
    (output / "review.html").write_text(render_relations(report), encoding="utf-8")
    verify_hashes(bindings | code)
    write_json(output / "manifest.json", {"version": VERSION, "inputs": bindings, "code": code,
                                           "outputs": {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return dict(report["summary"])
