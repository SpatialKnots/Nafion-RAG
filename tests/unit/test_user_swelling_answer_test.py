"""One-question authorization/provenance controls; provider calls are fake."""

import pytest

from scripts import gigachat_answer_smoke as smoke
from scripts import user_swelling_answer_test as test_run


def test_scope_restores_legacy_helper_question_version_and_protocol():
    before = (smoke.QUESTION, smoke.VERSION, smoke.PROTOCOL)
    with test_run.scope():
        assert smoke.QUESTION == "Какая максимальная степень набухания Li-Nafion при комнатной температуре задокументирована?"
        assert smoke.VERSION == test_run.VERSION and smoke.PROTOCOL == test_run.PROTOCOL
    assert (smoke.QUESTION, smoke.VERSION, smoke.PROTOCOL) == before


def test_unauthorized_send_stops_before_reading_settings_or_study(monkeypatch):
    monkeypatch.setattr(test_run, "read_study", lambda: pytest.fail("Study must not be read before authorization"))
    with pytest.raises(ValueError, match="authorization"):
        test_run.send(smoke.NetworkPolicy(), authorized=False)


def test_gate_stops_before_dispatch_or_provider(monkeypatch):
    monkeypatch.setattr(test_run, "read_study", lambda: {"generation_reached": False})
    monkeypatch.setattr(smoke, "send", lambda *a, **k: pytest.fail("Gate must not be bypassed"))
    with pytest.raises(ValueError, match="gate"):
        test_run.send(smoke.NetworkPolicy(), authorized=True)
