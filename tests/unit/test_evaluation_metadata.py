from types import SimpleNamespace

import pytest

from app.evaluation.retrieval import run_extended_retrieval_evaluation, run_retrieval_evaluation
from app.retrieval.search import SearchResponse


@pytest.mark.parametrize("runner", [run_retrieval_evaluation, run_extended_retrieval_evaluation])
@pytest.mark.parametrize("change_index", [False, True])
def test_language_diagnostics_can_vary_but_index_must_not(monkeypatch, tmp_path, runner, change_index):
    questions = tmp_path / "questions.yaml"
    questions.write_text(
        "- id: en\n  query: membrane conductivity\n  expected_article_dois: ['10.1000/example']\n  expected_keywords: []\n"
        "- id: ru\n  query: проводимость мембраны\n  expected_article_dois: ['10.1000/example']\n  expected_keywords: []\n",
        encoding="utf-8",
    )
    responses = iter(
        [
            SearchResponse(
                query="membrane conductivity",
                results=[],
                metadata={
                    "embedding_model": "test/model",
                    "manifest_sha256": "original",
                    "language_diversity": {"query_language": "en", "promoted": False},
                },
            ),
            SearchResponse(
                query="проводимость мембраны",
                results=[],
                metadata={
                    "embedding_model": "test/model",
                    "manifest_sha256": "changed" if change_index else "original",
                    "language_diversity": {"query_language": "ru", "promoted": True},
                },
            ),
        ]
    )
    monkeypatch.setattr("app.evaluation.retrieval.search_chunks", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr("app.evaluation.retrieval._article_checksums_for_results", lambda *args: {})
    monkeypatch.setattr("app.evaluation.retrieval._chunk_texts_for_results", lambda *args: {})
    monkeypatch.setattr("app.evaluation.retrieval._git_commit", lambda: "test")
    monkeypatch.setattr("app.evaluation.retrieval._corpus_manifest_sha256", lambda: "corpus")
    args = (object(), SimpleNamespace(default_top_k=10), questions)
    kwargs = {"collection": "literature", "top_k": 10, "method": "hybrid_cross_lingual"}
    if change_index:
        with pytest.raises(ValueError, match="metadata changed"):
            runner(*args, **kwargs)
    else:
        report = runner(*args, **kwargs)
        assert report["summary"]["total"] == 2
        assert report["settings"]["text_matching"] == "lower_latin_ligatures_v1"
        assert "language_diversity" not in report["settings"]["retrieval_metadata"]
        assert report["questions"][0]["retrieval_metadata"]["language_diversity"]["query_language"] == "en"
        assert report["questions"][1]["retrieval_metadata"]["language_diversity"]["promoted"] is True
