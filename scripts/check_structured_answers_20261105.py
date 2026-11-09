"""Offline structured-fact/native/service/UI checks; all new replies are synthetic."""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import fitz

from app.generation.answer_facts import selection_records, verify_raw_binding
from app.generation.providers import Evidence, GeneratedClaim, ProviderResult
from scripts import benchmark_retrieval_replay_20261105 as engine
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_answer_fidelity_20261105 import client, native
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE, INTAKE, OLD, inventory_scope
from scripts.review_benchmark_retrieval_repair_20261105 import ReviewStructure, check_html, detail, presence
from scripts.review_retrieval_ablation import unpack

ROOT = files.ROOT
BASE = ROOT / "output/structured_answers_20261105"
PREVIOUS = ROOT / "output/answer_fidelity_20261105/review_v03"
LIVE = ROOT / "output/user_benchmark_retest_20261105"
PROTOCOL = ROOT / "docs/records/structured_answers_protocol_2026-11-05_v0.1.md"


def raw_evidence(trace, corpus):
    rows = []
    for e in trace["evidence"]:
        parent = corpus[e["chunk_id"]]
        if e["source_type"] == "source_fact_derived":
            verify_raw_binding(e["text"], parent["full_text"], article_id=e["article_id"], chunk_id=e["chunk_id"],
                               citation_id=e["citation_id"], page_start=e["page_start"], page_end=e["page_end"])
            text = parent["full_text"]
        elif e["source_type"] == "reference_quote_derived":
            text = "\n".join(r["raw_span"]["text"] for r in json.loads(e["text"])["records"])
        else:
            text = e["text"]
            if text != parent["full_text"]:
                raise ValueError("Unexpected raw source drift")
        rows.append({**e, "text": text})
    return rows


def http_check(cid, trace, settings, output, mode, articles):
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    from app import ui
    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import service
    from app.generation.presentation import capture_sources
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    selected = [Evidence(**e) for e in trace["evidence"]]
    records = selection_records(selected)
    claims = [{"text": key, "citation_ids": [r["citation_id"]]} for key, r in reversed(list(records.items()))]
    if mode == "partial":
        claims.pop()
    if mode in {"unknown", "service_bypass"}:
        claims[0]["text"] = "F999"
    if mode == "abstention":
        claims = []
    content = {"answerable": mode != "abstention", "claims": claims}
    envelope = files.encode({"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
                 "content": json.dumps(content, ensure_ascii=False)}}]})
    calls = []

    class Proxy:
        def generate(self, q, evidence, **kwargs):
            provider = client(settings)

            def post(url, body, authorization, *, oauth=False):
                calls.append("fake_oauth" if oauth else "fake_model_ids")
                if oauth:
                    return b'{"access_token":"offline-placeholder"}'
                if body != (output / f"{cid}_native_unsent.json").read_bytes():
                    raise ValueError("HTTP/native bytes differ")
                return (LIVE / cid / "live/response.bin").read_bytes() if mode == "counterfactual_old_native" else envelope

            provider._post = post
            if mode == "service_bypass":
                return ProviderResult(True, [GeneratedClaim(**c) for c in claims], "SYNTHETIC_INVALID_IDS", None)
            result = provider.generate(q, evidence, **kwargs)
            return replace(result, provider="SYNTHETIC_STRUCTURED_FACT_SELECTION", model=None)

    retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                               results=[SearchResult(**r) for r in trace["retrieval"]["results"]])

    def no_session():
        yield object()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = no_session
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch.object(service, "search_chunks", return_value=retrieval), \
                patch.object(service, "build_answer_provider", return_value=Proxy()), \
                patch.object(Engine, "connect", side_effect=AssertionError("Offline HTTP forbids DB")):
            with TestClient(app) as test:
                response = test.post("/answer", json=read(LIVE / cid / "authorized_inputs/api_request.json"))
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    body = response.json()
    if mode in {"partial", "unknown", "service_bypass", "counterfactual_old_native"}:
        if response.status_code != 502:
            raise ValueError("Invalid or historical counterfactual selection was accepted")
    elif response.status_code != 200 or body["status"] != ("answered" if mode == "complete" else "insufficient_evidence"):
        raise ValueError("Synthetic positive/abstention failed")
    if mode == "complete":
        expected = [{"text": r["allowed_claim"], "citation_ids": [r["citation_id"]]} for r in records.values()]
        if body["claims"] != expected or not body["metadata"]["source_facts"]["active"]:
            raise ValueError("Public rendering differs from source-bound server rendering")
        fragment = ui._answer_payload_panel(body, body["query"], capture_sources(retrieval, selected))
        files.save(output / f"{cid}_SYNTHETIC_ui_runtime.html", ui._layout("SYNTHETIC — " + cid, fragment).body)
        replacements = {}
        for citation in body["citations"]:
            pdf = Path(articles[citation["article_id"]]["original_pdf_path"]).as_uri()
            for key in ("pdf_page_url", "context_url", "article_url", "pdf_url"):
                if isinstance(citation.get(key), str):
                    replacements[citation[key]] = pdf + "#page=" + str(citation["page_start"])
        # Registered article links in the runtime UI are also mapped, for this offline copy only.
        for citation in body["citations"]:
            replacements["/articles/" + citation["article_id"]] = Path(
                articles[citation["article_id"]]["original_pdf_path"]).as_uri()
        local = fragment
        for before, after in sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True):
            local = local.replace(html.escape(before, quote=True), html.escape(after, quote=True))
        files.save(output / f"{cid}_SYNTHETIC_ui_local_fragment.html", local.encode())
    files.write(output / f"{cid}_{mode}_HTTP.json", {"http_status": response.status_code, "body": body})
    if mode in {"complete", "abstention"}:
        files.save(output / f"{cid}_{mode}_SYNTHETIC_native_response.json", envelope)
    return {"case_id": cid, "mode": mode, "http_status": response.status_code, "simulated_boundaries": calls,
            "kind": "SYNTHETIC_OR_COUNTERFACTUAL_NOT_A_NEW_REAL_MODEL_RESULT", "real_model_oauth_db_calls": 0}


def run(output):
    from app.generation import service

    settings = files.configure()
    files.verify_manifest(BASE / "freeze_v01")
    output.mkdir(parents=True, exist_ok=False)
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"), Path(__file__), PROTOCOL,
             ROOT / "tests/unit/test_answer_facts.py", ROOT / "tests/unit/test_reference_quote_service.py",
             ROOT / "tests/unit/test_requested_context_service.py",
             ROOT / "docs/records/structured_answers_amendment_2026-11-05_v0.2.md"]
    bindings = files.bindings(paths)
    for path in paths:
        target = output / "source_snapshot" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        files.save(target, path.read_bytes())
    corpus, articles = read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")
    predictions, natives, http = {}, {}, []
    for number in range(1, 6):
        cid = f"Q{number:02}"
        source = read(CORPUS_BASE / cid / "boundaries.json")
        with inventory_scope(corpus, articles), patch.object(service, "prepare_answer_facts", return_value=None):
            before = engine.replay(source, settings, replacement=lambda r: r)
        if before["trace"] != read(PREVIOUS / f"{cid}_repaired.json")["trace"]:
            raise ValueError("Pre-fact full baseline differs")
        with inventory_scope(corpus, articles):
            after = engine.replay(source, settings, replacement=lambda r: r)
        if before["trace"]["retrieval"] != after["trace"]["retrieval"]:
            raise ValueError("Retrieval changed during structured rendering stage")
        if cid == "Q03" and before["trace"] != after["trace"]:
            raise ValueError("Out-of-scope Q03 full trace changed")
        if cid != "Q03" and not after["trace"]["metadata"]["source_facts"]["active"]:
            raise ValueError("Expected supported structured path: " + cid + " " + json.dumps(
                after["trace"]["metadata"].get("source_facts"), ensure_ascii=True))
        for arm, value in (("baseline", before), ("repaired", after)):
            files.write(output / f"{cid}_{arm}.json", value)
        predictions[cid] = {"baseline": before, "repaired": after}
        natives[cid] = native(cid, after["trace"], settings, output)
        if cid == "Q03" and (output / f"{cid}_native_unsent.json").read_bytes() != (PREVIOUS / f"{cid}_native_unsent.json").read_bytes():
            raise ValueError("Q03 native bytes changed")
    for cid in ("Q01", "Q02", "Q04", "Q05"):
        http += [http_check(cid, predictions[cid]["repaired"]["trace"], settings, output, mode, articles)
                 for mode in ("complete", "abstention", "partial", "unknown", "service_bypass", "counterfactual_old_native")]
    old_corpus, dataset = read(OLD / "corpus.json"), read(OLD / "cases.json")
    regressions = []
    for index, case in enumerate(dataset["cases"]):
        source = unpack(read(OLD / f"cases/{index:03}_baseline.json"), old_corpus)
        with patch.object(service, "prepare_answer_facts", return_value=None):
            before = engine.replay(source, settings)
        after = engine.replay(source, settings, replacement=lambda r: r)
        identical = before["trace"] == after["trace"]
        scoped = "source_facts" in after["trace"]["metadata"]
        if not scoped and not identical:
            raise ValueError("Out-of-scope full trace changed")
        regressions.append({"id": case["id"], "scoped": scoped, "full_trace_identical": identical})
        if index % 20 == 0:
            print(json.dumps({"old_cases_checked": index + 1}), flush=True)
    files.verify_manifest(INTAKE)
    gold, cases, fresh_pages, spans = read(INTAKE / "report.json"), [], 0, 0
    for ref in gold["cases"]:
        cid = ref["id"]
        target = next(a for a in articles.values() if Path(a["original_pdf_path"]).resolve()
                      == Path(ref["source_pdf_path_verbatim"]).resolve())
        pages = [p["pdf_page"] for p in gold["source_pages"] if p["case_id"] == cid]
        case = {"id": cid, "question": ref["question"]}
        for arm in ("baseline", "repaired"):
            value = predictions[cid][arm]
            evidence = raw_evidence(value["trace"], corpus)
            case[arm] = {"presence": presence(evidence, target["article_id"], pages, ref["quotes"]), "evidence": evidence,
                         "boundary": value["boundary"], "source_facts": value["trace"]["metadata"].get("source_facts")}
        cases.append(case)
    for page in gold["source_pages"]:
        ref = next(c for c in gold["cases"] if c["id"] == page["case_id"])
        with fitz.open(ref["source_pdf_path_verbatim"]) as pdf:
            raw = pdf[page["pdf_page"] - 1].get_text()
        if files.sha(raw.encode()) != page["sha256"]:
            raise ValueError("Fresh PDF page differs")
        fresh_pages += 1
        for span in [q["span"] for q in ref["quotes"] if q["span"] and q["pdf_page"] == page["pdf_page"]] + [
                n["raw_span"] for n in gold["source_notes"] if n["case_id"] == ref["id"] and n["pdf_page"] == page["pdf_page"]]:
            if raw[span["start"]:span["end"]] != span["text"]:
                raise ValueError("Reference raw span differs")
            spans += 1
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF differs")
        bindings.update(files.bindings([path]))
    for number in range(1, 6):
        folder = LIVE / f"Q{number:02}/live"
        files.verify_manifest(folder)
        bindings.update(files.bindings([folder / "manifest.json", folder / "api_response.json", folder / "response.bin"]))
    summary = {"version": "structured_answers_offline_v0.2", "exact_baselines": 81,
               "frozen_channel_service_runs": 162, "offline_http_checks": http, "native_unsent": natives,
               "old_scoped_cases": sum(r["scoped"] for r in regressions),
               "old_trace_changes": sum(not r["full_trace_identical"] for r in regressions),
               "fresh_reference_pages": fresh_pages, "fresh_raw_spans": spans,
               "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0, "scientific_accuracy": None,
               "limitations": ["Finite source grammars; Q03/unsupported/English requests keep the old path",
                   "Source binding and arithmetic are not independent scientific confirmation",
                   "Ambiguous raw units and unknown conditions remain explicit",
                   "All positive new outputs are SYNTHETIC, not actual provider responses", "Browser/full suite not tested"]}
    report = {"summary": summary, "bindings": bindings, "articles": articles, "cases": cases, "regressions": regressions}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Структурированные факты и русский ответ")
    examples = "<h2>Новые русские ответы — SYNTHETIC, не новый результат модели</h2>"
    for cid in ("Q01", "Q02", "Q04", "Q05"):
        examples += detail(cid + " — прежний реальный ответ, без исправлений", read(LIVE / cid / "live/api_response.json"))
        examples += "<h3>" + cid + " — SYNTHETIC UI, данные и текст формирует сервер</h3>"
        examples += (output / f"{cid}_SYNTHETIC_ui_local_fragment.html").read_text(encoding="utf-8")
    document = document.replace("<h2>TAC: все работы снимка</h2>", examples + "<h2>TAC: все работы снимка</h2>")
    files.verify(bindings)
    files.write(output / "report.json", report)
    files.save(output / "review.html", document.encode())
    structure = ReviewStructure()
    structure.feed(document)
    ui_sections = 0
    for cid in ("Q01", "Q02", "Q04", "Q05"):
        parser = ReviewStructure()
        parser.feed((output / f"{cid}_SYNTHETIC_ui_local_fragment.html").read_text(encoding="utf-8"))
        ui_sections += parser.sections
    if structure.sections != 5 + ui_sections or any(document.count(f"<section><h2>Q{i:02}</h2>") != 1 for i in range(1, 6)):
        raise ValueError("Case sections or embedded UI inventory differs")
    qa = check_html(document, article_count=len(articles), case_count=structure.sections)
    files.write(output / "qa.json", {**qa, "case_sections": 5, "embedded_ui_sections": ui_sections})
    files.manifest(output)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.output)
    if policy.denied:
        raise ValueError("Unexpected offline network attempt")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
