"""Question-only isolation and native boundaries; no actual DB/model calls."""

import json
from types import SimpleNamespace

import pytest

from scripts import gigachat_answer_smoke as smoke
from scripts import prepare_benchmark_inputs_20261103 as inputs


def test_packet_exact_inventory_and_no_reference_fields():
    cases = inputs.load_cases()
    assert [c["id"] for c in cases] == ["Q01", "Q02", "Q03", "Q04", "Q05"]
    assert all(set(c) == {"id", "question"} for c in cases)


@pytest.mark.parametrize("change", ["hash", "extra_top", "extra_case", "live", "order", "non_object"])
def test_packet_corruption_or_annotations_rejected(tmp_path, change):
    value = json.loads(inputs.CASES.read_bytes())
    if change == "extra_top":
        value["reference_answer"] = "constructed sentinel"
    elif change == "extra_case":
        value["cases"][0]["expected_article_id"] = "constructed sentinel"
    elif change == "live":
        value["live_authorization"] = True
    elif change == "order":
        value["cases"].reverse()
    elif change == "non_object":
        value["cases"][0] = "constructed sentinel"
    path = tmp_path / "packet.json"
    path.write_bytes(smoke.encode(value))
    digest = "0" * 64 if change == "hash" else smoke.sha(path.read_bytes())
    with pytest.raises(ValueError):
        inputs.load_cases(path, digest)


@pytest.mark.parametrize("path", [
    inputs.ROOT / "docs/records/Nafion_RAG_Benchmark_v1.0_original.md",
    inputs.ROOT / "output/user_benchmark_20261103/review_v01/report.json",
    inputs.ROOT / "docs/records/user_benchmark_provenance_2026-11-03_v0.1.json",
    "C:/Users/unive/Downloads/Nafion_RAG_Benchmark_v1.0.md",
])
def test_gold_reads_denied(path):
    guard = inputs.GoldReadGuard()
    with pytest.raises(PermissionError):
        guard("open", (str(path), "r", 0))
    assert len(guard.denied) == 1


def test_question_protocol_and_corpus_are_allowed():
    guard = inputs.GoldReadGuard()
    for path in (inputs.CASES, inputs.PROTOCOL, inputs.ROOT / "data/pdf/constructed.pdf"):
        guard("open", (str(path), "r", 0))
    assert guard.denied == []


def test_scope_restored_on_failure():
    original = smoke.QUESTION, smoke.VERSION, smoke.PROTOCOL
    with pytest.raises(RuntimeError):
        with inputs.case_scope(inputs.load_cases()[0]):
            assert smoke.QUESTION == inputs.load_cases()[0]["question"]
            raise RuntimeError("constructed")
    assert (smoke.QUESTION, smoke.VERSION, smoke.PROTOCOL) == original


def test_native_transport_cannot_dispatch_or_retry(tmp_path):
    from app.generation.gigachat import AUTH_URL, CHAT_URL

    settings = SimpleNamespace(gigachat_credentials="constructed-not-a-secret")
    observer = inputs.BoundaryObservation(tmp_path, settings, smoke.NetworkPolicy())
    provider = SimpleNamespace(_post=lambda *a, **k: pytest.fail("Real transport must never run"))
    observer.instrument(provider)
    assert provider._post(AUTH_URL, b"", "", oauth=True) == b'{"access_token":"offline-preparation-placeholder"}'
    native = b'{"model":"constructed","messages":[]}'
    with pytest.raises(smoke.PreparedBoundary):
        provider._post(CHAT_URL, native, "")
    assert (tmp_path / "request.json").read_bytes() == native == observer.body
    with pytest.raises(ValueError, match="repeated"):
        provider._post(CHAT_URL, native, "")
    assert observer.result["model_attempts"] == observer.result["oauth_attempts"] == 0


@pytest.mark.parametrize("reached,size", [(True, 80), (True, 100001), (False, 0)])
def test_actual_route_preparation_never_authorizes_calls(tmp_path, monkeypatch, reached, size):
    settings = SimpleNamespace(default_collection="literature", rag_retrieval_method="hybrid_cross_lingual", rag_top_k=5,
        rag_model="GigaChat-2-Max", rag_gigachat_max_tokens=1200, rag_timeout_seconds=120)
    freeze = tmp_path / "freeze"
    freeze.mkdir()
    smoke.write(freeze / "runtime.json", {"input_bindings": {}})
    smoke.manifest(freeze)
    monkeypatch.setattr(inputs, "FREEZE", freeze)
    monkeypatch.setattr(smoke, "configure", lambda: settings)
    monkeypatch.setattr(smoke, "source_inputs", lambda *a: {})
    monkeypatch.setattr(smoke, "reserve", lambda *a, **k: pytest.fail("No live reservation"))
    monkeypatch.setattr(inputs, "BoundaryObservation", lambda *a: SimpleNamespace(trace={}, sources={"diagnostics": []},
        body=b"x" * size if reached else None, result={}, fake_oauth_calls=int(reached), native_boundary_calls=int(reached)))
    case = inputs.load_cases()[0]

    def route(observation, request):
        assert set(request) == {"question", "collection", "method", "top_k", "answer_style", "answer_language"}
        assert request["question"] == case["question"]
        if reached:
            raise smoke.PreparedBoundary()
        return SimpleNamespace(status_code=200, json=lambda: {"status": "insufficient_evidence"})

    monkeypatch.setattr(smoke, "run_route", route)
    folder = tmp_path / "prepared"
    result = inputs.prepare(folder, case, smoke.NetworkPolicy(), inputs.GoldReadGuard())
    contract = json.loads((folder / "contract.json").read_bytes())
    assert (result["preparation_status"] == "prepared_unsent") == (reached and size <= 100000)
    assert contract["maximum_model_attempts"] == contract["maximum_oauth_attempts"] == contract["new_slot_reservations"] == 0
    assert contract["new_model_calls"] == contract["new_oauth_calls"] == 0
    assert contract["reference_answers_or_expected_articles_passed_to_inference"] is False
    smoke.verify_manifest(folder)
