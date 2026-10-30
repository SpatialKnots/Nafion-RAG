"""Bounded send controls with fake transport; no live OAuth or model calls."""

import json
from types import SimpleNamespace

import pytest

from app.generation.gigachat import GigaChatAnswerProvider
from scripts import gigachat_answer_smoke as smoke
from scripts import run_gigachat_event_pilot as pilot
from scripts.gigachat_event_proposal import build_request, catalog


def fake_study(tmp_path, monkeypatch):
    source = catalog("Samples equilibrated until spectra were unchanged.")
    prepared = tmp_path / "cases" / pilot.IDS[0] / "prepared"
    prepared.mkdir(parents=True)
    raw = smoke.encode(build_request("What criterion?", source, model="GigaChat-2-Max", max_tokens=1200))
    smoke.save(prepared / "request.json", raw)
    smoke.write(prepared / "catalog.json", source)
    study = {"cases": [{"id": pilot.IDS[0], "request_sha256": smoke.sha(raw)}], "ca_bundle_file": "",
             "authorization": "constructed", "bindings": {}}
    monkeypatch.setattr(pilot, "BASE", tmp_path)
    monkeypatch.setattr(pilot, "read_study", lambda: study)
    monkeypatch.setattr(smoke, "LEDGER", tmp_path / "ledger")
    monkeypatch.setattr(smoke, "configure", lambda: SimpleNamespace(
        gigachat_ca_bundle_file="", gigachat_credentials="constructed-key", gigachat_scope="GIGACHAT_API_PERS",
        rag_model="GigaChat-2-Max", rag_timeout_seconds=120, rag_gigachat_max_tokens=1200))
    return raw


def test_unauthorized_send_stops_before_settings_or_transport(monkeypatch):
    monkeypatch.setattr(pilot, "read_study", lambda: pytest.fail("Must not read/send before authorization"))
    with pytest.raises(ValueError, match="authorization"):
        pilot.send(pilot.IDS[0], authorized=False, policy=smoke.NetworkPolicy())


@pytest.mark.parametrize("failure", ["oauth", "native_filter", "valid_selection"])
def test_single_slot_counts_and_raw_before_parse_survive_failures(tmp_path, monkeypatch, failure):
    expected_body = fake_study(tmp_path, monkeypatch)
    seen = []
    def post(self, url, body, authorization, *, oauth=False):
        seen.append("oauth" if oauth else "model")
        assert len(list((tmp_path / "ledger").iterdir())) == 1
        if oauth:
            if failure == "oauth":
                raise OSError("constructed offline failure")
            return b'{"access_token":"constructed-token"}'
        assert body == expected_body
        missing = {"status": "not_found", "ids": []}
        value = {"target": {"kind": "measurement_wait", "context_ids": ["S1"], "sample": missing,
                            "operation": {"status": "present", "ids": ["S1"]}, "duration": missing,
                            "conditions": missing, "completion_criterion": {"status": "present", "ids": ["S1"]}},
                 "other_events": [], "diagnostic": "Constructed."}
        return json.dumps({"choices": [{"finish_reason": "blacklist" if failure == "native_filter" else "stop",
                                        "message": {"role": "assistant", "content": json.dumps(value)}}]}).encode()
    monkeypatch.setattr(GigaChatAnswerProvider, "_post", post)
    result = pilot.send(pilot.IDS[0], authorized=True, policy=smoke.NetworkPolicy())
    assert result["oauth_attempts"] == 1 and result["model_attempts"] == (failure != "oauth")
    assert seen == (["oauth"] if failure == "oauth" else ["oauth", "model"])
    live = tmp_path / "cases" / pilot.IDS[0] / "live"
    assert (live / "response.bin").exists() == (failure != "oauth")
    assert result["status"] == {"oauth": "transport_failed", "native_filter": "output_rejected",
                                "valid_selection": "integrity_valid_scientific_assignment_unverified"}[failure]
    smoke.verify_manifest(live)
    before = list(seen)
    with pytest.raises(FileExistsError):
        pilot.send(pilot.IDS[0], authorized=True, policy=smoke.NetworkPolicy())
    assert seen == before  # A second output/command cannot reopen the request slot.
