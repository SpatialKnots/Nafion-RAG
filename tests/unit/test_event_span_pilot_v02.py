"""New bounded-pilot controls use fake transport only, no live calls."""

import json
from types import SimpleNamespace

import pytest

from app.generation.gigachat import GigaChatAnswerProvider
from scripts import gigachat_answer_smoke as files
from scripts import run_event_span_pilot_v02 as pilot
from scripts.event_spans_v02 import build_request, catalog


def fake_study(tmp_path, monkeypatch):
    source = catalog("Samples equilibrated until spectra were unchanged.")
    body = files.encode(build_request("What criterion?", source, model="GigaChat-2-Max", max_tokens=1200))
    prepared = tmp_path / "cases" / pilot.IDS[0] / "prepared"
    prepared.mkdir(parents=True)
    files.save(prepared / "request.json", body)
    files.write(prepared / "input.json", {"source": source})
    study = {"cases": [{"id": pilot.IDS[0], "request_sha256": files.sha(body)}], "model": "GigaChat-2-Max",
             "scope": "GIGACHAT_API_PERS", "max_tokens": 1200, "timeout_seconds": 120, "ca_bundle_file": "",
             "authorization": "constructed", "bindings": {}}
    settings = SimpleNamespace(gigachat_ca_bundle_file="", gigachat_credentials="constructed-key",
                               gigachat_scope="GIGACHAT_API_PERS", rag_model="GigaChat-2-Max",
                               rag_timeout_seconds=120, rag_gigachat_max_tokens=1200)
    monkeypatch.setattr(pilot, "BASE", tmp_path)
    monkeypatch.setattr(pilot, "read_study", lambda: study)
    monkeypatch.setattr(files, "LEDGER", tmp_path / "ledger")
    monkeypatch.setattr(files, "configure", lambda: settings)
    return body, settings


def test_no_authorization_stops_before_settings_or_network(monkeypatch):
    monkeypatch.setattr(pilot, "read_study", lambda: pytest.fail("Must stop before reading study"))
    with pytest.raises(ValueError, match="authorization"):
        pilot.send(pilot.IDS[0], authorized=False, policy=files.NetworkPolicy())


@pytest.mark.parametrize("outcome", ["oauth_failure", "bad_token", "model_failure", "filtered", "truncated", "invalid_local", "valid"])
def test_durable_slots_exact_body_no_retry_and_strict_outcomes(tmp_path, monkeypatch, outcome):
    body, settings = fake_study(tmp_path, monkeypatch)
    seen = []
    raw_reply = None

    def post(self, url, raw_body, authorization, *, oauth=False):
        nonlocal raw_reply
        seen.append("oauth" if oauth else "model")
        assert len(list((tmp_path / "ledger").iterdir())) == 1
        if oauth:
            if outcome == "oauth_failure":
                raise OSError(settings.gigachat_credentials)
            return b'{"access_token":{}}' if outcome == "bad_token" else b'{"access_token":"constructed-token"}'
        assert raw_body == body
        if outcome == "model_failure":
            raise OSError("constructed-token")
        value = {"events": [], "target": {"status": "not_found", "event_ids": []}, "relations": [], "diagnostic": "Constructed."}
        if outcome == "invalid_local":
            value["diagnostic"] = ""
        finish = {"filtered": "blacklist", "truncated": "length"}.get(outcome, "stop")
        raw_reply = json.dumps({"choices": [{"finish_reason": finish,
                                            "message": {"role": "assistant", "content": json.dumps(value)}}]}).encode()
        return raw_reply

    monkeypatch.setattr(GigaChatAnswerProvider, "_post", post)
    result = pilot.send(pilot.IDS[0], authorized=True, policy=files.NetworkPolicy())
    failed_oauth = outcome in {"oauth_failure", "bad_token"}
    assert seen == (["oauth"] if failed_oauth else ["oauth", "model"])
    assert result["oauth_attempts"] == 1 and result["model_attempts"] == (not failed_oauth)
    live = tmp_path / "cases" / pilot.IDS[0] / "live"
    assert (live / "response.bin").exists() == (raw_reply is not None)
    if raw_reply is not None:
        assert (live / "response.bin").read_bytes() == raw_reply
    expected = "transport_failed" if outcome in {"oauth_failure", "bad_token", "model_failure"} else (
        "integrity_valid_scientific_assignment_unverified" if outcome == "valid" else "output_rejected")
    assert result["status"] == expected
    assert "constructed-key" not in json.dumps(result) and "constructed-token" not in json.dumps(result)
    files.verify_manifest(live)
    slot, = (tmp_path / "ledger").iterdir()
    assert (slot / "result.json").read_bytes() == (live / "result.json").read_bytes()
    before = list(seen)
    with pytest.raises((ValueError, FileExistsError)):
        pilot.send(pilot.IDS[0], authorized=True, policy=files.NetworkPolicy())
    assert seen == before
    if expected == "transport_failed":
        with pytest.raises(ValueError, match="stopped after a transport failure"):
            pilot.send(pilot.IDS[1], authorized=True, policy=files.NetworkPolicy())
        assert seen == before


@pytest.mark.parametrize("setting,value", [("rag_model", "different"), ("rag_gigachat_max_tokens", 2400),
                                         ("gigachat_ca_bundle_file", "different.pem"), ("rag_timeout_seconds", 240)])
def test_changed_settings_fail_before_reservation(tmp_path, monkeypatch, setting, value):
    _, settings = fake_study(tmp_path, monkeypatch)
    setattr(settings, setting, value)
    with pytest.raises(ValueError, match="settings differ"):
        pilot.send(pilot.IDS[0], authorized=True, policy=files.NetworkPolicy())
    assert not (tmp_path / "ledger").exists()
