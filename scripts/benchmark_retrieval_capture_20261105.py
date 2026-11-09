"""Question-only, read-only retrieval boundaries. No generation or send mode."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

from scripts import gigachat_answer_smoke as files
from scripts.prepare_benchmark_inputs_20261103 import GoldReadGuard, load_cases
from scripts.run_swelling_retrieval_audit import CaptureComplete, NoGeneration

ROOT = files.ROOT
PROTOCOL = ROOT / "docs/records/benchmark_retrieval_repair_protocol_2026-11-05_v0.1.md"
BASE = ROOT / "output/benchmark_retrieval_repair_20261105"
FUNCTIONS = (
    "exact_search", "semantic_search", "hybrid_search", "_rerank_cross_lingual_results",
    "_legacy_rerank_cross_lingual_results", "_diversify_cross_lingual_results",
    "feature_rerank_cross_lingual_results", "_ensure_cross_language_presence",
)


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def capture(case_id: str, output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    case = next(c for c in load_cases() if c["id"] == case_id)
    guard = GoldReadGuard()
    guard.allowed.add(PROTOCOL.resolve())
    sys.addaudithook(guard)
    settings = files.configure()
    from sqlalchemy import select, text

    from app.db.models import Article, Chunk, Collection
    from app.db.session import SessionLocal
    from app.documents.service import resolve_article_pdf
    from app.generation import service
    from app.retrieval import search

    historical_folder = ROOT / "output/user_benchmark_live_20261104" / case_id / "live"
    historical = read(historical_folder / "trace.json")
    api = read(ROOT / "output/user_benchmark_live_20261104" / case_id / "authorized_inputs/api_request.json")
    if api["question"] != case["question"]:
        raise ValueError("Question differs from frozen packet")
    output.mkdir(parents=True, exist_ok=False)
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"),
             Path(__file__), PROTOCOL, historical_folder / "trace.json",
             ROOT / "docs/records/user_benchmark_questions_2026-11-03_v0.1.json"]
    bindings = files.bindings(paths)
    stages: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    active: list[str] = []

    def instrument(name: str) -> Any:
        original = getattr(search, name)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            counters[name] = counters.get(name, 0) + 1
            label = f"{name}:{counters[name]}"
            channel = name in {"exact_search", "semantic_search", "hybrid_search"}
            extra = ({"query": args[1], "top_k": args[3]} if channel else {})
            parent = active[-1] if active else None
            if not channel:
                stages.append({"name": label + ":input", "parent": parent,
                               "results": [asdict(r) for r in args[0]]})
            active.append(label)
            try:
                result = original(*args, **kwargs)
            finally:
                active.pop()
            metadata = getattr(result, "metadata", {})
            rows = result.results if hasattr(result, "results") else result
            if isinstance(result, tuple):
                rows, metadata = result
            stages.append({"name": label + ":output", "parent": parent, **extra,
                           "metadata": metadata, "results": [asdict(r) for r in rows]})
            return result
        return wrapped

    trace: dict[str, Any] = {}

    def observe(retrieval: Any, evidence: Any, metadata: Any) -> None:
        trace.update(retrieval=asdict(retrieval), evidence=[asdict(e) for e in evidence], metadata=metadata)

    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '120s'"))
        readonly = session.execute(text("SHOW transaction_read_only")).scalar_one()
        if readonly != "on":
            raise ValueError("Read-only transaction required")
        with ExitStack() as stack:
            for name in FUNCTIONS:
                stack.enter_context(patch.object(search, name, instrument(name)))
            stack.enter_context(patch.object(service, "build_answer_provider", side_effect=AssertionError("No provider")))
            try:
                answer = service.answer_question(
                    session, settings, api["question"], collection=api["collection"], top_k=api["top_k"],
                    method=api["method"], answer_style=api["answer_style"], answer_language=api["answer_language"],
                    provider=NoGeneration(), trace_observer=observe,
                )
                boundary = {"status": answer.status, "generation_reached": False}
            except CaptureComplete:
                boundary = {"status": "stopped_before_generation", "generation_reached": True}
        if not trace:
            raise ValueError("Service trace missing")
        files.write(output / "boundaries.json", {"stages": stages, "trace": trace, "api": api, "boundary": boundary})
        # Entire collection inventory, never selected with expected article identities.
        corpus, articles = {}, {}
        for chunk, article in session.execute(select(Chunk, Article).join(Article).join(Collection).where(
                Collection.name == api["collection"]).order_by(Chunk.id)):
            corpus[str(chunk.id)] = {"article_id": str(chunk.article_id), "chunk_id": str(chunk.id),
                "chunk_index": chunk.chunk_index, "page_start": chunk.page_start, "page_end": chunk.page_end,
                "source_type": chunk.source_type, "text_layer": chunk.text_layer, "full_text": chunk.text,
                "title": article.title, "doi": article.doi}
        for article_id in sorted({row["article_id"] for row in corpus.values()}):
            article = session.get(Article, UUID(article_id))
            pdf = resolve_article_pdf(article, settings, "original").path.resolve()
            if files.sha(pdf.read_bytes()) != article.checksum_sha256:
                raise ValueError("PDF checksum mismatch")
            bindings.update(files.bindings([pdf]))
            articles[article_id] = {"article_id": article_id, "title": article.title, "authors": article.authors,
                "journal": article.journal, "year": article.year, "abstract": article.abstract,
                "original_pdf_path": str(pdf), "original_pdf_sha256": article.checksum_sha256}
        session.rollback()
    if policy.denied or guard.denied:
        raise ValueError("Forbidden network/reference access")
    files.verify(bindings)
    result = {"case": case, "bindings": bindings, "historical_trace_identical": trace == historical,
              "transaction_read_only": readonly, "transaction_end": "rollback",
              "model_calls": 0, "oauth_calls": 0, "slots": 0, "network_denials": policy.denied,
              "gold_read_denials": guard.denied}
    for name, value in (("capture", result), ("corpus", corpus), ("articles", articles)):
        files.write(output / f"{name}.json", value)
    files.manifest(output)
    return {"id": case_id, "historical_trace_identical": result["historical_trace_identical"],
            "stages": len(stages), "chunks": len(corpus), "articles": len(articles), **boundary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[f"Q{i:02}" for i in range(1, 6)], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(capture(args.case, args.output, policy), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
