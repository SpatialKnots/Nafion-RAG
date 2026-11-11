"""Offline request and isolated-scope controls; no real transport."""

import json

import pytest

from app.generation.answer_instruction_experiment import ExperimentalScientificAnswerProvider
from app.generation.required_answer_fields import RequirementGuidedAnswerProvider, build
from scripts import gigachat_answer_smoke as f
from scripts import prepare_answer_instruction_experiment_v02_20261110 as old_capture
from scripts import run_required_answer_fields_20261110 as runner


def test_three_family_card_is_only_addition_to_existing_native():
    from test_required_answer_fields import QUESTION, source

    evidence = [source()]
    old = old_capture.capture_request(ExperimentalScientificAnswerProvider, QUESTION, evidence)
    new = runner.capture(RequirementGuidedAnswerProvider, QUESTION, evidence)
    before, after = json.loads(old['request']), json.loads(new['request'])
    assert after['messages'][1]['content'].endswith(before['messages'][1]['content'])
    assert 'Requirement card:' in after['messages'][1]['content']
    after['messages'][1]['content'] = before['messages'][1]['content']
    assert after == before
    assert old_capture.ExperimentalScientificAnswerProvider is ExperimentalScientificAnswerProvider


def test_positive_control_native_is_exactly_retained():
    from test_required_answer_fields import source

    question = 'Which products have not been identified?'
    old = old_capture.capture_request(ExperimentalScientificAnswerProvider, question, [source()])
    new = runner.capture(RequirementGuidedAnswerProvider, question, [source()])
    assert old == new


def test_new_explicit_scope_never_reopens_or_writes_old_identical_request_slot(tmp_path, monkeypatch):
    from test_answer_instruction_pilot import setup_pilot

    base, oldledger, freeze, raw = setup_pilot(tmp_path, monkeypatch)
    inp = runner.read(freeze / 'case/input.json')
    from app.generation.providers import Evidence
    f.write(freeze / 'case/requirements.json', build(inp['question'], [Evidence(**e) for e in inp['evidence']]))
    (freeze / 'manifest.json').unlink()
    f.manifest(freeze)
    oldslot = f.reserve(f.sha(raw), {'authorization': 'closed-old-synthetic-scope'})
    oldbytes = (oldslot / 'attempt.json').read_bytes()
    newledger = tmp_path / 'new-ledger'
    monkeypatch.setattr(runner, 'BASE', base)
    monkeypatch.setattr(runner, 'LEDGER', newledger)
    events = []

    def transport(self, url, body, authorization, *, oauth=False):
        events.append(oauth)
        if oauth:
            return b'{"access_token":"offline-placeholder"}'
        assert body == raw
        return json.dumps({'model': 'synthetic', 'choices': [{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': json.dumps({'answerable': False, 'claims': []})}}]}).encode()

    monkeypatch.setattr(RequirementGuidedAnswerProvider, '_post', transport)
    result = runner.send('case', f.NetworkPolicy())
    assert result['status'] == 'provider_abstained' and events == [True, False]
    assert (oldslot / 'attempt.json').read_bytes() == oldbytes
    assert list(oldslot.iterdir()) == [oldslot / 'attempt.json']
    assert (newledger / f.sha(raw) / 'result.json').exists()
    f.verify_manifest(base / 'diagnostics/case')
    assert runner.close()['remaining_allowance'] == 0
    with pytest.raises(FileExistsError, match='closed'):
        runner.send('case', f.NetworkPolicy())
    assert events == [True, False]


def test_wrong_capture_class_is_refused():
    with pytest.raises(ValueError, match='declared'):
        runner.capture(object, 'question', [])
