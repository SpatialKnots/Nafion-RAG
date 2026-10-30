"""Capture unchanged local retrieval boundaries for the saved Li-Nafion question, without inference."""

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.retrieval_loss_audit import VERSION, retention_path  # noqa: E402

BASE = ROOT / "output/user_swelling_answer_20261029"


class CaptureComplete(Exception):
    """Expected stop at generation, not a provider output or failure suppression."""


class NoGeneration:
    def generate(self, *args: Any, **kwargs: Any) -> Any:
        raise CaptureComplete("Retrieval audit stops before generation")


def capture(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    from sqlalchemy import select, text

    from app.db.models import Article, Chunk
    from app.db.session import SessionLocal
    from app.documents.service import resolve_article_pdf
    from app.generation import service
    from app.retrieval import search

    output.mkdir(parents=True, exist_ok=False)
    files.verify_manifest(BASE / "prepared")
    files.verify_manifest(BASE / "live")
    files.verify_manifest(BASE / "review_v02")
    previous = json.loads((BASE / "prepared/trace.json").read_bytes())
    request = json.loads((BASE / "prepared/api_request.json").read_bytes())
    reviewed = json.loads((BASE / "review_v02/report.json").read_bytes())
    old_bindings = json.loads((BASE / "prepared/contract.json").read_bytes())["input_bindings"]
    # Verify the retrieval/generation implementation, original PDFs and local models/index inputs.
    immutable = {name: digest for name, digest in old_bindings.items()
                 if Path(name).is_relative_to(ROOT / "app") or Path(name).is_relative_to(ROOT / "data")}
    files.verify(immutable)
    bindings = {**immutable, **files.bindings([
        Path(__file__), ROOT / "scripts/retrieval_loss_audit.py", ROOT / "scripts/gigachat_answer_smoke.py",
        BASE / "prepared/trace.json", BASE / "prepared/api_request.json", BASE / "review_v02/report.json",
    ])}
    target = next(w for w in reviewed["source_windows"] if w["label"] == "larger_mixture_value")
    stages: list[dict[str, Any]] = []
    calls: dict[str, int] = {}
    active: list[str] = []

    def record(name: str, results: Any, **extra: Any) -> None:
        stages.append({"name": name, "results": [asdict(r) for r in results], **extra})

    def instrument(name: str) -> Any:
        original = getattr(search, name)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            calls[name] = calls.get(name, 0) + 1
            label = name + ":" + str(calls[name])
            parent = active[-1] if active else None
            if name.startswith("_") or name == "feature_rerank_cross_lingual_results":
                record(label + ":input", args[0], parent=parent)
            active.append(label)
            try:
                result = original(*args, **kwargs)
            finally:
                active.pop()
            if hasattr(result, "results"):
                record(label + ":output", result.results, parent=parent, metadata=result.metadata)
            elif isinstance(result, tuple):
                record(label + ":output", result[0], parent=parent, metadata=result[1])
            else:
                record(label + ":output", result, parent=parent)
            return result
        return wrapped

    traced: dict[str, Any] = {}

    def observe(retrieval: Any, evidence: Any, metadata: Any) -> None:
        traced.update(retrieval=asdict(retrieval), evidence=[asdict(e) for e in evidence], metadata=metadata)
        record("retrieval_top_k", retrieval.results)
        stages.append({"name": "generation_evidence", "results": [asdict(e) for e in evidence]})

    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '120s'"))
        readonly = session.execute(text("SHOW transaction_read_only")).scalar_one()
        if readonly != "on":
            raise ValueError("Read-only transaction is required")
        with ExitStack() as stack:
            for name in ("exact_search", "semantic_search", "hybrid_search", "_rerank_cross_lingual_results",
                         "_legacy_rerank_cross_lingual_results", "_diversify_cross_lingual_results",
                         "feature_rerank_cross_lingual_results", "_ensure_cross_language_presence"):
                stack.enter_context(patch.object(search, name, instrument(name)))
            stack.enter_context(patch.object(service, "build_answer_provider", side_effect=AssertionError("Provider forbidden")))
            try:
                service.answer_question(session, settings, request["question"], collection=request["collection"],
                    top_k=request["top_k"], method=request["method"], answer_style=request["answer_style"],
                    answer_language=request["answer_language"], provider=NoGeneration(), trace_observer=observe)
            except CaptureComplete:
                pass
        if not traced:
            raise ValueError("Trace was not captured")
        files.write(output / "boundaries.json", {"stages": stages, "trace": traced})
        # Current DB inventory is recorded separately, never injected as a retrieval candidate.
        chunks = session.scalars(select(Chunk).where(Chunk.article_id == UUID(target["article_id"]),
            Chunk.page_start <= target["page_number"], Chunk.page_end >= target["page_number"]).order_by(Chunk.chunk_index)).all()
        inventory = [{"article_id": str(c.article_id), "chunk_id": str(c.id), "page_start": c.page_start,
                      "page_end": c.page_end, "text_layer": c.text_layer, "source_type": c.source_type,
                      "full_text": c.text, "chunk_index": c.chunk_index} for c in chunks]
        ids = sorted({r["article_id"] for s in stages for r in s["results"]})
        articles = []
        for article_id in ids:
            a = session.get(Article, UUID(article_id))
            if a is None:
                raise ValueError("Captured article is missing")
            pdf = resolve_article_pdf(a, settings, "original").path
            if files.sha(pdf.read_bytes()) != a.checksum_sha256:
                raise ValueError("Original PDF checksum differs")
            bindings.update(files.bindings([pdf.resolve()]))
            articles.append({"article_id": article_id, "title": a.title, "authors": a.authors, "journal": a.journal,
                "year": a.year, "abstract": a.abstract, "conclusions": None, "terms": None,
                "original_pdf_path": str(pdf.resolve()), "original_pdf_sha256": a.checksum_sha256,
                "metadata_basis": "registered metadata, not independently verified",
                "uncollected_fields": ["conclusions", "terms"]})
        session.rollback()
    target_pdf = Path(target["original_pdf_path"])
    if files.sha(target_pdf.read_bytes()) != target["original_pdf_sha256"]:
        raise ValueError("Target PDF differs from post-hoc source")
    # Fresh extraction is a verification only, never a new retrieval candidate.
    import fitz
    with fitz.open(target_pdf) as document:
        page_text = document[target["page_number"] - 1].get_text("text")
    if page_text[target["start"]:target["end"]] != target["exact_text"]:
        raise ValueError("Exact target anchor differs from fresh PDF extraction")
    target_args = {"article_id": target["article_id"], "page_number": target["page_number"], "exact_text": target["exact_text"]}
    # This is an observation list, not a falsely linear model of nested channels.
    observations = [{**retention_path([s], **target_args)[0], "parent": s.get("parent")} for s in stages]
    files.verify(bindings)
    report = {"version": VERSION, "question": request["question"], "request": request,
        "bindings": bindings, "target": target, "target_origin": "assistant_posthoc_counterexample_from_previous_stage",
        "fresh_target_page": {"page_number": target["page_number"], "text_layer": "original", "page_text": page_text},
        "database_target_inventory": inventory, "stages": stages, "observations": observations, "trace": traced,
        "historical_final_trace_identical": traced == previous, "transaction_read_only": readonly,
        "articles": articles, "model_calls": 0, "oauth_calls": 0, "network_denials": policy.denied,
        "scientific_acceptance": "not_established", "independent_accuracy": None,
        "limitation": "Fresh-process reproduction; historical internal stages were not captured. No ranking fix or semantic validation."}
    files.write(output / "capture.json", report)
    files.manifest(output)
    return {"stages": len(stages), "historical_final_trace_identical": traced == previous,
            "target_chunks": len(inventory), "articles": len(articles), "observations": observations}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(capture(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
