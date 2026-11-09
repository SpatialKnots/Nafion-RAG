"""Real service/frozen-channel checks, never generated scientific answers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.retrieval.requested_context import body_facets, requested_facets
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.benchmark_retrieval_replay_20261105 import replay
from scripts.check_requested_context_runtime_20261105 import baseline_scope
from scripts.explicit_reference_retrieval_20261105 import select

FROZEN = Path(__file__).resolve().parents[2] / "output/benchmark_retrieval_repair_20261105/capture_v02"


@pytest.fixture(scope="module")
def settings():
    return files.configure()


@pytest.fixture(autouse=True)
def retrieval_layer_only():
    # This suite audits original raw retrieval objects, before later fact rendering.
    with patch("app.generation.service.prepare_answer_facts", return_value=None), \
            patch("app.generation.service.complete_context", side_effect=lambda s, q, c, f, rows: (rows, None)):
        # Historical retention-only audit, before separately tested DB completion.
        yield


@pytest.mark.parametrize("case_id", ["Q03", "Q04"])
def test_requested_body_context_survives_real_service_cuts(case_id, settings):
    source = read(FROZEN / case_id / "boundaries.json")
    # Reproduce the pre-context historical runtime without the later fidelity
    # audit. Current production behavior is exercised separately below.
    with baseline_scope(), patch("app.generation.service.prepare_answer_fidelity", return_value=None):
        original = replay(source, settings)
    repaired = replay(source, settings, replacement=lambda response: response)
    question = source["api"]["question"]
    facets = requested_facets(question)
    matches = {facet for e in repaired["trace"]["evidence"] for facet in body_facets(e["text"], facets)}
    assert matches == set(facets)
    assert repaired["boundary"]["generation_reached"] is True
    assert len(repaired["trace"]["retrieval"]["results"]) <= source["api"]["top_k"]
    assert {e["chunk_id"] for e in repaired["trace"]["evidence"]} != {
        e["chunk_id"] for e in original["trace"]["evidence"]}
    corpus = read(FROZEN / "Q01/corpus.json")
    for e in repaired["trace"]["evidence"]:
        assert e["text"] == corpus[e["chunk_id"]]["full_text"]


@pytest.mark.parametrize("case_id", ["Q01", "Q05"])
def test_author_match_and_quotes_do_not_bypass_existing_gate(case_id, settings):
    source = read(FROZEN / case_id / "boundaries.json")
    corpus, articles = read(FROZEN / "Q01/corpus.json"), read(FROZEN / "Q01/articles.json")

    def candidate(response):
        return select(source["api"]["question"], response, corpus, articles, top_k=source["api"]["top_k"])[0]

    with patch("app.retrieval.search._source_reference_search", return_value=(None, None)):
        result = replay(source, settings, replacement=candidate)
    assert result["boundary"] == {"status": "insufficient_evidence", "generation_reached": False}
    assert result["trace"]["metadata"]["evidence_adequacy"]["reason"] == "explicit_reference_not_uniquely_resolved"
