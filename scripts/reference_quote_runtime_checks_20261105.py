"""Offline service comparison and explicitly synthetic bounded selections."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import benchmark_retrieval_replay_20261105 as engine
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.retrieval_ablation_labels import label_retention
from scripts.review_benchmark_retrieval_repair_20261105 import INTAKE, OLD, check_html, condition_surfaces, presence
from scripts.review_retrieval_ablation import unpack

ROOT = files.ROOT
BASE = ROOT / "output/reference_quote_runtime_20261105"
CORPUS_BASE = ROOT / "output/benchmark_retrieval_repair_20261105/capture_v02"
PREVIOUS = ROOT / "output/requested_context_runtime_20261105"
PROTOCOL = ROOT / "docs/records/reference_quote_runtime_protocol_2026-11-05_v0.2.md"


@contextmanager
def baseline_scope():
    from app.generation import service
    from app.retrieval import search
    with patch.object(search, "_source_reference_search", return_value=(None, None)), \
            patch.object(service, "prepare_reference_quotes", return_value=None):
        yield


@contextmanager
def inventory_scope(corpus: dict[str, Any], articles: dict[str, Any]):
    from app.retrieval import search

    def chunks(_session: Any, query: str, collection: str, filters: Any, article_id: str) -> Any:
        rows = sorted((r for r in corpus.values() if r["article_id"] == article_id), key=lambda r: (r["chunk_index"], r["chunk_id"]))
        article = articles[article_id]
        return [search.SearchResult(**{k: r[k] for k in ("article_id", "chunk_id", "title", "doi", "page_start", "page_end",
                                                        "source_type", "text_layer", "full_text")},
                                    year=article["year"], journal=article["journal"], snippet=search.make_snippet(r["full_text"], query),
                                    score=0.0, retrieval_method="explicit_source_reference") for r in rows if r["full_text"].strip()]

    with patch.object(search, "_source_reference_inventory", return_value=articles), \
            patch.object(search, "_source_reference_chunks", chunks):
        yield


def raw_evidence(trace: dict[str, Any], corpus: dict[str, Any]) -> list[dict[str, Any]]:
    from app.generation.reference_quotes import SOURCE_TYPE, verify_raw_binding
    rows = []
    for item in trace["evidence"]:
        raw = corpus[item["chunk_id"]]
        if item["source_type"] == SOURCE_TYPE:
            verify_raw_binding(item["text"], raw["full_text"], article_id=item["article_id"], chunk_id=item["chunk_id"],
                               citation_id=item["citation_id"])
            # Measure actual quotations entering inference, not the entire parent.
            text = "\n".join(r["raw_span"]["text"] for r in json.loads(item["text"])["records"])
        else:
            if item["text"] != raw["full_text"]:
                raise ValueError("Raw evidence changed")
            text = item["text"]
        rows.append({**item, "text": text})
    return rows


def synthetic_selection(source: dict[str, Any], settings: Any, corpus: Any, articles: Any, output: Path, case_id: str) -> Any:
    from app.generation import service
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider
    from app.generation.lithiation_overview import allowed_claims
    from app.generation.providers import GeneratedClaim, ProviderResult

    calls, answers = [], []

    class SyntheticProvider:
        def generate(self, question: str, evidence: Any, **kwargs: Any) -> Any:
            client = GigaChatAnswerProvider(credentials="offline-placeholder", scope=settings.gigachat_scope,
                model=settings.rag_model, timeout_seconds=settings.rag_timeout_seconds, max_tokens=settings.rag_gigachat_max_tokens)

            def post(url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
                calls.append("simulated_oauth_boundary" if oauth else "unsent_native_boundary")
                if oauth:
                    if url != AUTH_URL:
                        raise ValueError("Wrong fake OAuth endpoint")
                    return b'{"access_token":"offline-placeholder"}'
                if url != CHAT_URL:
                    raise ValueError("Wrong native boundary")
                files.save(output / f"{case_id}_native_unsent.json", body)
                raise files.PreparedBoundary()

            client._post = post
            try:
                client.generate(question, evidence, **kwargs)
            except files.PreparedBoundary:
                pass
            else:
                raise ValueError("Expected explicit native boundary stop")
            allowed = allowed_claims(evidence)
            return ProviderResult(answerable=True, claims=[GeneratedClaim(text, [citation])
                for citation, texts in allowed.items() for text in texts], provider="SYNTHETIC_EXACT_SELECTION", model=None)

    original = service.answer_question

    def observe_answer(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        answers.append(service.answer_response_to_dict(result))
        return result

    with inventory_scope(corpus, articles), patch.object(engine, "NoGeneration", SyntheticProvider), \
            patch.object(service, "answer_question", observe_answer):
        engine.replay(source, settings, replacement=lambda response: response)
    if len(answers) != 1 or answers[0]["status"] != "answered" or len(calls) != 2:
        raise ValueError("Synthetic complete selection did not traverse actual service/native schema")
    files.write(output / f"{case_id}_SYNTHETIC_selection.json", answers[0])
    native = (output / f"{case_id}_native_unsent.json").read_bytes()
    value = json.loads(native)
    if (value["model"], value["max_tokens"]) != (settings.rag_model, 1200):
        raise ValueError("Unsent native settings drift")
    return {"kind": "SYNTHETIC_not_a_model_answer", "calls": calls, "real_model_calls": 0, "real_oauth_calls": 0,
            "request_bytes": len(native), "request_sha256": files.sha(native), "max_output_tokens": 1200}


def run(output: Path) -> dict[str, Any]:
    settings = files.configure()
    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(BASE / "freeze_v01")
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"), Path(__file__), PROTOCOL,
             ROOT / "tests/unit/test_source_reference.py", ROOT / "tests/unit/test_reference_quotes.py"]
    bindings = files.bindings(paths)
    for path in paths:
        target = output / "source_snapshot" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        files.save(target, path.read_bytes())
    corpus, articles = read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")
    bindings.update(files.bindings([CORPUS_BASE / "Q01/corpus.json", CORPUS_BASE / "Q01/articles.json"]))
    selected = {}
    for i in range(1, 6):
        case_id = f"Q{i:02}"
        folder = PREVIOUS / "fresh_v01" / case_id if i in (3, 4) else CORPUS_BASE / case_id
        files.verify_manifest(folder)
        bindings.update(files.bindings([folder / "manifest.json", folder / "boundaries.json"]))
        source = read(folder / "boundaries.json")
        with baseline_scope():
            baseline = engine.replay(source, settings)
        with inventory_scope(corpus, articles):
            repaired = engine.replay(source, settings, replacement=lambda response: response)
        selected[case_id] = {"source": source, "baseline": baseline, "repaired": repaired}
        for arm, result in (("baseline", baseline), ("repaired", repaired)):
            files.write(output / f"{case_id}_{arm}.json", result)
        print(json.dumps({"question_only_selection_complete": case_id}), flush=True)

    # First reference/gold read, after every new prediction/selection is frozen.
    files.verify_manifest(INTAKE)
    gold = read(INTAKE / "report.json")
    bindings.update(files.bindings([INTAKE / "manifest.json", INTAKE / "report.json"]))
    cases = []
    for reference_case in gold["cases"]:
        case_id = reference_case["id"]
        target = next(a for a in articles.values() if Path(a["original_pdf_path"]).resolve()
                      == Path(reference_case["source_pdf_path_verbatim"]).resolve())
        pages = [p["pdf_page"] for p in gold["source_pages"] if p["case_id"] == case_id]
        case = {"id": case_id, "question": reference_case["question"]}
        for arm in ("baseline", "repaired"):
            result = selected[case_id][arm]
            raw = raw_evidence(result["trace"], corpus)
            before = raw_evidence(selected[case_id]["baseline"]["trace"], corpus)
            case[arm] = {"presence": presence(raw, target["article_id"], pages, reference_case["quotes"]), "evidence": raw,
                "adequacy": result["trace"]["metadata"]["evidence_adequacy"], "boundary": result["boundary"],
                "reference_quote_selection": result["trace"]["metadata"].get("reference_quote_selection"),
                "reference_resolution": result["trace"]["retrieval"]["metadata"].get("explicit_source_reference"),
                "condition_surfaces_added": sorted(set(condition_surfaces(raw)) - set(condition_surfaces(before))),
                "condition_surfaces_lost": sorted(set(condition_surfaces(before)) - set(condition_surfaces(raw)))}
        cases.append(case)
    synthetic = {case_id: synthetic_selection(selected[case_id]["source"], settings, corpus, articles, output, case_id)
                 for case_id in ("Q01", "Q05")}
    files.verify_manifest(OLD)
    old_corpus, old_articles, dataset = read(OLD / "corpus.json"), read(OLD / "articles.json"), read(OLD / "cases.json")
    regressions = []
    for index, case in enumerate(dataset["cases"]):
        path = OLD / f"cases/{index:03}_baseline.json"
        bindings.update(files.bindings([path]))
        source = unpack(read(path), old_corpus)
        with baseline_scope():
            baseline = engine.replay(source, settings)
        with inventory_scope(corpus, articles):
            repaired = engine.replay(source, settings, replacement=lambda response: response)
        before = label_retention(case, baseline["trace"]["retrieval"]["results"], old_articles)
        after = label_retention(case, repaired["trace"]["retrieval"]["results"], old_articles)
        changed = baseline["trace"] != repaired["trace"]
        if changed:
            files.write(output / f"regression_{index:03}.json", {"baseline": baseline, "repaired": repaired})
        regressions.append({"id": case["id"], "full_trace_changed": changed,
            "labelled_article_losses": sorted(set(before["matching_article_ids"]) - set(after["matching_article_ids"])),
            "gate_decision_changed": (baseline["trace"]["metadata"]["evidence_adequacy"]["adequate"]
                                      != repaired["trace"]["metadata"]["evidence_adequacy"]["adequate"])})
        if index % 15 == 0:
            print(json.dumps({"old_cases_checked": index + 1}), flush=True)
    original = read(BASE / "freeze_v01/runtime.json")["bindings"]
    drift = {name: {"before": digest, "after": files.sha(Path(name).read_bytes()),
                   "snapshot": str(BASE / "freeze_v01/source_snapshot" / Path(name).relative_to(ROOT))}
             for name, digest in original.items() if files.sha(Path(name).read_bytes()) != digest}
    for article in articles.values():
        pdf = Path(article["original_pdf_path"])
        if files.sha(pdf.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        bindings.update(files.bindings([pdf]))
    files.verify(bindings)
    summary = {"version": "reference_quote_runtime_v0.2", "runtime_drift": drift, "old_baseline_traces_reproduced": 81,
        "offline_service_runs": 164, "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0,
        "synthetic_selections": synthetic, "old_full_trace_changes": [r["id"] for r in regressions if r["full_trace_changed"]],
        "old_labelled_article_losses": [r["id"] for r in regressions if r["labelled_article_losses"]],
        "old_gate_decision_changes": [r["id"] for r in regressions if r["gate_decision_changed"]],
        "arms": {arm: {"pages": sum(len(c[arm]["presence"]["reference_pages_present"]) for c in cases), "page_total": 10,
                       "quotes": sum(c[arm]["presence"]["mapped_quotes_retained"] for c in cases), "quote_total": 12}
                 for arm in ("baseline", "repaired")}, "scientific_accuracy": None,
        "limitations": ["Exposed development cases, not independent scientific evaluation", "Quoted source text, not free synthesis",
                        "No actual model output or provider behavior measured", "Unit interpretation/ownership not established",
                        "No browser/full suite/concurrency check"]}
    report = {"summary": summary, "bindings": bindings, "cases": cases, "regressions": regressions, "articles": articles}
    html = render(report)
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
    result = run(args.output)
    if policy.denied:
        raise ValueError("Unexpected network access")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
