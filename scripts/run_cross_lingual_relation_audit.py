"""Replay frozen service preparations and audit source-local RU/EN relations."""

from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.cross_lingual_relation_audit import VERSION, audit  # noqa: E402
from scripts.retrieval_ablation import ARMS  # noqa: E402
from scripts.run_swelling_retrieval_audit import CaptureComplete, NoGeneration  # noqa: E402

CAPTURE = ROOT / "output/retrieval_ablation_20261031/capture_v02"
WINDOW = ROOT / "output/retrieval_window_selection_20261102/review_v02"
PROTOCOL = ROOT / "docs/records/cross_lingual_relation_audit_protocol_v0.1.md"
CONTROLS = ROOT / "docs/records/cross_lingual_relation_controls_v0.1.json"


def validate_sources(trace: dict[str, Any], corpus: dict[str, Any]) -> None:
    for row in trace["retrieval"]["results"]:
        original = corpus[row["chunk_id"]]
        for key in ("article_id", "chunk_id", "full_text", "page_start", "page_end", "source_type", "text_layer"):
            if row[key] != original[key]:
                raise ValueError("Frozen raw retrieval source differs: " + key)


def replay_service(record: dict[str, Any], settings: Any) -> dict[str, Any]:
    from sqlalchemy.engine import Engine

    from app.generation import service
    from app.retrieval import search

    request = record["request"]
    saved = record["trace"]["retrieval"]
    response = search.SearchResponse(
        query=saved["query"], results=[search.SearchResult(**row) for row in saved["results"]], metadata=copy.deepcopy(saved["metadata"])
    )
    actual: dict[str, Any] = {}

    def observe(retrieval: Any, evidence: Any, metadata: Any) -> None:
        actual.update(retrieval=asdict(retrieval), evidence=[asdict(row) for row in evidence], metadata=metadata)

    with ExitStack() as stack:
        guards = [
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name + " forbidden")))
            for owner, name in (
                (Engine, "connect"),
                (service, "build_answer_provider"),
                (search, "embed_query_with_fastembed"),
                (search, "exact_search"),
                (search, "semantic_search"),
            )
        ]
        stack.enter_context(patch.object(service, "search_chunks", return_value=response))
        try:
            result = service.answer_question(
                object(),
                settings,
                request["question"],
                collection=request["collection"],
                top_k=request["top_k"],
                method=request["method"],
                answer_style=request["answer_style"],
                answer_language=request["answer_language"],
                provider=NoGeneration(),
                trace_observer=observe,
            )
            status = result.status
        except CaptureComplete:
            status = "stopped_before_generation"
        if any(guard.call_count for guard in guards):
            raise ValueError("Forbidden operation attempted")
    if actual != record["trace"] or status != record["boundary_status"]:
        raise ValueError("Frozen full service trace or status differs")
    return {"full_trace_identical": True, "boundary_status": status, "forbidden_calls": 0}


def load_records() -> list[dict[str, Any]]:
    dataset = json.loads((CAPTURE / "cases.json").read_bytes())["cases"]
    records, requests = [], {}
    for index, case in enumerate(dataset):
        for arm in ARMS:
            path = CAPTURE / f"cases/{index:03d}_{arm}.json"
            value = json.loads(path.read_bytes())
            requests[case["id"], arm] = value["request"]
            records.append(
                {
                    "case_id": case["id"],
                    "origin": case["origin"],
                    "fixture_answerable": case.get("answerable"),
                    "arm": arm,
                    "window_qualifier": "historical",
                    "trace": value["trace"],
                    "request": value["request"],
                    "boundary_status": value["boundary_status"],
                    "input_path": str(path.resolve()),
                }
            )
    window = json.loads((WINDOW / "report.json").read_bytes())
    for item in window["scoped_records"]:
        records.append(
            {
                "case_id": item["case_id"],
                "origin": "frozen_window_selection_candidate",
                "fixture_answerable": None,
                "arm": item["arm"],
                "window_qualifier": item["qualifier"],
                "trace": item["trace"],
                "request": requests[item["case_id"], item["arm"]],
                "boundary_status": item["boundary_status"],
                "input_path": str((WINDOW / "report.json").resolve()),
            }
        )
    return records


def evaluate_controls() -> dict[str, Any]:
    dataset = json.loads(CONTROLS.read_bytes())
    results = []
    for control in dataset["controls"]:
        texts = control.get("texts", [control.get("text", "")])
        sources = [{"text": raw} for raw in texts]
        diagnostic = audit(control.get("question", dataset["default_question"]), sources, baseline_adequate=False)
        if bool(diagnostic["proposals"]) != control["candidate"]:
            raise ValueError("Control differs: " + control["id"])
        if diagnostic["textual_requirements_met"] != control.get("requirements_met", control["candidate"]):
            raise ValueError("Control requirements differ: " + control["id"])
        results.append({**control, "sources": sources, "diagnostic": diagnostic})
    return {
        "origin": dataset["origin"],
        "criterion": dataset["criterion"],
        "records": results,
        "expected_behavior_agreements": len(results),
        "informative_but_unresolved_controls": [
            row["id"] for row in results if row.get("development_informative") and not row["diagnostic"]["textual_requirements_met"]
        ],
        "scientific_accuracy": None,
    }


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return "<details><summary>" + esc(label) + "</summary><pre>" + esc(raw) + "</pre></details>"

    body = (
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: RU/EN relation audit</title>'
        "<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}"
        "[hidden]{display:none!important}</style><h1>RU/EN: запрошенная связь и локальная принадлежность</h1>"
        "<p>" + esc(VERSION) + ". Frozen inputs: retrieval_ablation_20261031/capture_v02 и "
        "retrieval_window_selection_20261102/review_v02. Новых DB/search/embedding/model/OAuth/slots:0. "
        "Gate/runtime не менялись. План качества ответов75%; независимая оценка открыта.</p>"
        "<p>Все результаты ниже — source-local textual proposals или unresolved. Ни один результат не разрешает "
        "генерацию и не подтверждает научную связь, выполнение опыта или владельца численных условий. "
        "Исходные решения gate сохранены отдельно. Exact-match conditions остаются без подтверждённого owner.</p>"
        + detail("Итоги и ограничения", report["summary"])
        + detail("Constructed controls, включая известные пропуски", report["controls"])
        + "<h2>Каждый frozen набор evidence</h2><table><thead><tr><th>Case</th><th>Arm / window qualifier</th>"
        "<th>Baseline gate</th><th>Source-local proposals</th><th>Textual requirements</th><th>Scope / details</th>"
        "</tr></thead><tbody>"
    )
    for record in report["records"]:
        analysis = record["analysis"]
        body += (
            "<tr><td>"
            + esc(record["case_id"])
            + "</td><td>"
            + esc(record["arm"] + " / " + record["window_qualifier"])
            + "</td><td>"
            + esc(record["baseline_adequacy"]["adequate"])
            + "</td><td>"
            + str(len(analysis.get("proposals", [])))
            + "</td><td>"
            + esc(analysis["textual_requirements_met"])
            + "</td><td>"
            + detail(analysis["state"], record)
            + "</td></tr>"
        )
    body += "</tbody></table><h2>Полный source context scoped случаев, raw offsets и unresolved</h2>"
    for record in report["records"]:
        if not record["analysis"]["requirements"]["in_scope"]:
            continue
        body += detail(record["case_id"] + " / " + record["arm"] + " / " + record["window_qualifier"], record)
    body += "<h2>Reference anchors: только проверка источников, не input анализатора</h2>"
    for window in report["reference_windows"]:
        body += (
            '<p><a href="'
            + esc(Path(window["original_pdf_path"]).as_uri() + "#page=" + str(window["pdf_page"]))
            + '">'
            + esc(window["label"])
            + ", PDF с."
            + str(window["pdf_page"])
            + "</a></p>"
            + detail("Exact source window", window)
        )
    body += (
        "<h2>TAC: все33 работы исходного snapshot</h2><p>Сохранённые metadata, не новая выгрузка БД. "
        "Неизвестные поля сохранены; независимой проверки metadata нет.</p>"
        '<label>Поиск по TAC <input id="q" type="search"></label><table id="tac"><thead><tr>'
        + "".join(
            "<th>" + name + "</th>"
            for name in ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "hyperlink to original file")
        )
        + "</tr></thead><tbody>"
    )
    for article in report["articles"]:
        body += "<tr data-row>"
        for key in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            body += "<td>" + ("Неизвестно / не собрано" if article[key] is None else detail("Полное значение", article[key])) + "</td>"
        body += (
            '<td><a href="'
            + esc(Path(article["original_pdf_path"]).as_uri())
            + '">Оригинальный PDF</a>'
            + detail("Source provenance и diagnostics", article)
            + "</td></tr>"
        )
    body += (
        '</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
        'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});'
        "</script></html>"
    )
    files.save(output / "review.html", body.encode("utf-8"))


def run(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    for folder in (CAPTURE, WINDOW):
        files.verify_manifest(folder)
    previous = json.loads((WINDOW / "report.json").read_bytes())
    files.verify(previous["bindings"])
    corpus = json.loads((CAPTURE / "corpus.json").read_bytes())
    new_paths = [
        Path(__file__),
        ROOT / "scripts/cross_lingual_relation_audit.py",
        PROTOCOL,
        CONTROLS,
        ROOT / "tests/unit/test_cross_lingual_relation_audit.py",
        ROOT / "scripts/event_value_ownership_audit.py",
        ROOT / "scripts/retrieval_ablation.py",
        WINDOW / "report.json",
        WINDOW / "manifest.json",
        ROOT / "scripts/gigachat_answer_smoke.py",
    ]
    bindings = {**previous["bindings"], **files.bindings(new_paths)}
    controls = evaluate_controls()
    records = load_records()
    if len(records) != 328:
        raise ValueError("Incomplete frozen evidence inventory")
    output.mkdir(parents=True, exist_ok=False)
    (output / "records").mkdir()
    for path in new_paths:
        if path.is_relative_to(ROOT / "scripts") or path.is_relative_to(ROOT / "docs") or path.is_relative_to(ROOT / "tests"):
            destination = output / "source_snapshot" / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            files.save(destination, path.read_bytes())
    files.write(output / "frozen_inputs.json", {"version": VERSION, "bindings": bindings})
    reports = []
    for index, record in enumerate(records):
        validate_sources(record["trace"], corpus)
        proof = replay_service(record, settings)
        evidence = record["trace"]["evidence"]
        baseline = record["trace"]["metadata"]["evidence_adequacy"]
        analysis = audit(record["request"]["question"], evidence, baseline_adequate=baseline["adequate"])
        repeated = audit(record["request"]["question"], evidence, baseline_adequate=baseline["adequate"])
        if analysis != repeated:
            raise ValueError("Relation sidecar execution differs on repeat")
        item = {key: value for key, value in record.items() if key not in {"trace", "request"}}
        item.update(
            question=record["request"]["question"],
            baseline_adequacy=baseline,
            analysis=analysis,
            replay=proof,
            repeated_execution_identical=True,
            full_evidence=evidence if analysis["requirements"]["in_scope"] else None,
            frozen_full_trace_sha256=files.sha(files.encode(record["trace"])),
        )
        reports.append(item)
        files.write(output / f"records/{index:03d}.json", item)
        if (index + 1) % 20 == 0 or index + 1 == len(records):
            print(json.dumps({"completed_records": index + 1, "total_records": len(records)}), flush=True)
    corrupted = copy.deepcopy(records[0])
    corrupted["trace"]["retrieval"]["results"][0]["full_text"] += " corrupt"
    try:
        validate_sources(corrupted["trace"], corpus)
    except ValueError as exc:
        if str(exc) != "Frozen raw retrieval source differs: full_text":
            raise
    else:
        raise ValueError("Corrupted source accepted")
    corrupted = copy.deepcopy(records[0])
    corrupted["trace"]["metadata"]["evidence_adequacy"]["reason"] = "corrupt"
    try:
        replay_service(corrupted, settings)
    except ValueError as exc:
        if str(exc) != "Frozen full service trace or status differs":
            raise
    else:
        raise ValueError("Corrupted baseline trace accepted")
    import fitz

    for article in previous["articles"]:
        if files.sha(Path(article["original_pdf_path"]).read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
    for window in previous["reference_windows"]:
        with fitz.open(window["original_pdf_path"]) as pdf:
            raw = pdf[window["pdf_page"] - 1].get_text()
        if window["exact_text"] not in raw:
            raise ValueError("Fresh source anchor differs")
    files.verify(bindings)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    scoped = [row for row in reports if row["analysis"]["requirements"]["in_scope"]]
    summary = {
        "version": VERSION,
        "evidence_sets": len(reports),
        "service_full_trace_replays": len(reports),
        "diagnostic_executions": 2 * len(reports),
        "scoped_sets": len(scoped),
        "outside_scope_baseline_preserved": len(reports) - len(scoped),
        "textual_requirements_met_sets": sum(row["analysis"]["textual_requirements_met"] for row in scoped),
        "source_proposals": sum(len(row["analysis"]["proposals"]) for row in scoped),
        "baseline_true_textual_false": [
            i
            for i, row in enumerate(reports)
            if row["analysis"]["requirements"]["in_scope"]
            and row["baseline_adequacy"]["adequate"]
            and not row["analysis"]["textual_requirements_met"]
        ],
        "baseline_false_textual_true": [
            i
            for i, row in enumerate(reports)
            if row["analysis"]["requirements"]["in_scope"]
            and not row["baseline_adequacy"]["adequate"]
            and row["analysis"]["textual_requirements_met"]
        ],
        "exact_duplicate_source_groups": sum(len(row["analysis"]["duplicates"]) for row in scoped),
        "repeated_proposal_span_groups": sum(len(row["analysis"].get("repeated_proposal_spans", [])) for row in scoped),
        "control_count": len(controls["records"]),
        "expected_control_behavior_agreements": controls["expected_behavior_agreements"],
        "informative_but_unresolved_controls": controls["informative_but_unresolved_controls"],
        "corrupted_source_rejected": True,
        "corrupted_baseline_rejected": True,
        "verified_bindings": len(bindings),
        "pdf_hashes_checked": len(previous["articles"]),
        "fresh_reference_windows": len(previous["reference_windows"]),
        "runtime_changed": False,
        "db_calls": 0,
        "search_calls": 0,
        "embedding_calls": 0,
        "model_calls": 0,
        "oauth_calls": 0,
        "slot_reservations": 0,
        "network_denials": policy.denied,
        "scientific_acceptance": "not_established",
        "independent_accuracy": None,
        "answer_quality_plan_completion_percent": 75,
        "limits": [
            "finite morphology question scope; textual grammar is not scientific entailment",
            "condition surfaces retain unverified owners; constrained questions stay unresolved",
            "implicit relations, unnamed solvent variables and unrestricted anaphora unresolved",
            "exposed development inputs; no new model answers or runtime decisions",
            "browser/PDF visual QA/full suite/mypy not run",
        ],
    }
    report = {
        "summary": summary,
        "bindings": bindings,
        "controls": controls,
        "records": reports,
        "articles": previous["articles"],
        "reference_windows": previous["reference_windows"],
    }
    files.write(output / "report.json", report)
    render(report, output)
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
