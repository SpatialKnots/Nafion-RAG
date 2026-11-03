"""Separate all-candidate diagnostic; never changes the captured production search."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.run_kim_retrieval_audit import article_presence  # noqa: E402


def expand(captured: Path, output: Path, policy: files.NetworkPolicy) -> dict:
    settings = files.configure()
    from sqlalchemy import func, select, text

    from app.db.models import Article, Chunk, Collection
    from app.db.session import SessionLocal
    from app.retrieval import search

    files.verify_manifest(captured)
    capture = json.loads((captured / "capture.json").read_bytes())
    files.verify(capture["bindings"])
    stages = {s["name"]: s for s in capture["stages"]}
    request = capture["request"]
    output.mkdir(parents=True, exist_ok=False)
    bindings = {**capture["bindings"], **files.bindings([
        Path(__file__), captured / "capture.json", captured / "manifest.json",
    ])}
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '120s'"))
        readonly = session.execute(text("SHOW transaction_read_only")).scalar_one()
        if readonly != "on":
            raise ValueError("Read-only transaction required")
        count = session.scalar(select(func.count(Chunk.id)).join(Article).join(Collection).where(
            Collection.name == request["collection"]))
        if not count:
            raise ValueError("Empty collection")
        semantic_count = stages["semantic_search:1:output"]["metadata"]["chunk_count"]
        exact = search.exact_search(session, request["question"], request["collection"], count)
        semantic = search.semantic_search(session, request["question"], request["collection"], semantic_count,
                                         settings=settings, enforce_top_k_limit=False)
        expanded = {"exact": [asdict(r) for r in exact.results], "semantic": [asdict(r) for r in semantic.results]}
        for channel, rows in expanded.items():
            prior = stages[channel + "_search:1:output"]
            if rows[:len(prior["results"])] != prior["results"]:
                raise ValueError("Expanded channel prefix differs: " + channel)
        if semantic.metadata != stages["semantic_search:1:output"]["metadata"]:
            raise ValueError("Semantic index identity differs")
        session.rollback()
    files.verify(bindings)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    result = {"version": "kim_all_candidate_diagnostic_v0.1", "bindings": bindings,
        "request": request, "origin": "separate_expanded_diagnostic_not_production_retrieval_or_fix",
        "database_collection_chunk_count": count, "semantic_index_chunk_count": semantic_count,
        "transaction_read_only": readonly, "transaction_end": "rollback", "expanded_channels": expanded,
        "prefixes_identical_to_captured_production_channels": True,
        "target_article_id": capture["target_article_id"],
        "target_ranks": {name: article_presence(rows, capture["target_article_id"]) for name, rows in expanded.items()},
        "model_calls": 0, "oauth_calls": 0, "slot_reservations": 0, "network_denials": policy.denied}
    files.write(output / "expanded.json", result)
    files.manifest(output)
    return {"counts": {name: len(rows) for name, rows in expanded.items()}, "target_ranks": result["target_ranks"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captured", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(expand(args.captured, args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
