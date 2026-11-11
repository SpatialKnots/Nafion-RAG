"""Source-bound offline Methods policy review; no send mode and no writable DB."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from html import escape, unescape
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import fitz
from sqlalchemy.engine import Engine

from app.generation import answer_facts, service
from app.generation.methods_identity import POLICY, prepare
from app.generation.presentation import capture_sources
from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError, ProviderResult
from app.retrieval.search import SearchResponse, SearchResult
from app.ui import _answer_payload_panel, _prepared_statement_text
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_answer_fidelity_20261105 import native
from scripts.check_requested_context_runtime_20261105 import render
from scripts.methods_identity_runtime_20261109 import BASE, PROTOCOL
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail
from scripts.review_methods_identity_bridge_20261109 import anchors


class Synthetic:
    def __init__(self, mode):
        self.mode = mode

    def generate(self, question, evidence, **kwargs):
        records = answer_facts.selection_records(evidence)
        claims = [GeneratedClaim(k, [r["citation_id"]]) for k, r in records.items()]
        if self.mode == "invalid":
            claims.pop()
        return ProviderResult(self.mode != "abstain", [] if self.mode == "abstain" else claims,
                              "SYNTHETIC_METHODS_POLICY", None)


def run(output: Path, disabled: Path, enabled: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    for folder in (BASE / "freeze_v01", disabled, enabled):
        files.verify_manifest(folder)
    suites = list(ET.parse(junit).getroot().iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    scope = read(junit.with_suffix(".scope.json"))
    if counts["failures"] or counts["errors"] or scope["exit_code"] or scope["external_network_denials"]:
        raise ValueError("Affected tests failed or external network attempted")
    files.verify(scope["test_bindings"])
    initial = read(BASE / "freeze_v01/bindings.json")
    changes = [{"path": name, "before": digest, "after": files.sha(Path(name).read_bytes())}
               for name, digest in initial.items() if Path(name).is_relative_to(files.ROOT / "app")
               and files.sha(Path(name).read_bytes()) != digest]
    expected_changes = {"app/core/config.py", "app/generation/answer_facts.py", "app/generation/service.py", "app/ui.py"}
    if {Path(c["path"]).relative_to(files.ROOT).as_posix() for c in changes} != expected_changes:
        raise ValueError("Unexpected old app drift")
    new_modules = {str(p.resolve()) for p in (files.ROOT / "app").rglob("*.py")} - set(initial)
    if new_modules != {str((files.ROOT / "app/generation/methods_identity.py").resolve())}:
        raise ValueError("Unexpected new app module")
    cases = read(files.ROOT / "output/methods_identity_bridge_20261109/controls_v02.json")
    controls = []
    for case in cases:
        bundle = prepare(case["question"], [Evidence(**s) for s in case["sources"]], case["reference"], case["layers"], policy=POLICY)
        if bundle.eligible != case["expected_candidate"]:
            raise ValueError("Declared audit control differs: " + case["id"])
        if bundle.eligible:
            answer_facts.selection_records(bundle.evidence)
        controls.append({"id": case["id"], "origin": case.get("origin", "exposed_real"),
                         "eligible": bundle.eligible, "reason": bundle.reason})
    case = cases[0]
    source_evidence = [Evidence(**s) for s in case["sources"]]
    bundle = prepare(case["question"], source_evidence, case["reference"], case["layers"], policy=POLICY)
    rows = [SearchResult(s.article_id, s.chunk_id, s.title, s.doi, s.page_start, s.page_end, s.source_type,
            s.text, s.score, s.retrieval_method, full_text=s.text, text_layer=case["layers"][s.chunk_id]) for s in source_evidence]
    retrieval = SearchResponse(case["question"], rows, {"explicit_source_reference": case["reference"]})
    settings = files.configure().model_copy(update={"rag_methods_identity_policy": POLICY})
    actual, captured_trace = [], []
    for mode in ("complete", "abstain", "invalid"):
        def observe(retrieval, evidence, metadata, mode=mode):
            if mode == "complete":
                captured_trace.append({"retrieval": {"query": retrieval.query}, "evidence": [vars(e) for e in evidence],
                                       "metadata": metadata})

        with patch.object(service, "search_chunks", return_value=retrieval), \
                patch.object(Engine, "connect", side_effect=AssertionError("Offline review forbids DB")):
            try:
                response = service.answer_question(None, settings, case["question"], answer_language="ru",
                                                   provider=Synthetic(mode), trace_observer=observe)
            except GenerationOutputError as exc:
                if mode != "invalid":
                    raise
                result = {"mode": mode, "rejected": True, "error": str(exc)}
            else:
                if response.status != ("answered" if mode == "complete" else "insufficient_evidence"):
                    raise ValueError("Synthetic actual service outcome differs")
                result = {"mode": mode, "response": service.answer_response_to_dict(response)}
        files.write(output / f"SYNTHETIC_{mode}_service.json", result)
        actual.append(result)
    if len(captured_trace) != 1 or len(captured_trace[0]["evidence"]) != 3:
        raise ValueError("New graph not active in actual service trace")
    trace = captured_trace[0]
    # The service assigns request-local E IDs in retrieval order. Compare native
    # witnesses with those actual IDs, not the diagnostic packet's old numbering.
    by_chunk = {s.chunk_id: s for s in source_evidence}
    source_evidence = [replace(by_chunk[e["chunk_id"]], citation_id=e["citation_id"]) for e in trace["evidence"]]
    bundle = prepare(case["question"], source_evidence, case["reference"], case["layers"], policy=POLICY)
    if not bundle.eligible:
        raise ValueError("Actual service sources cannot reproduce the graph")
    files.write(output / "SYNTHETIC_complete_trace.json", trace)
    captured = native("REAL_SOURCE_POLICY", trace, settings, output)
    body = read(output / "REAL_SOURCE_POLICY_native_unsent.json")
    decoded = json.loads(body["messages"][-1]["content"].split("Source-bound records:\n", 1)[1])
    if decoded != answer_facts.prompt_records([Evidence(**e) for e in trace["evidence"]]):
        raise ValueError("Decoded actual native records differ")
    for row in decoded:
        parent = next(s for s in source_evidence if s.citation_id == row["citation_id"])
        if not all(f["source_quote"] in parent.text for f in row["source_bound_facts"]):
            raise ValueError("Actual native fact quote missing from raw source")
        if row["source_role_assembly"]["witnesses"] != bundle.assembly["witnesses"]:
            raise ValueError("Actual native definitions differ")
    files.write(output / "decoded_actual_native_records.json", decoded)

    articles, corpus = read(CORPUS_BASE / "Q01/articles.json"), read(CORPUS_BASE / "Q01/corpus.json")
    pdfs, fresh = [], {}
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        pdfs.append(path)
    for source in source_evidence:
        raw_parent = corpus[source.chunk_id]
        if source.text != raw_parent["full_text"] or source.source_type != raw_parent["source_type"]:
            raise ValueError("Source text or registered type changed")
        with fitz.open(articles[source.article_id]["original_pdf_path"]) as pdf:
            for number in range(source.page_start, source.page_end + 1):
                fresh[(source.article_id, number)] = pdf[number - 1].get_text()
                pdf[number - 1].get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(str(output / f"page_{number:02}.png"))
    matches = []
    bound = anchors(bundle.assembly["bindings"])
    for anchor in bound:
        parent = next(s for s in source_evidence if s.chunk_id == anchor["chunk_id"])
        found = [n for (article, n), text in fresh.items() if article == anchor["article_id"]
                 and anchor["page_start"] <= n <= anchor["page_end"] and anchor["text"] in text]
        if (parent.text[anchor["start"]:anchor["end"]] != anchor["text"]
                or files.sha(parent.text.encode()) != anchor["raw_chunk_sha256"] or not found):
            raise ValueError("Raw/fresh PDF anchor differs")
        matches.append({"anchor": anchor, "fresh_pdf_pages": found})

    # Preserve exact runtime fragment. Only the standalone review copy remaps
    # observed source links to known original PDFs; source/claim text is unchanged.
    ui_fragment = _answer_payload_panel(actual[0]["response"], case["question"],
        capture_sources(retrieval, [Evidence(**e) for e in trace["evidence"]]))
    files.save(output / "runtime_ui_original.html", ui_fragment.encode())
    links = {}
    for href in re.findall(r"href='([^']*)'", ui_fragment):
        path = urlparse(unescape(href)).path
        matching = [s for s in source_evidence if path in {f"/ui/articles/{s.article_id}", f"/articles/{s.article_id}/pdf"}
                    or path in {f"/ui/articles/{s.article_id}/chunks/{s.chunk_id}/context",
                                f"/articles/{s.article_id}/chunks/{s.chunk_id}/context"}]
        if not matching:
            raise ValueError("Unmapped runtime UI link: " + path)
        source = matching[0]
        page = re.search(r"page=(\d+)", unescape(href))
        number = int(page[1]) if page else source.page_start
        target = Path(articles[source.article_id]["original_pdf_path"]).as_uri() + "#page=" + str(number)
        links[href] = target
    ui_local = re.sub(r"href='([^']*)'", lambda m: "href='" + escape(links[m[1]], quote=True) + "'", ui_fragment)
    ui_document = ("<!doctype html><html lang='ru'><meta charset='utf-8'><title>ARIADNE — Methods policy UI</title>"
        "<style>body{font:16px/1.5 system-ui;color:#183044;margin:25px}.claim-card,.source-card{border:1px solid #abc;"
        "padding:16px;margin:15px 0}.citation-chip{display:inline-block;padding:6px;margin:4px;background:#eef4f8}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}table{width:100%;table-layout:fixed}td{overflow-wrap:anywhere}"
        "details{margin:8px 0}summary{cursor:pointer}.muted{color:#526577}</style><body>"
        "<h1>Проверка UI на реальных источниках</h1><p>Ответ SYNTHETIC: F-ID выбраны фикстурой. "
        "Новых ответов модели нет. В этой локальной копии ссылки контекста ведут на оригинальные PDF.</p>"
        + ui_local + "</body></html>")
    files.save(output / "runtime_ui.html", ui_document.encode())
    display = [_prepared_statement_text(e.text, answer_facts.SOURCE_TYPE) for e in bundle.evidence]
    files.write(output / "UI_prepared_text.json", display)

    summary = {"policy": POLICY, "default": "disabled", "affected_tests": counts,
        "default_comparison": read(disabled / "service/summary.json"),
        "enabled_comparison": read(enabled / "service/summary.json"), "controls": controls,
        "exposed_real_source_graph_complete": bundle.eligible, "synthetic_service": actual,
        "native_unsent": captured, "native_definition_witnesses_per_record": len(bundle.assembly["witnesses"]),
        "raw_anchor_observations": len(bound), "unique_raw_anchors": len({(a["chunk_id"], a["start"], a["end"]) for a in bound}),
        "corpus_PDF_hashes": len(pdfs), "fresh_pages": [{"article_id": a, "page": n, "sha256": files.sha(t.encode())}
            for (a, n), t in fresh.items()], "runtime_drift": changes, "new_modules": sorted(new_modules),
        "actual_UI_link_targets": links, "real_model_calls": 0, "real_oauth_exchanges": 0, "new_slots": 0,
        "new_DB_preparation": False, "independent_scientific_accuracy": None,
        "limitations": ["One exposed work and an explicitly selected ordered-list assumption",
            "Complete real Abstract already supports the legacy fact path: no new answer/refusal gain established",
            "Actual service/ASGI outcomes are synthetic, not real provider answers",
            "No fresh DB retrieval, live behavior, cache-ORM/concurrency/deployment or independent evaluation"]}
    prior = read(files.ROOT / "output/methods_identity_bridge_20261109/review_final_v01/report.json")
    report = {"summary": summary, "cases": copy.deepcopy(prior["cases"]), "articles": articles,
              "regressions": summary["enabled_comparison"]["regressions"], "graph": bundle.assembly, "source_matches": matches}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Opt-in: проверяемая связь через Methods")
    extra = ("<h2>Новый контракт Methods</h2><p>Полный пакет реального источника проходит новый конечный контракт. "
        "Ранее он уже проходил старый путь фактов через Abstract. Улучшение научной точности или отказов не измерено.</p>"
        + detail("Полная цепочка и явное допущение списков", bundle.assembly)
        + detail("Реальный native prompt, без отправки", decoded)
        + detail("Synthetic actual service", actual)
        + "<h3>UI: синтетический ответ по исходным фрагментам</h3><iframe src='runtime_ui.html' "
          "title='Methods policy UI' style='width:100%;height:1100px;border:1px solid #abc'></iframe>")
    for number in (1, 3, 7):
        extra += (f"<details><summary>Свежий рендер PDF {number}</summary>"
                  f"<img src='page_{number:02}.png' style='max-width:100%' alt='PDF page {number}'></details>")
    document = document.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(document, article_count=len(articles), case_count=5)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL,
        files.ROOT / "docs/records/methods_identity_runtime_amendment_2026-11-09_v0.2.md",
        files.ROOT / "tests/unit/test_methods_identity_runtime.py", junit, junit.with_suffix(".scope.json"), *pdfs]
    report["bindings"] = files.bindings(paths)
    files.verify(report["bindings"])
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", document.encode())
    return {k: v for k, v in summary.items() if k not in {"default_comparison", "enabled_comparison", "synthetic_service", "controls"}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--disabled", type=Path, required=True)
    parser.add_argument("--enabled", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.output, args.disabled, args.enabled, args.junit)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
