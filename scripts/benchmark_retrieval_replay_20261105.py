"""Replay the actual answer service from frozen channels, without DB or generation."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import asdict
from typing import Any
from unittest.mock import patch

from scripts.benchmark_retrieval_capture_20261105 import FUNCTIONS
from scripts.run_swelling_retrieval_audit import CaptureComplete, NoGeneration


def replay(value: dict[str, Any], settings: Any, *, wide: bool = False,
           replacement: Any = None) -> dict[str, Any]:
    from sqlalchemy.engine import Engine

    from app.generation import service
    from app.retrieval import search

    expected = value["stages"]
    channel_calls, stages, counts, active = [], [], {}, []

    def channel(name: str) -> Any:
        def call(_session: Any, query: str, collection: str, top_k: int, **kwargs: Any) -> Any:
            matches = [s for s in expected if s["name"].startswith(name + ":") and s["name"].endswith(":output")
                       and s.get("query") == query and s.get("top_k", s.get("requested_top_k")) == top_k]
            if len(matches) != 1:
                raise ValueError("Missing/ambiguous frozen channel: " + name)
            row = matches[0]
            channel_calls.append({"name": name, "query": query, "top_k": top_k})
            stages.append(row)
            return search.SearchResponse(query=query, results=[search.SearchResult(**r) for r in row["results"]],
                                         metadata=row["metadata"])
        return call

    def instrument(name: str) -> Any:
        original = getattr(search, name)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            counts[name] = counts.get(name, 0) + 1
            label = f"{name}:{counts[name]}"
            is_hybrid = name == "hybrid_search"
            parent = active[-1] if active else None
            if not is_hybrid:
                stages.append({"name": label + ":input", "parent": parent, "results": [asdict(r) for r in args[0]]})
            active.append(label)
            try:
                result = original(*args, **kwargs)
            finally:
                active.pop()
            metadata = getattr(result, "metadata", {})
            rows = result.results if hasattr(result, "results") else result
            if isinstance(result, tuple):
                rows, metadata = result
            stages.append({"name": label + ":output", "parent": parent, "metadata": metadata,
                           **({"query": args[1], "top_k": args[3]} if is_hybrid else {}),
                           "results": [asdict(r) for r in rows]})
            return result
        return wrapped

    trace: dict[str, Any] = {}

    def observe(retrieval: Any, evidence: Any, metadata: Any) -> None:
        trace.update(retrieval=asdict(retrieval), evidence=[asdict(e) for e in evidence], metadata=metadata)

    api = value.get("api", value.get("request"))
    original_rank = search._rerank_cross_lingual_results

    def wide_rank(rows: Any, bundle: Any, *, window_size: int) -> Any:
        return original_rank(rows, bundle, window_size=len(rows))

    with ExitStack() as stack:
        stack.enter_context(patch.object(Engine, "connect", side_effect=AssertionError("Offline replay forbids DB")))
        stack.enter_context(patch.object(service, "build_answer_provider", side_effect=AssertionError("No provider")))
        for name in ("exact_search", "semantic_search"):
            stack.enter_context(patch.object(search, name, channel(name)))
        if wide:
            stack.enter_context(patch.object(search, "_rerank_cross_lingual_results", wide_rank))
        for name in FUNCTIONS:
            if name not in {"exact_search", "semantic_search"}:
                stack.enter_context(patch.object(search, name, instrument(name)))
        if replacement is not None:
            original_search = service.search_chunks

            def replace_search(*args: Any, **kwargs: Any) -> Any:
                baseline = original_search(*args, **kwargs)
                return replacement(baseline)
            stack.enter_context(patch.object(service, "search_chunks", replace_search))
        try:
            answer = service.answer_question(
                None, settings, api["question"], collection=api["collection"], top_k=api["top_k"], method=api["method"],
                answer_style=api["answer_style"], answer_language=api["answer_language"], provider=NoGeneration(),
                trace_observer=observe,
            )
            boundary = {"status": answer.status, "generation_reached": False}
        except CaptureComplete:
            boundary = {"status": "stopped_before_generation", "generation_reached": True}
    if not trace:
        raise ValueError("Missing replay trace")
    # Older captures also recorded these two observer boundaries explicitly.
    observer_names = {s["name"] for s in expected}
    if "retrieval_top_k" in observer_names:
        stages.append({"name": "retrieval_top_k", "results": trace["retrieval"]["results"]})
    if "generation_evidence" in observer_names:
        stages.append({"name": "generation_evidence", "results": trace["evidence"]})
    if not wide and replacement is None:
        if trace != value["trace"]:
            raise ValueError("Baseline full service trace differs")
        for previous, current in zip(expected, stages, strict=True):
            if previous["name"] != current["name"] or previous["results"] != current["results"]:
                raise ValueError("Boundary differs: " + previous["name"])
    return {"trace": trace, "stages": stages, "boundary": boundary, "channel_calls": channel_calls}
