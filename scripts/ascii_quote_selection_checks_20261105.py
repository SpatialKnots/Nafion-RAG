"""Offline ASCII-ID service/native checks; synthetic responses, no live calls."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import benchmark_retrieval_replay_20261105 as engine
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE, INTAKE, OLD, inventory_scope
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, presence
from scripts.review_retrieval_ablation import unpack

ROOT = files.ROOT
BASE = ROOT / "output/ascii_quote_selection_20261105"
PREVIOUS = ROOT / "output/reference_quote_runtime_20261105"
PROTOCOL = ROOT / "docs/records/ascii_quote_selection_protocol_2026-11-05_v0.1.md"


def old_prepare():
    path = BASE / "freeze_v01/source_snapshot/app/generation/reference_quotes.py"
    spec = importlib.util.spec_from_file_location("ascii_stage_historical_v2", path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load preserved v0.2 baseline")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module.prepare


@contextmanager
def baseline_scope():
    from app.generation import service
    with patch.object(service, "prepare_reference_quotes", old_prepare()):
        yield


def evaluated_evidence(trace: dict[str, Any], corpus: dict[str, Any]) -> list[dict[str, Any]]:
    # Forensic reader only: no v0.2 acceptance is added to production.
    rows = []
    for item in trace["evidence"]:
        parent = corpus[item["chunk_id"]]
        text = item["text"]
        if item["source_type"] == "reference_quote_derived":
            payload = json.loads(text)
            if payload["version"] not in {"explicit_reference_quotes_v0.2", "explicit_reference_quotes_v0.3"}:
                raise ValueError("Unexpected forensic contract version")
            excerpts = []
            for record in payload["records"]:
                span = record["raw_span"]
                if (record["raw_chunk_sha256"] != hashlib.sha256(parent["full_text"].encode()).hexdigest()
                        or parent["full_text"][span["start"]:span["end"]] != span["text"]
                        or record["citation_id"] != item["citation_id"] or record["chunk_id"] != item["chunk_id"]):
                    raise ValueError("Bound quotation source differs")
                excerpts.append(span["text"])
            text = "\n".join(excerpts)
        elif text != parent["full_text"]:
            raise ValueError("Raw source changed")
        rows.append({**item, "text": text})
    return rows


def synthetic_selection(source: dict[str, Any], settings: Any, corpus: Any, articles: Any, output: Path, case_id: str) -> Any:
    from app.generation import service
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider
    from app.generation.reference_quotes import selection_records

    calls, answers, inputs = [], [], []

    class SyntheticIDProvider:
        def generate(self, question: str, evidence: Any, **kwargs: Any) -> Any:
            inputs.extend(evidence)
            client = GigaChatAnswerProvider(credentials="offline-placeholder", scope=settings.gigachat_scope,
                model=settings.rag_model, timeout_seconds=settings.rag_timeout_seconds, max_tokens=settings.rag_gigachat_max_tokens)

            def post(url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
                calls.append("simulated_oauth_boundary" if oauth else "simulated_id_model_boundary")
                if oauth:
                    if url != AUTH_URL:
                        raise ValueError("Wrong fake OAuth endpoint")
                    return b'{"access_token":"offline-placeholder"}'
                if url != CHAT_URL:
                    raise ValueError("Wrong fake native endpoint")
                files.save(output / f"{case_id}_native_unsent.json", body)
                records = selection_records(evidence)
                content = {"answerable": True, "claims": [{"text": key, "citation_ids": [record["citation_id"]]}
                                                           for key, record in reversed(list(records.items()))]}
                envelope = {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
                             "content": json.dumps(content)}}]}
                files.write(output / f"{case_id}_SYNTHETIC_ID_response.json", envelope)
                return files.encode(envelope)

            client._post = post
            result = client.generate(question, evidence, **kwargs)
            return replace(result, provider="SYNTHETIC_ASCII_ID_SELECTION", model=None)

    original = service.answer_question

    def observe(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        answers.append(service.answer_response_to_dict(result))
        return result

    with inventory_scope(corpus, articles), patch.object(engine, "NoGeneration", SyntheticIDProvider), \
            patch.object(service, "answer_question", observe):
        replayed = engine.replay(source, settings, replacement=lambda response: response)
    if len(answers) != 1 or answers[0]["status"] != "answered" or len(calls) != 2:
        raise ValueError("Synthetic ID selection failed to traverse actual provider/service")
    files.write(output / f"{case_id}_SYNTHETIC_server_answer.json", answers[0])
    records = selection_records(inputs)
    if [c["text"] for c in answers[0]["claims"]] != [r["allowed_claim"] for r in records.values()]:
        raise ValueError("Server rendered modified or wrongly ordered quotation")
    old = read(PREVIOUS / f"review_v02/{case_id}_SYNTHETIC_selection.json")
    if answers[0]["answer"] != old["answer"] or answers[0]["claims"] != old["claims"]:
        raise ValueError("Public quotations/citations differ from the prior valid source strings")
    raw = (output / f"{case_id}_native_unsent.json").read_bytes()
    native = json.loads(raw)
    enum = native["response_format"]["schema"]["$defs"]["_Claim"]["properties"]["text"]["enum"]
    if enum != list(records) or not all(key.isascii() for key in enum):
        raise ValueError("Native enum did not contain the canonical ASCII IDs")
    return {"kind": "SYNTHETIC_NOT_A_REAL_MODEL_ANSWER", "real_model_calls": 0, "real_oauth_calls": 0,
            "simulated_boundaries": calls, "request_bytes": len(raw), "request_sha256": files.sha(raw),
            "selection_ids": enum, "public_answer_identical_to_prior_source_strings": True,
            "trace": replayed["trace"]}


def run(output: Path) -> dict[str, Any]:
    settings = files.configure()
    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(BASE / "freeze_v01")
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"), Path(__file__), PROTOCOL,
             ROOT / "tests/unit/test_ascii_quote_selection.py", ROOT / "tests/unit/test_reference_quotes.py",
             ROOT / "tests/unit/test_reference_quote_service.py"]
    bindings = files.bindings(paths)
    for path in paths:
        target = output / "source_snapshot" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        files.save(target, path.read_bytes())
    corpus, articles = read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")
    predictions = {}
    for number in range(1, 6):
        case_id = f"Q{number:02}"
        source = read(CORPUS_BASE / case_id / "boundaries.json")
        with inventory_scope(corpus, articles), baseline_scope():
            before = engine.replay(source, settings, replacement=lambda response: response)
        expected = read(PREVIOUS / f"review_v02/{case_id}_repaired.json")["trace"]
        if before["trace"] != expected:
            raise ValueError("Preserved v0.2 baseline differs")
        with inventory_scope(corpus, articles):
            after = engine.replay(source, settings, replacement=lambda response: response)
        predictions[case_id] = {"source": source, "baseline": before, "repaired": after}
        for arm, value in (("baseline", before), ("repaired", after)):
            files.write(output / f"{case_id}_{arm}.json", value)
    synthetic = {case_id: synthetic_selection(predictions[case_id]["source"], settings, corpus, articles, output, case_id)
                 for case_id in ("Q01", "Q05")}
    files.verify_manifest(INTAKE)
    gold = read(INTAKE / "report.json")
    cases = []
    for reference in gold["cases"]:
        target = next(a for a in articles.values() if Path(a["original_pdf_path"]).resolve()
                      == Path(reference["source_pdf_path_verbatim"]).resolve())
        pages = [p["pdf_page"] for p in gold["source_pages"] if p["case_id"] == reference["id"]]
        case = {"id": reference["id"], "question": reference["question"]}
        for arm in ("baseline", "repaired"):
            value = predictions[reference["id"]][arm]
            evidence = evaluated_evidence(value["trace"], corpus)
            case[arm] = {"presence": presence(evidence, target["article_id"], pages, reference["quotes"]),
                         "evidence": evidence, "adequacy": value["trace"]["metadata"]["evidence_adequacy"],
                         "boundary": value["boundary"]}
        cases.append(case)
    old_corpus, dataset = read(OLD / "corpus.json"), read(OLD / "cases.json")
    regressions = []
    for index, case in enumerate(dataset["cases"]):
        source = unpack(read(OLD / f"cases/{index:03}_baseline.json"), old_corpus)
        before = engine.replay(source, settings)
        after = engine.replay(source, settings, replacement=lambda response: response)
        if before["trace"] != after["trace"]:
            raise ValueError("Out-of-scope legacy full trace changed: " + case["id"])
        regressions.append({"id": case["id"], "full_trace_identical": True})
        if index % 20 == 0:
            print(json.dumps({"old_cases_verified": index + 1}), flush=True)
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        bindings.update(files.bindings([path]))
    bindings.update(files.bindings([PREVIOUS / "review_v02/manifest.json", INTAKE / "manifest.json", OLD / "manifest.json",
                                   CORPUS_BASE / "Q01/corpus.json", CORPUS_BASE / "Q01/articles.json"]))
    files.verify(bindings)
    summary = {"version": "ascii_quote_selection_v0.1", "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0,
        "synthetic_selections": {key: {k: v for k, v in value.items() if k != "trace"} for key, value in synthetic.items()},
        "exact_previous_baselines": 81, "offline_service_runs": 164, "old_full_trace_changes": 0,
        "public_quote_text_and_citations_changed": False, "thresholds_changed": False, "scientific_accuracy": None,
        "limitations": ["No actual model response for the new ID protocol", "Exposed development cases and finite source parsers",
                        "Old real HTTP502 outputs unchanged, never repaired", "No full suite/browser/concurrency check"]}
    report = {"summary": summary, "bindings": bindings, "cases": cases, "articles": articles, "regressions": regressions}
    html = render(report).replace("Сохранение запрошенного контекста в runtime", "ASCII-ID и серверная подстановка цитат")
    marker = "<h2>TAC: все работы снимка</h2>"
    from scripts.review_benchmark_retrieval_repair_20261105 import detail
    examples = "<h2>Только синтетические проверки</h2><p>Новых реальных ответов модели нет. Старые HTTP502 не исправлялись.</p>"
    for case_id in ("Q01", "Q05"):
        examples += detail(case_id + " — SYNTHETIC: серверная подстановка", read(output / f"{case_id}_SYNTHETIC_server_answer.json"))
    html = html.replace(marker, examples + marker)
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", check_html(html, article_count=len(articles), case_count=5))
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    value = run(args.output)
    if policy.denied:
        raise ValueError("Unexpected external network attempt")
    print(json.dumps(value, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
