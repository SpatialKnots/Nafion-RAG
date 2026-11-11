"""Actual preparation-to-context wiring with explicitly synthetic DB/source seams."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from app.generation import context_action_routes as route
from app.generation import preparation, service
from app.generation.preparation_routes import PreparationRequest
from app.retrieval.search import SearchResponse, SearchResult
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    case = copy.deepcopy(read(files.ROOT / "output/source_role_assembly_20261109/controls_v01.json")["constructed"][0])
    article = str(UUID(int=100))
    for i, e in enumerate(case["sources"], 101):
        e["article_id"], e["chunk_id"] = article, str(UUID(int=i))
    case["reference"]["article_id"] = article
    rows = [SearchResult(e["article_id"], e["chunk_id"], e["title"], e["doi"], e["page_start"], e["page_end"],
        e["source_type"], e["text"], 0.8, "synthetic", full_text=e["text"], text_layer="original") for e in case["sources"]]

    class Session:
        no_autoflush = nullcontext()

        def execute(self, statement):
            if str(statement) != "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY":
                raise AssertionError("Only original read-only transaction setup is expected in synthetic session")

        def get(self, model, key):
            return SimpleNamespace(authors=[{"name": "Smith"}, {"name": "Jones"}], year=2021,
                                   title="Constructed article", doi=None)

    def registry(session, settings, evidence):
        return {"chunks": {e.chunk_id: {"article_id": e.article_id, "page_start": e.page_start, "page_end": e.page_end,
                    "source_type": e.source_type, "text": e.text, "text_layer": "original"} for e in evidence},
                "chunk_layers": {e.chunk_id: "original" for e in evidence}, "pages": {}, "diagnostics": []}

    loader = Mock(return_value=rows[2:])
    forbidden = Mock(side_effect=AssertionError("Probe forbids real generation provider"))
    request = PreparationRequest(question=case["question"], collection="synthetic", method="exact", answer_language="ru")
    with patch.object(service, "search_chunks", return_value=SearchResponse(case["question"], rows[:2],
                {"explicit_source_reference": case["reference"]})), patch.object(service, "build_answer_provider", forbidden), \
            patch.object(preparation, "collect_sources", registry), patch.object(route, "collect_sources", registry), \
            patch.object(route, "load_context_rows", loader):
        result = route.prepare_context_action(Session(), request)
    forbidden.assert_not_called()
    files.write(output / "result.json", result)
    summary = {"stop_reason": result["stop_reason"], "lookup_calls": loader.call_count,
        "baseline_blockers": result["input_packet"]["content"]["parent"]["preparation"]["blocking_reasons"],
        "added": result["added_evidence"] is not None, "generation_provider_calls": forbidden.call_count,
        "synthetic_DB_source_metadata": True}
    files.write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    files.configure()
    result = run(args.output)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
