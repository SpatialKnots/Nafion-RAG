"""Bounded real-run controls; these tests never dispatch external requests."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import run_satoh_fan_qa_20261110 as run


def public():
    return json.loads(run.PUBLIC.read_bytes())


def test_question_only_payload_preserves_original_and_adds_only_declared_article_citation():
    source = public()
    cases = run.make_cases(source)
    assert len(cases) == 20
    for row, case in zip(source["cases"], cases, strict=True):
        label = case["id"].split("_")[0]
        year = "2013" if label == "Satoh" else "2018"
        assert case["question_original"] == row["question_verbatim"]
        assert case["question"] == f"По статье {label} ({year}): " + row["question_verbatim"]
        assert set(case) == {"id", "question_original", "question", "article_id", "original_pdf_sha256",
                             "original_pdf_path", "augmentation"}


@pytest.mark.parametrize("change", ["reference", "wrong_article", "wrong_pdf", "duplicate", "reorder", "empty"])
def test_unsupported_payload_or_scope_identity_is_rejected(change):
    source = public()
    if change == "reference":
        source["cases"][0]["reference_answer"] = "do not transmit"
    elif change == "wrong_article":
        source["cases"][0]["article_id"] = source["cases"][-1]["article_id"]
    elif change == "wrong_pdf":
        source["cases"][0]["original_pdf_sha256"] = "0" * 64
    elif change == "duplicate":
        source["cases"][1] = copy.deepcopy(source["cases"][0])
    elif change == "reorder":
        source["cases"].reverse()
    else:
        source["cases"][0]["question_verbatim"] = " "
    with pytest.raises(ValueError):
        run.make_cases(source)


@pytest.mark.parametrize("path", [run.PUBLIC, run.ROOT / "output/old/references.json",
                                 run.ROOT / "docs/records/old.md",
                                 Path("C:/Users/unive/Downloads/Ariadne_QA_Satoh_2013_Fan_2018.md")])
def test_gold_guard_blocks_reference_and_prior_output_reads(path):
    guard = run.GoldReadGuard()
    with pytest.raises(PermissionError):
        guard("open", (str(path), "r", 0))
    assert len(guard.denied) == 1


def test_gold_guard_allows_only_current_question_freeze_scope_and_ordinary_sources():
    guard = run.GoldReadGuard()
    for path in (run.BASE / "input_freeze_v01/questions.json", run.SCOPE, run.PDFS["Satoh"]):
        guard("open", (str(path), "r", 0))
    assert not guard.denied


def test_foreign_article_stops_before_parent_observation_or_transport(tmp_path):
    case = run.make_cases(public())[0]
    obs = run.ScopeObservation(tmp_path, SimpleNamespace(gigachat_credentials=None), run.files.NetworkPolicy(), target=case)
    with patch.object(run.files.Observation, "observe") as parent:
        with pytest.raises(ValueError, match="outside"):
            obs.observe(None, None, [SimpleNamespace(article_id="foreign", chunk_id="c")], {})
        parent.assert_not_called()
    assert (tmp_path / "scope_mismatch.json").is_file()


def test_offline_native_boundary_is_captured_once_without_transport(tmp_path):
    from app.generation.gigachat import AUTH_URL, CHAT_URL

    obs = run.ScopeObservation(tmp_path, SimpleNamespace(gigachat_credentials=None), run.files.NetworkPolicy(),
                               target=run.make_cases(public())[0])
    provider = SimpleNamespace()
    obs.instrument(provider)
    assert b"placeholder" in provider._post(AUTH_URL, b"scope", "secret", oauth=True)
    with pytest.raises(run.files.PreparedBoundary):
        provider._post(CHAT_URL, b'{"native":"question only"}', "token")
    assert (tmp_path / "request.json").read_bytes() == b'{"native":"question only"}'
    with pytest.raises(ValueError, match="repeated"):
        provider._post(CHAT_URL, b"second", "token")
    assert (obs.fake_oauth_calls, obs.native_boundary_calls) == (1, 1)
    assert not obs.policy.denied and not obs.policy.external


def test_no_send_or_seal_without_current_authorization():
    with pytest.raises(PermissionError):
        run.send({}, run.files.NetworkPolicy(), authorized=False)
    with pytest.raises(PermissionError):
        run.seal(authorized=False)


def test_closed_scope_cannot_send_again(tmp_path):
    (tmp_path / "scope_closed_v01.json").write_text("{}")
    with patch.object(run, "BASE", tmp_path), pytest.raises(FileExistsError, match="closed"):
        run.send({}, run.files.NetworkPolicy(), authorized=True)


def test_interrupted_reserved_attempt_is_unknown_and_allowance_closes(tmp_path):
    base, ledger = tmp_path / "new", tmp_path / "slots"
    base.mkdir()
    digest = "a" * 64
    (ledger / digest).mkdir(parents=True)
    run.files.write(base / "approval_v01.json", {"request_sha256": {cid: digest if n == 0 else None
                                                                for n, cid in enumerate(run.IDS)}})
    with patch.object(run, "BASE", base), patch.object(run.files, "LEDGER", ledger):
        result = run.close()
    assert result["model_attempts"] is None and result["oauth_attempts"] is None
    assert result["cases"][0]["status"] == "reserved_outcome_unknown"
    assert result["remaining_allowance"] == 0
    assert all(row["resend_authorized"] is False for row in result["cases"])
    assert (ledger / digest / "scope_closed_satoh_fan_20261110_v01.json").is_file()
