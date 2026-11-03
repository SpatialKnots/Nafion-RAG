"""Read-only Kim2015 loss capture; external reference stays outside retrieval."""

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
from scripts.run_swelling_retrieval_audit import CaptureComplete, NoGeneration  # noqa: E402

BASE = ROOT / "output/user_reference_20261030_01"
PROTOCOL = ROOT / "docs/records/kim_retrieval_audit_protocol_v0.1.md"
VERSION = "kim_retrieval_audit_v0.1"


def article_presence(rows: list[dict[str, Any]], article_id: str) -> list[dict[str, Any]]:
    """Article membership says nothing about presence of a particular source statement."""
    return [{"rank": rank, "chunk_id": row["chunk_id"], "page_start": row["page_start"],
             "page_end": row["page_end"], "text_layer": row.get("text_layer", "unknown")}
            for rank, row in enumerate(rows, 1) if row["article_id"] == article_id]


def capture(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    from sqlalchemy import select, text

    from app.db.models import Article, Chunk
    from app.db.session import SessionLocal
    from app.documents.service import resolve_article_pdf
    from app.generation import service
    from app.retrieval import search

    for folder in (BASE / "preparation_v01", BASE / "review_v01", BASE / "live_review_v01"):
        files.verify_manifest(folder)
    prepared = BASE / "preparation_v01"
    old_contract = json.loads((prepared / "contract.json").read_bytes())
    files.verify(old_contract["input_bindings"])
    request = json.loads((prepared / "api_request.json").read_bytes())
    historical = json.loads((prepared / "trace.json").read_bytes())
    reference_review = json.loads((BASE / "review_v01/report.json").read_bytes())
    windows = reference_review["source_observations"]
    target_checksum = windows[0]["original_pdf_sha256"]
    output.mkdir(parents=True, exist_ok=False)
    bindings = {**old_contract["input_bindings"], **files.bindings([
        Path(__file__), PROTOCOL, ROOT / "scripts/run_swelling_retrieval_audit.py",
        ROOT / "scripts/gigachat_answer_smoke.py", prepared / "trace.json", prepared / "api_request.json",
        BASE / "review_v01/report.json", BASE / "live_review_v01/report.json",
    ])}
    stages: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    active: list[str] = []

    def record(name: str, rows: Any, **extra: Any) -> None:
        stages.append({"name": name, "results": [asdict(r) for r in rows], **extra})

    def instrument(name: str) -> Any:
        original = getattr(search, name)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            counters[name] = counters.get(name, 0) + 1
            label = name + ":" + str(counters[name])
            parent = active[-1] if active else None
            channel = name in {"exact_search", "semantic_search", "hybrid_search"}
            extra = ({"query": args[1], "requested_top_k": args[3]} if channel else {})
            if not channel:
                record(label + ":input", args[0], parent=parent)
            active.append(label)
            try:
                result = original(*args, **kwargs)
            finally:
                active.pop()
            if hasattr(result, "results"):
                record(label + ":output", result.results, parent=parent, metadata=result.metadata, **extra)
            elif isinstance(result, tuple):
                record(label + ":output", result[0], parent=parent, metadata=result[1], **extra)
            else:
                record(label + ":output", result, parent=parent, **extra)
            return result
        return wrapped

    traced: dict[str, Any] = {}

    def observe(retrieval: Any, evidence: Any, metadata: Any) -> None:
        traced.update(retrieval=asdict(retrieval), evidence=[asdict(e) for e in evidence], metadata=metadata)
        record("retrieval_top_k", retrieval.results)
        stages.append({"name": "generation_evidence", "results": [asdict(e) for e in evidence]})

    stopped = False
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '120s'"))
        readonly = session.execute(text("SHOW transaction_read_only")).scalar_one()
        if readonly != "on":
            raise ValueError("Read-only transaction required")
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
                stopped = True
        if not traced or not stopped:
            raise ValueError("Expected trace and explicit stop before generation")
        files.write(output / "boundaries.json", {"stages": stages, "trace": traced})
        # Identify the target only after retrieval; never promote/inject its chunks.
        target = session.scalars(select(Article).where(Article.checksum_sha256 == target_checksum)).one()
        target_id = str(target.id)
        inventory = [{"article_id": str(c.article_id), "chunk_id": str(c.id), "chunk_index": c.chunk_index,
                      "page_start": c.page_start, "page_end": c.page_end, "text_layer": c.text_layer,
                      "source_type": c.source_type, "full_text": c.text}
                     for c in session.scalars(select(Chunk).where(Chunk.article_id == target.id).order_by(Chunk.chunk_index))]
        ids = sorted({target_id, *[r["article_id"] for stage in stages for r in stage["results"]]})
        articles = []
        for article_id in ids:
            article = session.get(Article, UUID(article_id))
            if article is None:
                raise ValueError("Captured article missing")
            pdf = resolve_article_pdf(article, settings, "original").path.resolve()
            if files.sha(pdf.read_bytes()) != article.checksum_sha256:
                raise ValueError("Original PDF checksum differs")
            bindings.update(files.bindings([pdf]))
            articles.append({"article_id": article_id, "title": article.title, "authors": article.authors,
                "journal": article.journal, "year": article.year, "abstract": article.abstract,
                "conclusions": None, "terms": None, "uncollected_fields": ["conclusions", "terms"],
                "original_pdf_path": str(pdf), "original_pdf_sha256": article.checksum_sha256,
                "metadata_basis": "registered DB metadata; not independently verified"})
        session.rollback()
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    files.verify(bindings)
    report = {"version": VERSION, "request": request, "question": request["question"], "bindings": bindings,
        "target_article_id": target_id, "target_origin": "external_reference_posthoc_diagnostic_target_only",
        "database_target_inventory": inventory, "reference_windows": windows, "articles": articles,
        "stages": stages, "trace": traced, "historical_final_trace_identical": traced == historical,
        "transaction_read_only": readonly, "transaction_end": "rollback", "model_calls": 0, "oauth_calls": 0,
        "slot_reservations": 0, "network_denials": policy.denied,
        "observations": [{"name": s["name"], "parent": s.get("parent"), "count": len(s["results"]),
                          "target_article_rows": article_presence(s["results"], target_id)} for s in stages],
        "scientific_acceptance": "not_established", "independent_accuracy": None,
        "limitation": "Fresh-process reproduction; historical internal boundaries unavailable. No runtime fix."}
    files.write(output / "capture.json", report)
    files.manifest(output)
    return {"historical_final_trace_identical": traced == historical, "target_article_id": target_id,
            "target_chunks": len(inventory), "articles": len(articles), "observations": report["observations"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(capture(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
