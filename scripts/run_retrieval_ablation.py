"""Capture four offline retrieval arms at fixed per-query production limits."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.retrieval_ablation import (  # noqa: E402
    ARMS,
    VERSION,
    candidate_bundle,
    label_retention,
    normalized_search_statement,
)
from scripts.run_swelling_retrieval_audit import CaptureComplete, NoGeneration  # noqa: E402

RECIPE = ROOT / "docs/records/retrieval_ablation_cases_v0.1.json"
PROTOCOL = ROOT / "docs/records/retrieval_ablation_protocol_v0.1.md"
PRIOR = ROOT / "output/kim_retrieval_audit_20261031"


def load_cases(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    import yaml

    request = json.loads((ROOT / recipe["morphology_original_request"]).read_bytes())
    cases = [{"id": "morphology_original", "query": request["question"], "origin": "exposed_user_reference_case",
              "evaluate_reference_windows": True}]
    cases.extend({**row, "origin": "assistant_constructed_development_paraphrase", "evaluate_reference_windows": True}
                 for row in recipe["morphology_development_paraphrases"])
    users = json.loads((ROOT / recipe["user_questions_file"]).read_bytes())
    cases.extend({**row, "id": "user::" + row["id"], "query": row["question"], "origin": "exposed_user_question_without_gold"}
                 for row in users["cases"])
    for name in recipe["existing_fixture_files"]:
        fixtures = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
        cases.extend({**row, "id": Path(name).stem + "::" + row["id"], "origin": "existing_exposed_fixture",
                      "fixture_file": name} for row in fixtures)
    if len({row["id"] for row in cases}) != len(cases):
        raise ValueError("Case IDs must be unique")
    return cases


def capture(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    from sqlalchemy import select, text

    from app.db.models import Article, Chunk, Collection
    from app.db.session import SessionLocal
    from app.documents.service import resolve_article_pdf
    from app.generation import service
    from app.retrieval import search
    from app.retrieval.cross_lingual import build_query_bundle

    files.verify_manifest(PRIOR / "capture_v02")
    files.verify_manifest(PRIOR / "expanded_v01")
    prior = json.loads((PRIOR / "capture_v02/capture.json").read_bytes())
    expanded = json.loads((PRIOR / "expanded_v01/expanded.json").read_bytes())
    files.verify(expanded["bindings"])
    recipe = json.loads(RECIPE.read_bytes())
    if recipe["new_live_authorization"]:
        raise ValueError("Offline protocol only")
    cases = load_cases(recipe)
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    files.write(output / "cases.json", {"recipe": recipe, "cases": cases})
    source_paths = [Path(__file__), ROOT / "scripts/retrieval_ablation.py", ROOT / "tests/unit/test_retrieval_ablation.py",
                    RECIPE, PROTOCOL, output / "cases.json", PRIOR / "expanded_v01/expanded.json",
                    ROOT / "output/retrieval_ablation_20261031/capture_v01/manifest.json",
                    *[ROOT / name for name in recipe["existing_fixture_files"]], ROOT / recipe["user_questions_file"]]
    bindings = {**expanded["bindings"], **files.bindings(source_paths)}
    sem_original = search.semantic_search
    exact_original = search.exact_search
    semantic_cache: dict[tuple[Any, ...], Any] = {}
    exact_cache: dict[tuple[Any, ...], Any] = {}
    semantic_actual_calls = 0
    semantic_cache_hits = 0
    exact_actual_calls = 0
    exact_cache_hits = 0

    def cached_exact(*args: Any, **kwargs: Any) -> Any:
        nonlocal exact_actual_calls, exact_cache_hits
        key = (search._search_statement is normalized_search_statement, args[1], args[2], args[3],
               repr(kwargs.get("filters")))
        if key not in exact_cache:
            exact_actual_calls += 1
            exact_cache[key] = exact_original(*args, **kwargs)
        else:
            exact_cache_hits += 1
        return copy.deepcopy(exact_cache[key])

    def cached_semantic(*args: Any, **kwargs: Any) -> Any:
        nonlocal semantic_actual_calls, semantic_cache_hits
        key = (args[1], args[2], args[3], repr(kwargs.get("filters")))
        if key not in semantic_cache:
            semantic_actual_calls += 1
            semantic_cache[key] = sem_original(*args, **kwargs)
        else:
            semantic_cache_hits += 1
        return copy.deepcopy(semantic_cache[key])

    outcomes = []
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '120s'"))
        readonly = session.execute(text("SHOW transaction_read_only")).scalar_one()
        if readonly != "on":
            raise ValueError("Read-only transaction required")
        db_rows = session.execute(select(Chunk, Article).join(Article).join(Collection).where(
            Collection.name == recipe["collection"]).order_by(Chunk.id)).all()
        corpus = {str(chunk.id): {"article_id": str(chunk.article_id), "chunk_id": str(chunk.id),
            "chunk_index": chunk.chunk_index, "page_start": chunk.page_start, "page_end": chunk.page_end,
            "source_type": chunk.source_type, "text_layer": chunk.text_layer, "full_text": chunk.text,
            "title": article.title, "doi": article.doi} for chunk, article in db_rows}
        prior_corpus = {row["chunk_id"]: row for row in expanded["expanded_channels"]["semantic"]}
        if set(corpus) != set(prior_corpus) or any(corpus[key]["full_text"] != prior_corpus[key]["full_text"] for key in corpus):
            raise ValueError("Corpus differs from earlier all-candidate snapshot")
        articles = {}
        for article_id in sorted({row["article_id"] for row in corpus.values()}):
            article = session.get(Article, UUID(article_id))
            if article is None:
                raise ValueError("Missing article")
            pdf = resolve_article_pdf(article, settings, "original").path.resolve()
            if files.sha(pdf.read_bytes()) != article.checksum_sha256:
                raise ValueError("Original PDF checksum differs")
            bindings.update(files.bindings([pdf]))
            articles[article_id] = {"article_id": article_id, "title": article.title, "authors": article.authors,
                "journal": article.journal, "year": article.year, "abstract": article.abstract,
                "conclusions": None, "terms": None, "original_pdf_path": str(pdf),
                "original_pdf_sha256": article.checksum_sha256, "metadata_basis": "fresh read-only DB inventory; not expert verified",
                "uncollected_fields": ["conclusions", "terms"]}
        files.write(output / "corpus.json", corpus)
        files.write(output / "articles.json", articles)
        for index, case in enumerate(cases):
            question = case["query"]
            baseline_bundle = build_query_bundle(question)
            variant_k = search._cross_lingual_variant_top_k(baseline_bundle, top_k=recipe["top_k"], settings=settings)
            feature_k = search._cross_lingual_rerank_window_size(baseline_bundle, top_k=recipe["top_k"], candidate_window=variant_k)
            for arm in ARMS:
                started = time.monotonic()
                stages: list[dict[str, Any]] = []
                counters: dict[str, int] = {}
                active: list[str] = []
                traced: dict[str, Any] = {}

                def pack(rows: Any) -> list[dict[str, Any]]:
                    packed = []
                    for item in rows:
                        row = asdict(item)
                        if "full_text" in row:
                            raw = row.pop("full_text")
                            if raw != corpus[row["chunk_id"]]["full_text"]:
                                raise ValueError("Candidate changed raw source text")
                            row["full_text_sha256"] = files.sha(raw.encode())
                        packed.append(row)
                    return packed

                def instrument(name: str, counters: dict[str, int] = counters, active: list[str] = active,
                               stages: list[dict[str, Any]] = stages, pack_rows: Any = pack) -> Any:
                    original = getattr(search, name)

                    def wrapped(*args: Any, **kwargs: Any) -> Any:
                        counters[name] = counters.get(name, 0) + 1
                        label = name + ":" + str(counters[name])
                        parent = active[-1] if active else None
                        channel = name in {"exact_search", "semantic_search", "hybrid_search"}
                        extra = {"query": args[1], "requested_top_k": args[3]} if channel else {}
                        if not channel:
                            stages.append({"name": label + ":input", "parent": parent, "results": pack_rows(args[0])})
                        active.append(label)
                        try:
                            result = original(*args, **kwargs)
                        finally:
                            active.pop()
                        if hasattr(result, "results"):
                            rows, metadata = result.results, result.metadata
                        elif isinstance(result, tuple):
                            rows, metadata = result
                        else:
                            rows, metadata = result, None
                        stages.append({"name": label + ":output", "parent": parent, "results": pack_rows(rows),
                                       "metadata": metadata, **extra})
                        return result
                    return wrapped

                def observe(retrieval: Any, evidence: Any, metadata: Any,
                            traced: dict[str, Any] = traced, stages: list[dict[str, Any]] = stages) -> None:
                    traced.update(retrieval=asdict(retrieval), evidence=[asdict(item) for item in evidence], metadata=metadata)
                    stages.append({"name": "retrieval_top_k", "results": pack(retrieval.results)})
                    stages.append({"name": "generation_evidence", "results": [asdict(item) for item in evidence]})

                with ExitStack() as stack:
                    stack.enter_context(patch.object(search, "semantic_search", cached_semantic))
                    stack.enter_context(patch.object(search, "exact_search", cached_exact))
                    if arm in {"ligatures", "combined"}:
                        stack.enter_context(patch.object(search, "_search_statement", normalized_search_statement))
                    if arm in {"expansion", "combined"}:
                        stack.enter_context(patch.object(search, "build_query_bundle", candidate_bundle))
                    stack.enter_context(patch.object(search, "_cross_lingual_variant_top_k", return_value=variant_k))
                    stack.enter_context(patch.object(search, "_cross_lingual_rerank_window_size", return_value=feature_k))
                    stack.enter_context(patch.object(service, "build_answer_provider", side_effect=AssertionError("Provider forbidden")))
                    for name in ("exact_search", "semantic_search", "hybrid_search", "_rerank_cross_lingual_results",
                                 "_legacy_rerank_cross_lingual_results", "_diversify_cross_lingual_results",
                                 "feature_rerank_cross_lingual_results", "_ensure_cross_language_presence"):
                        stack.enter_context(patch.object(search, name, instrument(name)))
                    stopped = False
                    try:
                        response = service.answer_question(session, settings, question, collection=recipe["collection"],
                            top_k=recipe["top_k"], method="hybrid_cross_lingual", provider=NoGeneration(), trace_observer=observe)
                        boundary_status = response.status
                    except CaptureComplete:
                        stopped = True
                        boundary_status = "stopped_before_generation"
                if not traced:
                    raise ValueError("Missing evidence trace")
                if case["id"] == "morphology_original" and arm == "baseline" and traced != prior["trace"]:
                    raise ValueError("Baseline differs from frozen morphology trace")
                value = {"case_id": case["id"], "arm": arm, "question": question,
                    "request": {"question": question, "collection": recipe["collection"], "top_k": recipe["top_k"],
                                "method": "hybrid_cross_lingual", "answer_style": "claims", "answer_language": "auto"},
                    "limits": {"variant_top_k": variant_k, "feature_window": feature_k, "final_top_k": recipe["top_k"]},
                    "stages": stages, "trace": traced, "provider_boundary_reached": stopped, "boundary_status": boundary_status,
                    "article_label_retention": label_retention(case, traced["retrieval"]["results"], articles),
                    "channel_calls": {name: counters.get(name, 0) for name in ("exact_search", "semantic_search", "hybrid_search")},
                    "elapsed_seconds": time.monotonic() - started}
                filename = f"cases/{index:03d}_{arm}.json"
                files.write(output / filename, value)
                outcomes.append({"case_id": case["id"], "arm": arm, "artifact": filename,
                    "article_label_retention": value["article_label_retention"], "channel_calls": value["channel_calls"],
                    "boundary_status": boundary_status, "adequate": traced["metadata"]["evidence_adequacy"]["adequate"]})
            print(json.dumps({"completed_case": index + 1, "total_cases": len(cases), "id": case["id"]}), flush=True)
        session.rollback()
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    files.verify(bindings)
    summary = {"version": VERSION, "case_count": len(cases), "unique_queries": len({row["query"] for row in cases}),
        "arm_runs": len(outcomes), "transaction_read_only": readonly, "transaction_end": "rollback",
        "local_semantic_actual_calls": semantic_actual_calls, "local_semantic_cache_hits": semantic_cache_hits,
        "exact_actual_calls": exact_actual_calls, "exact_cache_hits": exact_cache_hits,
        "timing_scope": "ordered diagnostic timings; semantic cache/cold-start prevent unbiased latency comparison",
        "historical_morphology_baseline_trace_identical": True, "corpus_chunks": len(corpus), "tac_works": len(articles),
        "model_calls": 0, "oauth_calls": 0, "slot_reservations": 0, "network_denials": policy.denied,
        "runtime_changes": False, "scientific_acceptance": "not_established", "plan_completion_percent": 75}
    files.write(output / "capture.json", {"summary": summary, "bindings": bindings, "outcomes": outcomes})
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(capture(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
