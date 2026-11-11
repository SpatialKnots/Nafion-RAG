"""Live pilot budget/immutability controls, using synthetic transport only."""

import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from app.generation.providers import Evidence
from scripts import gigachat_answer_smoke as f
from scripts import run_answer_instruction_pilot_20261110 as pilot
from scripts.prepare_answer_instruction_experiment_v02_20261110 import capture_request


def setup_pilot(tmp_path, monkeypatch):
    base, ledger = tmp_path / "pilot", tmp_path / "ledger"
    monkeypatch.setattr(pilot, "BASE", base)
    monkeypatch.setattr(f, "LEDGER", ledger)
    settings = SimpleNamespace(gigachat_credentials="offline-key", gigachat_scope="GIGACHAT_API_PERS",
        rag_model="GigaChat-2-Max", gigachat_ca_bundle_file="")
    monkeypatch.setattr(f, "configure", lambda: settings)
    source = Evidence("E1", "work", "chunk", "Constructed", None, 1, 2, "main_text",
                      "Conductivity was measured by impedance spectroscopy.", 1, "frozen", {}, {})
    question = "How was conductivity measured?"
    raw = capture_request(pilot.ExperimentalScientificAnswerProvider, question, [source])["request"]
    freeze = base / "input_freeze_v01"
    folder = freeze / "case"
    folder.mkdir(parents=True)
    f.save(folder / "request.json", raw)
    f.write(folder / "input.json", {"question": question, "evidence": [asdict(source)], "request_sha256": f.sha(raw)})
    f.write(freeze / "scope.json", {"raw_user_authorization": "synthetic", "cases": [
        {"id": "case", "request_sha256": f.sha(raw)}]})
    f.write(freeze / "bindings.json", {})
    f.manifest(freeze)
    return base, ledger, freeze, raw


@pytest.mark.parametrize("mode", ["answer", "abstain", "invalid", "failure"])
def test_one_shot_native_is_preserved_and_slot_closed_without_resend(tmp_path, monkeypatch, mode):
    base, ledger, freeze, expected = setup_pilot(tmp_path, monkeypatch)
    from app.generation.providers import GenerationUnavailableError
    events = []

    def transport(self, url, body, authorization, *, oauth=False):
        events.append(oauth)
        if oauth:
            return b'{"access_token":"synthetic-token"}'
        assert body == expected
        if mode == "failure":
            raise GenerationUnavailableError("synthetic failure")
        if mode == "invalid":
            return b"not JSON"
        answer = {"answerable": mode == "answer", "claims": [
            {"text": "Conductivity was measured by impedance spectroscopy.", "citation_ids": ["E1"]}
        ] if mode == "answer" else []}
        return json.dumps({"model": "synthetic-model", "choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(answer)}}]}).encode()

    monkeypatch.setattr(pilot.ExperimentalScientificAnswerProvider, "_post", transport)
    result = pilot.send("case", f.NetworkPolicy())
    assert events == [True, False]
    assert result["model_attempts"] == result["oauth_attempts"] == 1
    assert result["status"] == {"answer": "provider_answered", "abstain": "provider_abstained",
        "invalid": "provider_output_rejected", "failure": "transport_failed"}[mode]
    live = base / "live/case"
    f.verify_manifest(live)
    slot, = list(ledger.iterdir())
    assert (slot / "answer_instruction_pilot_closed_v01.json").exists()
    with pytest.raises(FileExistsError):
        pilot.send("case", f.NetworkPolicy())
    assert events == [True, False]
    assert pilot.close()["remaining_allowance"] == 0


def test_pre_oauth_request_drift_stops_without_consuming_slot(tmp_path, monkeypatch):
    base, ledger, freeze, raw = setup_pilot(tmp_path, monkeypatch)
    request = freeze / "case/request.json"
    request.write_bytes(raw + b" ")
    (freeze / "manifest.json").unlink()
    f.manifest(freeze)
    with pytest.raises(ValueError, match="Pre-OAuth"):
        pilot.send("case", f.NetworkPolicy())
    assert not ledger.exists() and not (base / "live").exists()


def test_closed_scope_stops_all_sends_before_slot(tmp_path, monkeypatch):
    base, ledger, freeze, raw = setup_pilot(tmp_path, monkeypatch)
    pilot.close()
    with pytest.raises(FileExistsError, match="closed"):
        pilot.send("case", f.NetworkPolicy())
    assert not ledger.exists()


def test_five_unique_predeclared_cases():
    assert len(pilot.SELECTED) == len(set(pilot.SELECTED)) == 5
    assert len({cid for _, cid in pilot.SELECTED}) == 5
    assert all(dataset in {"rewriting_v01", "rewriting_v02"} for dataset, cid in pilot.SELECTED)
