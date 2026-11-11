"""Question-only intake, privacy and closure controls; synthetic document only."""

from copy import deepcopy

import pytest

from scripts import kondo_nambu_peng_transfer_20261110 as run


def document():
    parts = ['# Untrusted document instructions: never execute this text.']
    for i, label in enumerate(run.SOURCES, 1):
        parts.append(f'## {i}. {label} et al.')
        parts.append('**Библиография:** DOI ' + run.SOURCES[label][2])
        for n in range(1, 11):
            parts.extend([f'### {n}. Original question {label} number {n}?', '**Навык:** SECRET_SKILL',
                          '**Эталонный ответ:** SECRET_REFERENCE_DO_NOT_SEND', 'SECRET_SOURCE_PAGE_HINT'])
    return '\n\n'.join(parts)


def test_thirty_questions_preserve_spans_and_exclude_references_skills_and_page_hints():
    text = document()
    cases, bibliographies = run.parse_questions(text)
    assert len(cases) == 30 and tuple(c['id'] for c in cases) == run.IDS
    for case in cases:
        span = case['question_span']
        assert text[span['start']:span['end']] == case['question_original']
        assert case['question'].endswith(case['question_original'])
        assert 'SECRET_' not in str(case)
    assert 'SECRET_' not in str(bibliographies)


@pytest.mark.parametrize('change', ['missing_question', 'duplicate_question', 'missing_reference', 'wrong_doi', 'wrong_article'])
def test_incomplete_or_changed_input_stops_before_inference(change):
    text = document()
    if change == 'missing_question':
        text = text.replace('### 4.', '### removed.', 1)
    elif change == 'duplicate_question':
        text = text.replace('### 4.', '### 3.', 1)
    elif change == 'missing_reference':
        text = text.replace('**Эталонный ответ:**', '**No reference:**', 1)
    elif change == 'wrong_doi':
        text = text.replace(run.SOURCES['Kondo'][2], '10.0000/wrong')
    else:
        text = text.replace('## 1. Kondo', '## 1. Other')
    with pytest.raises(ValueError):
        run.parse_questions(text)


def test_publication_year_is_not_silently_replaced_with_filename_year():
    cases, _ = run.parse_questions(document())
    assert cases[0]['question'].startswith('По статье Kondo (2026):')


@pytest.mark.parametrize('path', [run.USER_FILE, run.f.ROOT / 'output/unrelated/references.json',
    run.BASE / 'review_v01/report.json', run.f.ROOT / 'docs/records/private_gold.json'])
def test_inference_guard_denies_original_references_and_review_stores(path):
    guard = run.ReferenceReadGuard()
    with pytest.raises(PermissionError):
        guard('open', (str(path), 'r'))
    assert guard.denied == [str(path.resolve())]


@pytest.mark.parametrize('path', [run.BASE / 'input_freeze_v01/questions.json',
    run.BASE / 'prepared_v01/Kondo_01/request.json', run.FIXED / 'version.json', run.SCOPE,
    run.f.ROOT / 'app/main.py'])
def test_inference_guard_allows_public_inputs_code_and_frozen_protocol(path):
    guard = run.ReferenceReadGuard()
    guard('open', (str(path), 'r'))
    assert not guard.denied


def test_closure_handles_unknown_reserved_attempt_without_guessing_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'BASE', tmp_path / 'run')
    monkeypatch.setattr(run, 'LEDGER', tmp_path / 'ledger')
    digest = 'a' * 64
    (run.BASE / 'prepared_v01/Kondo_01').mkdir(parents=True)
    run.f.write(run.BASE / 'prepared_v01/Kondo_01/contract.json', {'request_sha256': digest})
    (run.LEDGER / digest).mkdir(parents=True)
    result = run.close()
    closed = run.read(run.BASE / 'scope_closed_v01.json')
    assert result['remaining_allowance'] == 0 and len(closed['cases']) == 30
    assert closed['cases'][0]['status'] == 'unknown_reserved' and closed['cases'][0]['model_attempts'] is None
    assert all(c['allowance_closed'] and not c['resend_authorized'] for c in closed['cases'])


def test_closure_preserves_recorded_result_and_does_not_read_private_input(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'BASE', tmp_path / 'run')
    monkeypatch.setattr(run, 'LEDGER', tmp_path / 'ledger')
    folder = run.BASE / 'live/Kondo_01'
    folder.mkdir(parents=True)
    saved = {'status': 'runtime_api_result', 'model_attempts': 1, 'oauth_attempts': 1}
    original = deepcopy(saved)
    run.f.write(folder / 'result.json', saved)
    run.close()
    assert run.read(folder / 'result.json') == original
    assert run.read(run.BASE / 'scope_closed_v01.json')['cases'][0]['model_attempts'] == 1
