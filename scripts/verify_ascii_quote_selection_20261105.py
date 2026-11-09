"""Offline HTTP verification, source integrity and fresh unsent preparations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.ascii_quote_selection_checks_20261105 import BASE, CORPUS_BASE, INTAKE, PREVIOUS, ROOT, evaluated_evidence
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail

REVIEW = BASE / "review_v02"


def synthetic_http(case_id: str, output: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import service
    from app.generation.gigachat import GigaChatAnswerProvider
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    settings = files.configure()
    prepared = BASE / "fresh_v01" / case_id
    trace = read(prepared / "trace.json")
    retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                               results=[SearchResult(**r) for r in trace["retrieval"]["results"]])
    calls = []

    class Proxy:
        def generate(self, question: str, evidence: Any, **kwargs: Any) -> Any:
            client = GigaChatAnswerProvider(credentials="offline-placeholder", scope=settings.gigachat_scope,
                                           model=settings.rag_model, timeout_seconds=120, max_tokens=1200)

            def post(url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
                calls.append("fake_oauth" if oauth else "fake_model_id_response")
                if oauth:
                    return b'{"access_token":"offline-placeholder"}'
                if body != (prepared / "request.json").read_bytes():
                    raise ValueError("HTTP path native bytes differ from fresh preparation")
                return (REVIEW / f"{case_id}_SYNTHETIC_ID_response.json").read_bytes()

            client._post = post
            result = client.generate(question, evidence, **kwargs)
            return replace(result, provider="SYNTHETIC_ASCII_HTTP_TEST", model=None)

    def no_session():
        yield object()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = no_session
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch.object(service, "search_chunks", return_value=retrieval), \
                patch.object(service, "build_answer_provider", return_value=Proxy()), \
                patch.object(Engine, "connect", side_effect=AssertionError("Offline HTTP test forbids DB")):
            with TestClient(app) as client:
                response = client.post("/answer", json=read(prepared / "api_request.json"))
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    body = response.json()
    valid_prior = read(PREVIOUS / f"review_v02/{case_id}_SYNTHETIC_selection.json")
    if response.status_code != 200 or body["answer"] != valid_prior["answer"] or body["claims"] != valid_prior["claims"]:
        raise ValueError("Synthetic HTTP answer does not preserve original server quotations")
    if calls != ["fake_oauth", "fake_model_id_response"]:
        raise ValueError("Unexpected synthetic boundary count")
    files.write(output / f"{case_id}_SYNTHETIC_HTTP_response.json", {"http_status": response.status_code, "body": body})
    return {"case_id": case_id, "kind": "SYNTHETIC_NOT_A_REAL_MODEL_RESULT", "http_status": response.status_code,
            "public_answer_and_claims_identical_to_prior_valid_source_strings": True, "simulated_boundaries": calls,
            "real_model_calls": 0, "real_oauth_calls": 0, "db_calls": 0}


def verify(output: Path) -> dict[str, Any]:
    files.verify_manifest(REVIEW)
    files.verify_manifest(BASE / "freeze_v01")
    report = read(REVIEW / "report.json")
    files.verify(report["bindings"])
    output.mkdir(parents=True, exist_ok=False)
    fresh, old_live = [], {}
    for case_id in ("Q01", "Q05"):
        folder = BASE / "fresh_v01" / case_id
        files.verify_manifest(folder)
        contract = read(folder / "contract.json")
        files.verify(contract["input_bindings"])
        if read(folder / "trace.json") != read(REVIEW / f"{case_id}_repaired.json")["trace"]:
            raise ValueError("Fresh full trace differs from offline prediction")
        if (folder / "request.json").read_bytes() != (REVIEW / f"{case_id}_native_unsent.json").read_bytes():
            raise ValueError("Fresh native body differs")
        if (contract["transaction_read_only"], contract["transaction_end"], contract["model_calls"], contract["oauth_calls"],
                contract["new_slots"], contract["network_denials"], contract["gold_read_denials"],
                contract["source_registry_diagnostics"]) != ("on", "rollback", 0, 0, 0, [], [], []):
            raise ValueError("Fresh preparation exceeded offline read-only scope")
        fresh.append({"case_id": case_id, "full_trace_and_native_bytes_identical": True,
                      "request_bytes": contract["request_bytes"], "request_sha256": contract["request_sha256"]})
        original = ROOT / f"output/reference_quote_live_20261105/{case_id}/live"
        files.verify_manifest(original)
        if read(original / "api_response.json")["http_status"] != 502:
            raise ValueError("Historical live failure unexpectedly changed")
        old_live[case_id] = {name: files.sha((original / name).read_bytes())
                             for name in ("response.bin", "api_response.json", "result.json", "manifest.json")}
    http = [synthetic_http(case_id, output) for case_id in ("Q01", "Q05")]
    files.verify_manifest(INTAKE)
    reference = read(INTAKE / "report.json")
    corpus = read(CORPUS_BASE / "Q01/corpus.json")
    page_count, span_count, note_retention = 0, 0, []
    for case in reference["cases"]:
        article = next(a for a in report["articles"].values() if Path(a["original_pdf_path"]).resolve()
                       == Path(case["source_pdf_path_verbatim"]).resolve())
        selected = evaluated_evidence(read(REVIEW / f"{case['id']}_repaired.json")["trace"], corpus)
        combined = "\n".join(e["text"] for e in selected if e["article_id"] == article["article_id"])
        with fitz.open(article["original_pdf_path"]) as document:
            for page in (p for p in reference["source_pages"] if p["case_id"] == case["id"]):
                raw = document[page["pdf_page"] - 1].get_text()
                if files.sha(raw.encode()) != page["sha256"]:
                    raise ValueError("Fresh source page changed")
                page_count += 1
                spans = [q["span"] for q in case["quotes"] if q["span"] and q["pdf_page"] == page["pdf_page"]]
                notes = [n for n in reference["source_notes"] if n["case_id"] == case["id"] and n["pdf_page"] == page["pdf_page"]]
                spans += [n["raw_span"] for n in notes]
                for span in spans:
                    if raw[span["start"]:span["end"]] != span["text"]:
                        raise ValueError("Raw source offsets changed")
                    span_count += 1
                note_retention += [{"case_id": case["id"], "page": page["pdf_page"], "origin": n["origin"],
                                    "raw_span": n["raw_span"], "retained": n["raw_span"]["text"] in combined} for n in notes]
    result = {"version": "ascii_quote_selection_verification_v0.1", "fresh_preparations": fresh,
              "synthetic_http_checks": http, "historical_real_http502_hashes_unchanged": old_live,
              "fresh_reference_pages": page_count, "fresh_raw_spans": span_count, "source_note_retention": note_retention,
              "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0}
    report["summary"]["verification"] = {key: value for key, value in result.items() if key != "source_note_retention"}
    html = render(report).replace("Сохранение запрошенного контекста в runtime", "ASCII-ID: точные цитаты подставляет сервер")
    examples = ("<h2>Синтетический HTTP200 — не ответ реальной модели</h2>"
                "<p>Новые запросы модели не отправлялись. Старые HTTP502 неизменны.</p>")
    for case_id in ("Q01", "Q05"):
        examples += detail(case_id + " — SYNTHETIC HTTP /answer", read(output / f"{case_id}_SYNTHETIC_HTTP_response.json"))
    html = html.replace("<h2>TAC: все работы снимка</h2>", examples + "<h2>TAC: все работы снимка</h2>")
    files.write(output / "verification.json", result)
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", check_html(html, article_count=len(report["articles"]), case_count=5))
    files.write(output / "current_bindings.json", files.bindings([Path(__file__),
                ROOT / "scripts/capture_ascii_quote_selection_20261105.py",
                REVIEW / "manifest.json", *[BASE / f"fresh_v01/{cid}/manifest.json" for cid in ("Q01", "Q05")]]))
    files.manifest(output)
    return {key: value for key, value in result.items() if key != "source_note_retention"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = verify(args.output)
    if policy.denied:
        raise ValueError("Unexpected offline network attempt")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
