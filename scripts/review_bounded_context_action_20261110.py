"""Export one-action controls, verify recorded replay/hash chains and original PDFs."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from unittest.mock import Mock

import fitz

from app.generation.answer_evidence_packet import serialize_packet
from app.generation.bounded_context_action import VERSION, run_context_action, validate_context_result
from app.generation.context_action_routes import render_context_action
from app.generation.preparation_routes import PreparationRequest
from app.retrieval.search import SearchResult
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.bounded_context_action_20261110 import BASE, PROTOCOL
from scripts.bounded_context_controls_20261110 import packet, registry
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.review_answer_evidence_packet_20261109 import independent_digest
from scripts.review_answer_requirements_20261109 import local_links
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail


def check_chain(result: dict) -> int:
    previous = result["input_packet"]["journal"]["root_hash"]
    for i, event in enumerate(result["journal"]["events"], 1):
        body = {k: v for k, v in event.items() if k != "event_hash"}
        if (event["sequence"] != i or event["previous_hash"] != previous
                or independent_digest(body) != event["event_hash"]
                or event["actor_kind"] != "deterministic_system"):
            raise ValueError("Independent action journal check failed")
        previous = event["event_hash"]
    if (previous != result["journal"]["root_hash"]
            or independent_digest({k: v for k, v in result.items() if k != "result_id"}) != result["result_id"]):
        raise ValueError("Action root/result hash differs")
    validate_context_result(result, result["input_packet"], expected_result_id=result["result_id"])
    return len(result["journal"]["events"])


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    (output / "results").mkdir()
    for folder in (BASE / "freeze_v01", BASE / "pre_v02_snapshot", comparison,
                   BASE / "pipeline_probe_v01", BASE / "pipeline_probe_v02"):
        files.verify_manifest(folder)
    scope = read(junit.with_suffix(".scope.json"))
    files.verify(scope["test_bindings"])
    files.verify(scope["app_bindings"])
    counts = {k: sum(int(s.get(k, 0)) for s in ET.parse(junit).getroot().iter("testsuite"))
              for k in ("tests", "errors", "failures", "skipped")}
    if scope["exit_code"] or scope["external_network_denials"] or counts["errors"] or counts["failures"]:
        raise ValueError("Affected test scope failed")
    initial = read(BASE / "freeze_v01/bindings.json")
    drift = [name for name, digest in initial.items() if Path(name).is_relative_to(files.ROOT / "app")
             and files.sha(Path(name).read_bytes()) != digest]
    if {Path(p).relative_to(files.ROOT).as_posix() for p in drift} != {
            "app/main.py", "app/generation/preparation_routes.py"}:
        raise ValueError("Unexpected old app drift")
    new = {str(p.resolve()) for p in files.ROOT.joinpath("app").rglob("*.py")} - set(initial)
    if new != {str((files.ROOT / p).resolve()) for p in
               ("app/generation/bounded_context_action.py", "app/generation/context_action_routes.py")}:
        raise ValueError("Unexpected new app modules")
    outcomes, ui_results, total_events = [], [], 0
    for i, case in enumerate(read(BASE / "controls_v01.json")):
        original = packet(case)
        before = copy.deepcopy(original)
        loader = Mock(return_value=[SearchResult(**r) for r in case["rows"]])
        registrar = Mock(side_effect=registry)
        result = run_context_action(original, loader, registrar)
        added = result["added_evidence"] is not None
        if (added != case["expected_added"] or original != before or loader.call_count != 1
                or registrar.call_count != int(added) or result["admission_changed"]):
            raise ValueError("Declared one-action control differs: " + case["id"])
        if added:
            after = result["candidate_map_input_adapter"]
            if any(after[k] != original["content"]["parent"]["preparation"][k]
                   for k in ("status", "blocking_reasons", "baseline_metadata")):
                raise ValueError("Original restrictions changed")
        total_events += check_chain(result)
        target = output / f"results/action_{i:03}.json"
        files.save(target, serialize_packet(result))
        if serialize_packet(read(target)) != target.read_bytes():
            raise ValueError("Canonical result roundtrip differs")
        outcomes.append({"id": case["id"], "constructed": True, "added": added,
                         "stop_reason": result["stop_reason"], "consumed": result["consumed"],
                         "result_id": result["result_id"], "file": str(target)})
        ui_results.append((case["id"], result))
    old_outcomes = []
    for i, case in enumerate(read(files.ROOT / "output/answer_requirements_20261109/controls_v01.json")):
        prepared = copy.deepcopy(case)
        prepared["request_scope"] = PreparationRequest(question=case["parent"]["question"],
            collection="offline_fixture", method="exact").model_dump(mode="json")
        original = packet(prepared)
        forbidden = Mock(side_effect=AssertionError("No additional lookup/registry allowed"))
        result = run_context_action(original, forbidden, forbidden)
        if forbidden.call_count or result["added_evidence"]:
            raise ValueError("Prior requirement control unexpectedly acted")
        total_events += check_chain(result)
        files.save(output / f"results/prior_{i:03}.json", serialize_packet(result))
        old_outcomes.append({"id": case["id"], "reason": result["stop_reason"], "additional_lookup_calls": 0})
        if i == 0:
            real_packet = original
            ui_results.append(("real_Lin_full_context_no_gap", result))
    pipeline = read(BASE / "pipeline_probe_v02/result.json")
    pipeline_summary = read(BASE / "pipeline_probe_v02/summary.json")
    pipeline_events = check_chain(pipeline)
    if (not pipeline_summary["added"] or pipeline_summary["lookup_calls"] != 1
            or pipeline_summary["generation_provider_calls"] != 0
            or not pipeline["plan"]["inherited_empty_qualifier_rejection_preserved"]):
        raise ValueError("Actual synthetic preparation pipeline did not execute declared step")
    previous_pipeline = read(BASE / "pipeline_probe_v01/result.json")
    if previous_pipeline["input_packet_id"] != pipeline["input_packet_id"]:
        raise ValueError("Version amendment unexpectedly changed original preparation packet")
    files.write(output / "control_outcomes.json", outcomes)
    files.write(output / "prior_control_outcomes.json", old_outcomes)
    articles, corpus = read(CORPUS_BASE / "Q01/articles.json"), read(CORPUS_BASE / "Q01/corpus.json")
    pdfs, fresh = [], {}
    for a in articles.values():
        path = Path(a["original_pdf_path"])
        if files.sha(path.read_bytes()) != a["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        pdfs.append(path)
    for source in real_packet["content"]["sources"]:
        raw = corpus[source["chunk_id"]]
        if source["raw_text"] != raw["full_text"] or source["source_type"] != raw["source_type"]:
            raise ValueError("Real selected raw corpus text differs")
        with fitz.open(articles[source["article_id"]]["original_pdf_path"]) as pdf:
            for n in range(source["page_start"], source["page_end"] + 1):
                fresh[(source["article_id"], n)] = pdf[n - 1].get_text()
                pdf[n - 1].get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(str(output / f"page_{n:02}.png"))
    matches = []
    sources = {s["id"]: s for s in real_packet["content"]["sources"]}
    for item in real_packet["content"]["anchors"]:
        anchor, source = item["anchor"], sources[item["source_ref"]]
        pages = [n for (a, n), text in fresh.items() if a == anchor["article_id"]
                 and anchor["page_start"] <= n <= anchor["page_end"] and anchor["text"] in text]
        if (source["raw_text"][anchor["start"]:anchor["end"]] != anchor["text"]
                or files.sha(source["raw_text"].encode()) != anchor["raw_chunk_sha256"] or not pages):
            raise ValueError("Real raw anchor not reproduced on fresh declared PDF page")
        matches.append({"anchor": anchor, "fresh_PDF_pages": pages})
    fragments, links = [], []
    for i, (name, result) in enumerate(ui_results):
        fragment = render_context_action(result)
        files.save(output / f"runtime_UI_{i:03}.html", fragment.encode())
        local, mapped = local_links(fragment, articles)
        links.append({"id": name, "links": mapped})
        fragments.append('<div data-action-case="' + escape(name, quote=True) + '"><h2>' + escape(name)
                         + " — synthetic preparation</h2>" + local + "</div>")
    document = ("<!doctype html><html lang='ru'><meta charset='utf-8'><title>ARIADNE — один шаг контекста</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:1150px;margin:25px auto;padding:0 20px;color:#183044}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}"
        "td,th{padding:8px;border:1px solid #abc}details{margin:8px 0}summary{cursor:pointer}</style><body>"
        "<h1>Один явный шаг дополнения контекста</h1><p>Все положительные добавления искусственные. "
        "Реальная раскрытая работа Lin уже содержит CE: дополнительного поиска нет. "
        "Научное качество и новый допуск ответов не измерены.</p>" + "".join(fragments) + "</body></html>")
    if document.count("data-context-action") != len(ui_results) or document.count("<tbody>") != len(ui_results):
        raise ValueError("Action UI case/table inventory differs")
    files.save(output / "context_action_UI.html", document.encode())
    files.write(output / "UI_links.json", links)
    summary = {"version": VERSION, "tests": counts, "external_network_denials": scope["external_network_denials"],
        "constructed_action_controls": len(outcomes), "constructed_additions": sum(c["added"] for c in outcomes),
        "prior_controls_without_lookup": len(old_outcomes), "control_journal_events": total_events,
        "synthetic_pipeline_journal_events": pipeline_events, "synthetic_pipeline": pipeline_summary,
        "v01_v02_original_pipeline_packet_identical": True,
        "final_frozen_comparison": read(comparison / "service/summary.json"), "old_app_drift": drift, "new_modules": sorted(new),
        "corpus_PDF_hashes": len(pdfs), "fresh_pages": [{"article_id": a, "page": n, "sha256": files.sha(t.encode())}
            for (a, n), t in fresh.items()], "unique_raw_anchors": len(matches),
        "anchor_observations": real_packet["content"]["inspection"]["anchor_observations"],
        "real_model_calls": 0, "real_oauth_exchanges": 0, "new_slots": 0, "fresh_DB_preparation": False,
        "independent_scientific_accuracy": None, "browser_layout": "not_verified_prior_file_URL_policy_block",
        "limitations": ["Finite explicit-label missing-CE family, all additions constructed",
            "No real SQL execution/new natural answer or refusal improvement measured",
            "Original baseline and scientific support unchanged; no automatic continuation",
            "Trusted current code/parent required for replay; journal is not human review"]}
    prior = read(files.ROOT / "output/answer_evidence_packet_20261109/review_v01/report.json")
    report = {"summary": summary, "cases": copy.deepcopy(prior["cases"]), "articles": articles,
        "regressions": summary["final_frozen_comparison"]["regressions"], "controls": outcomes, "source_matches": matches}
    html = render(report).replace("Сохранение запрошенного контекста в runtime", "Один ограниченный шаг дополнения контекста")
    extra = ("<h2>Явный ограниченный шаг</h2><p>Один lookup, один raw-чанк, неизменный исходный пакет. "
        "Два положительных контроля constructed; scientific_support не оценена. "
        "v0.1 остановилась на наследованном пустом qualifier-отказе; v0.2 точно воспроизводит этот частный случай, "
        "не меняя исходные blockers.</p>" + detail("15 controls и27 прежних no-lookup случаев", [outcomes, old_outcomes])
        + detail("Сквозная synthetic preparation → packet → action", pipeline_summary)
        + "<iframe src='context_action_UI.html' title='One explicit context action UI' "
          "style='width:100%;height:1100px;border:1px solid #abc'></iframe>" + detail("Raw/PDF anchors", matches))
    for n in (1, 3, 7):
        extra += (f"<details><summary>Свежий PDF-рендер {n}</summary>"
                  f"<img src='page_{n:02}.png' style='max-width:100%' alt='PDF {n}'></details>")
    html = html.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(html, article_count=len(articles), case_count=5)
    qa.update(action_UI_cases=len(ui_results), independently_checked_action_events=total_events + pipeline_events)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL,
        files.ROOT / "docs/records/bounded_context_action_amendment_2026-11-10_v0.2.md",
        *[files.ROOT / p for p in ("scripts/bounded_context_action_20261110.py",
            "scripts/bounded_context_controls_20261110.py", "scripts/test_bounded_context_action_20261110.py",
            "scripts/probe_context_pipeline_20261110.py", "tests/unit/test_bounded_context_action.py")],
        BASE / "controls_v01.json", junit, junit.with_suffix(".scope.json"), *pdfs]
    report["bindings"] = files.bindings(paths)
    files.verify(report["bindings"])
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", html.encode())
    return {k: v for k, v in summary.items() if k not in {"final_frozen_comparison", "old_app_drift", "new_modules"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, args.comparison, args.junit)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
