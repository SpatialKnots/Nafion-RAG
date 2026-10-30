"""Safety properties of the explicitly bounded development smoke runner."""

import json

import pytest

from scripts import gigachat_answer_smoke as smoke


def test_reservation_cannot_be_reused_after_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(smoke, "LEDGER", tmp_path / "ledger")
    slot = smoke.reserve("a" * 64, {"status": "reserved"})
    assert json.loads((slot / "attempt.json").read_bytes()) == {"status": "reserved"}
    with pytest.raises(FileExistsError):
        smoke.reserve("a" * 64, {"status": "retry"})


def test_manifest_detects_additions_and_changes(tmp_path):
    smoke.save(tmp_path / "request.json", b"original")
    smoke.manifest(tmp_path)
    smoke.verify_manifest(tmp_path)
    (tmp_path / "request.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="manifest changed"):
        smoke.verify_manifest(tmp_path)


def test_network_policy_blocks_model_before_transport_phase():
    policy = smoke.NetworkPolicy()
    policy("socket.connect", (None, ("127.0.0.1", 59999)))
    with pytest.raises(RuntimeError, match="forbidden"):
        policy("socket.getaddrinfo", ("api.giga.chat", 443))
    policy.external = True
    policy("socket.getaddrinfo", ("api.giga.chat", 443))
    with pytest.raises(RuntimeError, match="forbidden"):
        policy("socket.getaddrinfo", ("huggingface.co", 443))


def test_raw_response_is_durable_before_production_parser(tmp_path):
    from types import SimpleNamespace

    from app.generation.gigachat import CHAT_URL

    expected = tmp_path / "prepared"
    live = tmp_path / "live"
    expected.mkdir()
    live.mkdir()
    body = b'{"native":"request"}'
    smoke.save(expected / "request.json", body)
    provider = SimpleNamespace(_post=lambda *a, **k: b'{"raw":"response"}')
    observation = smoke.Observation(live, SimpleNamespace(gigachat_credentials="test-key"), smoke.NetworkPolicy(), expected)
    observation.instrument(provider)
    assert provider._post(CHAT_URL, body, "Bearer test-token") == b'{"raw":"response"}'
    assert (live / "response.bin").read_bytes() == b'{"raw":"response"}'
    assert observation.result["model_attempts"] == 1
    with pytest.raises(ValueError, match="second model attempt"):
        provider._post(CHAT_URL, body, "Bearer test-token")


def test_live_request_drift_blocks_transport(tmp_path):
    from types import SimpleNamespace

    from app.generation.gigachat import CHAT_URL

    expected = tmp_path / "prepared"
    expected.mkdir()
    smoke.save(expected / "request.json", b"frozen")
    calls = []
    provider = SimpleNamespace(_post=lambda *a, **k: calls.append(a))
    observation = smoke.Observation(tmp_path, SimpleNamespace(gigachat_credentials="test-key"), smoke.NetworkPolicy(), expected)
    observation.instrument(provider)
    with pytest.raises(ValueError, match="differs from frozen"):
        provider._post(CHAT_URL, b"changed", "Bearer test-token")
    assert not calls
    assert observation.result["model_attempts"] == 0


def recovery_fixture(tmp_path, monkeypatch, model_attempts=0):
    monkeypatch.setattr(smoke, "LEDGER", tmp_path / "ledger")
    parent = tmp_path / "failed"
    parent.mkdir()
    attempt = {"request_sha256": "a" * 64, "output": str(parent.resolve())}
    slot = smoke.reserve("a" * 64, attempt)
    smoke.write(parent / "attempt.json", attempt)
    result = {"model_attempts": model_attempts, "oauth_attempts": 1, "http_status": 503,
              "answer": {"detail": "GigaChat OAuth request failed (URLError)"}}
    smoke.write(parent / "result.json", result)
    smoke.write(slot / "result.json", result)
    smoke.manifest(parent)
    return parent, slot


def test_infrastructure_continuation_preserves_original_and_cannot_repeat(tmp_path, monkeypatch):
    parent, original = recovery_fixture(tmp_path, monkeypatch)
    before = (original / "result.json").read_bytes()
    child = smoke.reserve_continuation(parent, "a" * 64, {"status": "reserved"})
    assert child.parent == original
    assert (original / "result.json").read_bytes() == before
    with pytest.raises(FileExistsError):
        smoke.reserve_continuation(parent, "a" * 64, {"status": "retry"})


def test_infrastructure_continuation_forbidden_after_any_model_attempt(tmp_path, monkeypatch):
    parent, _ = recovery_fixture(tmp_path, monkeypatch, model_attempts=1)
    with pytest.raises(ValueError, match="before any model attempt"):
        smoke.reserve_continuation(parent, "a" * 64, {"status": "retry"})
