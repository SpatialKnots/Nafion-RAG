"""Question-only frozen-channel service comparisons, then post-hoc source review."""

from __future__ import annotations

import argparse
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import fitz

from app.generation import context_completion as context
from app.generation import service
from app.retrieval.search import SearchResult, make_snippet
from scripts import benchmark_retrieval_replay_20261105 as engine
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_answer_fidelity_20261105 import native
from scripts.check_requested_context_runtime_20261105 import render
from scripts.check_structured_answers_20261105 import raw_evidence
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE, INTAKE, OLD, inventory_scope
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, presence
from scripts.review_retrieval_ablation import unpack

BASE = files.ROOT / "output/condition_context_completion_20261106"
PREVIOUS = files.ROOT / "output/structured_answers_20261105/review_v02"
PROTOCOL = files.ROOT / "docs/records/condition_context_completion_protocol_2026-11-06_v0.1.md"


@contextmanager
def completion_inventory(corpus, articles):
    """Offline seam only. SQL scope is separately tested and fresh DB is checked."""
    calls = []

    def load(_session, query, collection, filters, anchor):
        if filters.as_metadata():
            raise ValueError("Frozen inventory has no membership/filtered-scope oracle")
        rows = sorted((r for r in corpus.values() if r["article_id"] == anchor.article_id
            and r["text_layer"] == anchor.text_layer and r["source_type"] == anchor.source_type
            and r["page_start"] >= max(1, anchor.page_start - context.PAGE_LOOKBACK)
            and r["page_end"] <= anchor.page_start),
            key=lambda r: (r["page_start"], r["page_end"], r["chunk_index"], r["chunk_id"]))[:context.MAX_ROWS + 1]
        calls.append({"collection": collection, "anchor_chunk_id": anchor.chunk_id,
                      "candidate_chunk_ids": [r["chunk_id"] for r in rows]})
        return [SearchResult(**{k: r[k] for k in ("article_id", "chunk_id", "title", "doi", "page_start", "page_end",
            "source_type", "text_layer", "full_text")}, snippet=make_snippet(r["full_text"], query),
            score=0.0, retrieval_method="condition_context", year=articles[r["article_id"]]["year"],
            journal=articles[r["article_id"]]["journal"]) for r in rows]

    with patch.object(context, "load_context_rows", load):
        yield calls


def replay(source, settings, corpus, articles, *, baseline=False):
    with inventory_scope(corpus, articles), completion_inventory(corpus, articles) as calls:
        if baseline:
            with patch.object(service, "complete_context", side_effect=lambda s, q, c, f, rows: (rows, None)):
                value = engine.replay(source, settings, replacement=lambda r: r)
        else:
            value = engine.replay(source, settings, replacement=lambda r: r)
    return value, calls


def validate_added(trace, corpus, native_path):
    meta = trace["metadata"].get("condition_context_completion")
    if meta is None or not meta["added_chunk_ids"]:
        return 0
    message = " ".join(m["content"] for m in read(native_path)["messages"])
    count = 0
    for support in meta["supports"]:
        raw = corpus[support["chunk_id"]]["full_text"]
        if raw[support["start"]:support["end"]] != support["text"] or files.sha(raw.encode()) != support["raw_chunk_sha256"]:
            raise ValueError("Methods support binding differs")
        evidence = next(e for e in trace["evidence"] if e["chunk_id"] == support["chunk_id"])
        if evidence["text"] != raw or re.sub(r"\s+", " ", raw).strip() not in message:
            raise ValueError("Full raw context did not enter actual native prompt")
        count += 1
    return count


def run(output):
    settings = files.configure()
    output.mkdir(parents=True, exist_ok=False)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL,
             files.ROOT / "docs/records/condition_context_completion_amendment_2026-11-06_v0.2.md",
             files.ROOT / "tests/unit/test_context_completion.py", files.ROOT / "tests/unit/test_requested_context_service.py"]
    bindings = files.bindings(paths)
    files.verify_manifest(BASE / "freeze_v02")
    corpus, articles = read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")
    bindings.update(files.bindings([CORPUS_BASE / "Q01/corpus.json", CORPUS_BASE / "Q01/articles.json"]))
    predictions, natives, loader_calls = {}, {}, []
    for number in range(1, 6):
        cid = f"Q{number:02}"
        path = CORPUS_BASE / cid / "boundaries.json"
        bindings.update(files.bindings([path, PREVIOUS / f"{cid}_repaired.json"]))
        before, before_calls = replay(read(path), settings, corpus, articles, baseline=True)
        if before != read(PREVIOUS / f"{cid}_repaired.json") or before_calls:
            raise ValueError("Pre-change full trace/boundaries not reproduced: " + cid)
        after, calls = replay(read(path), settings, corpus, articles)
        if before["trace"]["retrieval"] != after["trace"]["retrieval"] or before["channel_calls"] != after["channel_calls"]:
            raise ValueError("Original retrieval or queries changed")
        if cid != "Q03" and before != after:
            raise ValueError("Out-of-scope service changed: " + cid)
        for arm, value in (("baseline", before), ("repaired", after)):
            files.write(output / f"{cid}_{arm}.json", value)
        predictions[cid] = {"baseline": before, "repaired": after}
        loader_calls.extend(calls)
        natives[cid] = native(cid, after["trace"], settings, output)
        if cid != "Q03" and (output / f"{cid}_native_unsent.json").read_bytes() != (PREVIOUS / f"{cid}_native_unsent.json").read_bytes():
            raise ValueError("Out-of-scope native bytes changed: " + cid)
    supports = validate_added(predictions["Q03"]["repaired"]["trace"], corpus, output / "Q03_native_unsent.json")
    if supports != 1 or len(loader_calls) != 1:
        raise ValueError("Expected exactly one new raw methods support and bounded loader invocation")
    old_corpus, old_articles = read(OLD / "corpus.json"), read(OLD / "articles.json")
    dataset, regressions = read(OLD / "cases.json"), []
    bindings.update(files.bindings([OLD / "corpus.json", OLD / "articles.json", OLD / "cases.json"]))
    for index, case in enumerate(dataset["cases"]):
        path = OLD / f"cases/{index:03}_baseline.json"
        bindings.update(files.bindings([path]))
        source = unpack(read(path), old_corpus)
        before, _ = replay(source, settings, old_corpus, old_articles, baseline=True)
        after, calls = replay(source, settings, old_corpus, old_articles)
        identical = before == after
        if not identical or calls:
            files.write(output / f"old_{index:03}_changed.json", {"baseline": before, "repaired": after, "calls": calls})
            raise ValueError("Previously exposed regression case changed: " + case["id"])
        regressions.append({"id": case["id"], "full_service_identical": identical, "loader_calls": len(calls)})
        if index % 20 == 0:
            print(json.dumps({"old_cases_checked": index + 1}), flush=True)

    # Reference files are read only after all question-only inference inputs close.
    files.verify_manifest(INTAKE)
    gold, cases = read(INTAKE / "report.json"), []
    bindings.update(files.bindings([INTAKE / "manifest.json", INTAKE / "report.json"]))
    for ref in gold["cases"]:
        cid = ref["id"]
        target = next(a for a in articles.values() if Path(a["original_pdf_path"]).resolve()
                      == Path(ref["source_pdf_path_verbatim"]).resolve())
        pages = [p["pdf_page"] for p in gold["source_pages"] if p["case_id"] == cid]
        case = {"id": cid, "question": ref["question"]}
        for arm, value in predictions[cid].items():
            evidence = raw_evidence(value["trace"], corpus)
            case[arm] = {"presence": presence(evidence, target["article_id"], pages, ref["quotes"]),
                "evidence": evidence, "boundary": value["boundary"],
                "context_completion": value["trace"]["metadata"].get("condition_context_completion")}
        cases.append(case)
    fresh_pages, spans = 0, 0
    for page in gold["source_pages"]:
        ref = next(c for c in gold["cases"] if c["id"] == page["case_id"])
        with fitz.open(ref["source_pdf_path_verbatim"]) as pdf:
            raw = pdf[page["pdf_page"] - 1].get_text()
        if files.sha(raw.encode()) != page["sha256"]:
            raise ValueError("Fresh reference page changed")
        fresh_pages += 1
        selected = [q["span"] for q in ref["quotes"] if q["span"] and q["pdf_page"] == page["pdf_page"]]
        selected += [n["raw_span"] for n in gold["source_notes"] if n["case_id"] == ref["id"] and n["pdf_page"] == page["pdf_page"]]
        for span in selected:
            if raw[span["start"]:span["end"]] != span["text"]:
                raise ValueError("Fresh reference span changed")
            spans += 1
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        bindings.update(files.bindings([path]))
    summary = {"version": context.VERSION, "exact_prechange_replays": 5, "actual_service_runs": 162,
        "old_full_service_unchanged": len(regressions), "bounded_loader_calls_five_cases": loader_calls,
        "raw_supports_in_actual_native_prompt": supports, "native_unsent": natives,
        "fresh_reference_pages": fresh_pages, "fresh_reference_spans": spans,
        "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0, "scientific_accuracy": None,
        "limitations": ["Finite RU methods grammar, one Li-Nafion table family", "Context is not verified value ownership",
            "No live model answer or independent scientific evaluation", "No browser/PDF visual/full-suite/concurrency validation"]}
    report = {"summary": summary, "bindings": bindings, "articles": articles, "cases": cases, "regressions": regressions}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Добор контекста условий v0.1")
    qa = check_html(document, article_count=len(articles), case_count=5)
    files.verify(bindings)
    files.write(output / "report.json", report)
    files.save(output / "review.html", document.encode())
    files.write(output / "qa.json", qa)
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
        raise ValueError("Unexpected external network attempt")
    print(json.dumps({**result, "external_network_denials": policy.denied}, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
