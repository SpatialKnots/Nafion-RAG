"""Verify fresh unsent inputs and render a local-link review from saved controls."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.generation.answer_facts import prompt_records, selection_records
from app.generation.fact_types import Anchor, verify_anchor
from app.generation.providers import Evidence
from scripts import gigachat_answer_smoke as files
from scripts.check_requested_context_runtime_20261105 import render
from scripts.check_structured_answers_20261105 import BASE, INTAKE, LIVE, ROOT
from scripts.review_benchmark_retrieval_repair_20261105 import ReviewStructure, check_html, detail, presence

IDS = ("Q01", "Q02", "Q04", "Q05")


def read(path):
    return json.loads(path.read_bytes())


def rewrite_links(fragment, articles, citations):
    """Map complete attributes, not substrings shared by several app routes."""
    chunks = {c["chunk_id"]: c for c in citations}

    def replace_href(match):
        original = html.unescape(match[2])
        uri = urlparse(original)
        if uri.scheme == "file":
            return match.group()
        target = re.fullmatch(r"/(?:ui/)?articles/([0-9a-f-]+)(?:/.*)?", uri.path)
        if target is None or target[1] not in articles:
            raise ValueError("Unregistered application link in offline preview")
        article = articles[target[1]]
        page = parse_qs(uri.query).get("page", [None])[0]
        if page is None:
            parsed_page = re.search(r"(?:^|&)page=(\d+)", uri.fragment)
            page = parsed_page[1] if parsed_page else None
        if page is None:
            chunk = re.search(r"/chunks/([0-9a-f-]+)", uri.path)
            if chunk:
                if chunk[1] not in chunks or chunks[chunk[1]]["article_id"] != target[1]:
                    raise ValueError("Unregistered chunk link in offline preview")
                page = str(chunks[chunk[1]]["page_start"])
        url = Path(article["original_pdf_path"]).as_uri()
        if page is not None:
            if not re.fullmatch(r"[1-9]\d*", str(page)):
                raise ValueError("Invalid PDF page in offline preview")
            url += "#page=" + str(page)
        return "href=" + match[1] + html.escape(url, quote=True) + match[1]

    return re.sub(r"href=([\"'])(.*?)\1", replace_href, fragment)


def anchors(value):
    if isinstance(value, dict):
        if {"raw_chunk_sha256", "start", "end", "text", "citation_id", "page_start"} <= set(value):
            yield value
        else:
            for child in value.values():
                yield from anchors(child)
    elif isinstance(value, list):
        for child in value:
            yield from anchors(child)


def verify(output):
    from app import ui
    from app.generation.presentation import capture_sources
    from app.retrieval.search import SearchResponse, SearchResult

    source = BASE / "review_v02"
    files.verify_manifest(source)
    files.verify_manifest(BASE / "review_v01")
    files.verify_manifest(BASE / "freeze_v01")
    report = read(source / "report.json")
    files.verify(report["bindings"])
    suite = ET.parse(BASE / "tests_affected_v02.xml").getroot()
    if len(list(suite.iter("testcase"))) != 544 or any(list(suite.iter(tag)) for tag in ("failure", "error", "skipped")):
        raise ValueError("Expected544 affected tests passed")
    scope = read(BASE / "tests_affected_v02.scope.json")
    files.verify(scope["test_bindings"])
    if scope["exit_code"] != 0 or scope["external_network_denials"]:
        raise ValueError("Test scope did not complete offline")
    gold = ROOT / "docs/records/Nafion_RAG_Benchmark_v1.0_original.md"
    if files.sha(gold.read_bytes()) != "8b5450878bf9791635767f800616c38e8f1d9108852563171b8af8d1a3677332":
        raise ValueError("Original gold changed")
    reference = read(INTAKE / "report.json")
    fresh, occurrences, unique = [], 0, set()
    output.mkdir(parents=True, exist_ok=False)
    examples = "<h2>Русские ответы — SYNTHETIC, не новый результат модели</h2>"
    for cid in IDS:
        folder = BASE / "fresh_v01" / cid
        files.verify_manifest(folder)
        contract = read(folder / "contract.json")
        files.verify(contract["input_bindings"])
        trace = read(folder / "trace.json")
        if (trace != read(source / f"{cid}_repaired.json")["trace"]
                or (folder / "request.json").read_bytes() != (source / f"{cid}_native_unsent.json").read_bytes()
                or contract["transaction_read_only"] != "on" or contract["transaction_end"] != "rollback"
                or any(contract[k] != 0 for k in ("model_calls", "oauth_calls", "new_slots", "maximum_model_attempts",
                                                 "maximum_oauth_attempts"))
                or contract["network_denials"] or contract["gold_read_denials"] or contract["source_registry_diagnostics"]):
            raise ValueError("Fresh preparation differs from offline read-only scope")
        if (files.LEDGER / contract["request_sha256"]).exists():
            raise ValueError("New request unexpectedly has a live slot")
        evidence = [Evidence(**e) for e in trace["evidence"]]
        by_id = {e.citation_id: e for e in evidence}
        raw = {e.citation_id: Evidence(**{**vars(e), "text": json.loads(e.text)["raw_source"]}) for e in evidence}
        records = selection_records(evidence)
        old_records = read(BASE / f"review_v01/{cid}_repaired.json")["trace"]["metadata"]["source_facts"]["records"]
        if [(r["facts"], r["arithmetic"]) for r in records.values()] != [(r["facts"], r["arithmetic"]) for r in old_records]:
            raise ValueError("v0.2 presentation-only change altered facts/arithmetic")
        for record in records.values():
            for anchor in anchors(record):
                verify_anchor(Anchor(**anchor), raw[anchor["citation_id"]])
                occurrences += 1
                unique.add((anchor["article_id"], anchor["chunk_id"], anchor["start"], anchor["end"]))
        body = read(folder / "request.json")
        supplied = json.loads(body["messages"][1]["content"].split("\nSource-bound records:\n", 1)[1])
        if supplied != prompt_records(evidence):
            raise ValueError("Native compact fact data differs")
        case = next(c for c in report["cases"] if c["id"] == cid)
        ref = next(c for c in reference["cases"] if c["id"] == cid)
        target = next(a for a in report["articles"].values() if Path(a["original_pdf_path"]).resolve()
                      == Path(ref["source_pdf_path_verbatim"]).resolve())
        literal = [{**vars(e), "text": "\n".join(f["source_quote"] for r in supplied if r["citation_id"] == key
                                                for f in r["source_bound_facts"])} for key, e in by_id.items()]
        pages = [p["pdf_page"] for p in reference["source_pages"] if p["case_id"] == cid]
        case["repaired"]["presence_scope"] = "raw_parent_inventory_server_side_not_literal_prompt_coverage"
        case["repaired"]["literal_prompt_source_quote_coverage"] = presence(literal, target["article_id"], pages, ref["quotes"])
        case["repaired"]["literal_prompt_source_quote_coverage"]["metric_scope"] = (
            "exact_raw_spans_in_decoded_source_quote_fields_not_semantic_fact_coverage")
        api = read(source / f"{cid}_complete_HTTP.json")
        retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                                   results=[SearchResult(**r) for r in trace["retrieval"]["results"]])
        fragment = ui._answer_payload_panel(api["body"], api["body"]["query"], capture_sources(retrieval, evidence))
        if fragment not in (source / f"{cid}_SYNTHETIC_ui_runtime.html").read_text(encoding="utf-8"):
            raise ValueError("Runtime UI changed since saved synthetic execution")
        local = rewrite_links(fragment, report["articles"], api["body"]["citations"])
        files.save(output / f"{cid}_SYNTHETIC_ui_local_fragment.html", local.encode())
        examples += detail(cid + " — прежний реальный ответ, без исправлений", read(LIVE / cid / "live/api_response.json"))
        examples += "<h3>" + cid + " — SYNTHETIC: серверная сводка и исходные цитаты</h3>" + local
        fresh.append({"case_id": cid, "request_bytes": contract["request_bytes"], "request_sha256": contract["request_sha256"],
                      "fact_records": len(records), "structured_facts": sum(len(r["facts"]) for r in records.values()),
                      "full_trace_and_native_identical": True})
    report["summary"]["verification"] = {"fresh_preparations": fresh, "raw_anchor_observations_verified": occurrences,
        "distinct_raw_anchor_addresses": len(unique), "tests_passed": 544, "new_fact_tests": 60,
        "v01_v02_fact_fields_and_arithmetic_identical": True, "display_links_only_rebuilt": True,
        "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0, "all_live_scopes_remain_closed": True}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Структурированные факты и русский ответ")
    document = document.replace("</style>", ".answer-lede,.claim-text{white-space:pre-wrap}.answer-card,.evidence-card"
                                "{padding:14px;border:1px solid #b5c5d0;margin:12px 0}</style>")
    note = ("<p>Таблица покрытия показывает инвентарь исходных родительских фрагментов на сервере. "
            "Компактный prompt получает поля фактов и отдельные точные цитаты; их буквальное покрытие показано "
            "отдельно в диагностике каждого случая. Эти счётчики не являются научной оценкой.</p>")
    document = document.replace("<h2>TAC: все работы снимка</h2>", examples + "<h2>TAC: все работы снимка</h2>")
    document = document.replace("<table><tr><th>Вопрос</th>", note + "<table><tr><th>Вопрос</th>", 1)
    structure = ReviewStructure()
    structure.feed(document)
    ui_sections = 0
    for cid in IDS:
        parser = ReviewStructure()
        parser.feed((output / f"{cid}_SYNTHETIC_ui_local_fragment.html").read_text(encoding="utf-8"))
        ui_sections += parser.sections
    if structure.sections != 5 + ui_sections or any(document.count(f"<section><h2>Q{i:02}</h2>") != 1 for i in range(1, 6)):
        raise ValueError("Final case/UI section inventory differs")
    qa = check_html(document, article_count=len(report["articles"]), case_count=structure.sections)
    paths = [Path(__file__), source / "manifest.json", BASE / "tests_affected_v02.xml", BASE / "tests_affected_v02.scope.json",
             ROOT / "docs/records/structured_answers_evaluation_amendment_2026-11-05_v0.1.md", gold,
             *[BASE / f"fresh_v01/{cid}/manifest.json" for cid in IDS]]
    bindings = files.bindings(paths)
    files.write(output / "verification.json", report["summary"]["verification"])
    files.write(output / "current_bindings.json", bindings)
    files.write(output / "report.json", report)
    files.save(output / "review.html", document.encode())
    files.write(output / "qa.json", {**qa, "case_sections": 5, "embedded_ui_sections": ui_sections})
    files.manifest(output)
    return report["summary"]["verification"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = verify(args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt in final review")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
