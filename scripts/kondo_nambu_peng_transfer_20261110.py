"""Question-only intake and one-shot fixed-version experimental API execution."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/kondo_nambu_peng_transfer_20261110'
USER_FILE = Path(r'C:\Users\unive\Downloads\Ariadne_QA_Kondo_Nambu_Peng.md')
SCOPE = f.ROOT / 'docs/records/kondo_nambu_peng_transfer_2026-11-10_v0.1.md'
FIXED = f.ROOT / 'output/required_fields_guard_20261110/freeze_v01'
DRAW = f.ROOT / 'output/guard_transfer_article_draw_20261110/draw.json'
LEDGER = f.ROOT / 'data/experiments/kondo_nambu_peng_transfer_20261110'
SOURCES = {
    'Kondo': ('3e970332-cced-4895-b44e-50a48bdc8e17', '2026', '10.1002/adma.202514060'),
    'Nambu': ('0743b075-4938-44d9-8dfe-61c6a6bfaf58', '2016', '10.5796/electrochemistry.84.776'),
    'Peng': ('0a3cf9d1-7c1e-4a90-9662-f1fbcceb1b46', '2021', '10.1039/d1ra05326d'),
}
IDS = tuple(f'{label}_{i:02}' for label in SOURCES for i in range(1, 11))


def read(path):
    return json.loads(path.read_bytes())


def parse_questions(text):
    sections = list(re.finditer(r'^## (?P<n>[123])\. (?P<label>Kondo|Nambu|Peng)\b[^\r\n]*', text, re.M))
    if [(m['n'], m['label']) for m in sections] != list(zip(('1', '2', '3'), SOURCES, strict=True)):
        raise ValueError('Expected exactly three ordered article sections')
    cases, bibliographies = [], []
    for i, section in enumerate(sections):
        end = sections[i + 1].start() if i < 2 else len(text)
        body = text[section.end():end]
        questions = list(re.finditer(r'^### (?P<n>\d+)\. (?P<q>[^\r\n]+)\r?$', body, re.M))
        if [m['n'] for m in questions] != [str(j) for j in range(1, 11)]:
            raise ValueError('Expected questions1..10 exactly once per source')
        bib = body[:questions[0].start()]
        label = section['label']
        if SOURCES[label][2].casefold() not in bib.casefold():
            raise ValueError('Bibliography DOI differs from selected PDF identity')
        bibliographies.append({'label': label, 'text': bib, 'heading': section[0]})
        for j, match in enumerate(questions):
            blockend = questions[j + 1].start() if j < 9 else len(body)
            block = body[match.end():blockend]
            if len(re.findall(r'\*\*Эталонный ответ:\*\*', block)) != 1:
                raise ValueError('Expected one held-back reference marker per question')
            start, finish = section.end() + match.start('q'), section.end() + match.end('q')
            cases.append({'id': f'{label}_{j + 1:02}', 'label': label, 'question_original': match['q'],
                'question_span': {'start': start, 'end': finish}, 'article_id': SOURCES[label][0],
                'question': f'По статье {label} ({SOURCES[label][1]}): ' + match['q'],
                'augmentation': 'explicit_supplied_article_context; original question verbatim',
                'source_doi_declared': SOURCES[label][2]})
    if tuple(c['id'] for c in cases) != IDS:
        raise ValueError('Expected thirty ordered unique question-only records')
    return cases, bibliographies


class ReferenceReadGuard:
    def __init__(self):
        self.denied = []

    def __call__(self, event, args):
        if event != 'open' or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        allowed_output = path.is_relative_to(BASE) and not any(x.startswith(('review_', 'assessment_', 'private_'))
            for x in path.relative_to(BASE).parts)
        allowed_fixed = path.is_relative_to(FIXED)
        docs = {SCOPE, f.ROOT / 'docs/records/required_fields_guard_2026-11-10_v0.1.md',
            f.ROOT / 'docs/records/guard_transfer_v0.1/README.md',
            f.ROOT / 'docs/records/guard_transfer_v0.1/registration_template.json'}
        forbidden = (path == USER_FILE.resolve() or path.name.casefold().startswith('ariadne_qa_')
            or path.is_relative_to(f.ROOT / 'output') and not (allowed_output or allowed_fixed)
            or path.is_relative_to(f.ROOT / 'docs/records') and path not in docs)
        if forbidden:
            self.denied.append(str(path))
            raise PermissionError('Question-only worker cannot open references/prior review')


def fixed_version():
    f.verify_manifest(FIXED)
    f.verify(read(FIXED / 'bindings.json'))
    if read(FIXED / 'version.json')['freeze_id'] != '27def498b8580a6922808d8eca08b0a5c6fb76f0eaa46657fc1cc279deacedd3':
        raise ValueError('Unexpected app version; do not tune on the new cohort')


def initialize():
    fixed_version()
    f.configure()
    raw = USER_FILE.read_bytes()
    text = raw.decode('utf-8-sig')
    cases, bibliography = parse_questions(text)
    selected = {r['article_id']: r for r in read(DRAW)['selected']}
    folder = BASE / 'input_freeze_v01'
    folder.mkdir(parents=True, exist_ok=False)
    for case in cases:
        paper = selected[case['article_id']]
        path = Path(paper['original_pdf_path'])
        if f.sha(path.read_bytes()) != paper['original_pdf_sha256']:
            raise ValueError('Original PDF hash changed')
        case.update(original_pdf_path=str(path), original_pdf_sha256=paper['original_pdf_sha256'])
    f.write(folder / 'questions.json', {'cases': cases, 'references_included': False, 'source_bibliography': bibliography})
    f.write(folder / 'reference_commitment.json', {'input_path': str(USER_FILE), 'input_sha256': f.sha(raw),
        'input_bytes': len(raw), 'reference_count': 30, 'raw_document_copied_to_inference_tree': False,
        'statement_verbatim': 'Я составил самостоятельно, без LLM', 'authorship': 'user_declared_self',
        'LLM_used': False, 'prepared_before_new_outputs': True, 'expert_verification': 'not_declared',
        'reference_contents_shown_to_implementation_model_before_inference': False})
    paths = [Path(__file__), SCOPE, f.ROOT / 'tests/unit/test_kondo_nambu_peng_transfer.py',
             FIXED / 'manifest.json', FIXED / 'bindings.json', FIXED / 'version.json']
    f.write(folder / 'bindings.json', f.bindings(paths))
    f.write(folder / 'runtime.json', {'raw_user_request': 'Вот сприсок вопросов. Всё как всегда',
        'maximum_model_attempts': 30, 'maximum_oauth_attempts': 30, 'attempts_per_question': 1,
        'automatic_retries': 0, 'fallbacks': 0, 'continuations': 0, 'reference_commitment_sha256': f.sha(raw),
        'fixed_version': read(FIXED / 'version.json')['freeze_id'], 'new_model_calls': 0})
    for path in paths[:3]:
        target = folder / 'source_snapshot' / path.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, path.read_bytes())
    f.manifest(folder)
    return {'questions': len(cases), 'sources': 3, 'references_held_back': 30, 'new_model_calls': 0}


def cases():
    fixed_version()
    f.verify_manifest(BASE / 'input_freeze_v01')
    f.verify(read(BASE / 'input_freeze_v01/bindings.json'))
    return read(BASE / 'input_freeze_v01/questions.json')['cases']


def run_route(observation, request):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import SessionLocal, get_session
    from app.generation import required_fields_guard_routes as routes
    from app.generation import service
    from app.main import app

    original, factory = service.answer_question, routes.make_provider

    def session_override():
        with SessionLocal() as session:
            try:
                yield session
            finally:
                session.rollback()

    def traced(session, *args, **kwargs):
        kwargs['trace_observer'] = lambda r, e, m: observation.observe(session, r, e, m)
        return original(session, *args, **kwargs)

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: observation.settings
    try:
        with patch.object(service, 'answer_question', traced), patch.object(routes, 'make_provider',
                lambda s: observation.instrument(factory(s))):
            with TestClient(app) as client:
                return client.post('/answer/experimental/required-fields', json=request)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)


class Observation(f.Observation):
    def __init__(self, *args, case, **kwargs):
        super().__init__(*args, **kwargs)
        self.case, self.readonly, self.scope_ok = case, None, False

    def observe(self, session, retrieval, evidence, metadata):
        from sqlalchemy import text

        self.readonly = session.execute(text('SHOW transaction_read_only')).scalar_one()
        if self.readonly != 'on':
            raise ValueError('Read-only transaction required')
        super().observe(session, retrieval, evidence, metadata)
        self.scope_ok = bool(evidence) and all(e.article_id == self.case['article_id'] for e in evidence)
        f.write(self.folder / 'scope.json', {'expected_article_id': self.case['article_id'], 'all_selected_match': self.scope_ok,
            'selected_article_ids': sorted({e.article_id for e in evidence}), 'transaction_read_only': self.readonly})


def prepare(case, policy, guard):
    if (BASE / 'scope_closed_v01.json').exists():
        raise FileExistsError('Scope closed')
    settings = f.configure()
    folder = BASE / 'prepared_v01' / case['id']
    folder.mkdir(parents=True, exist_ok=False)
    request = {'question': case['question'], 'collection': 'literature', 'top_k': 5, 'method': 'hybrid_cross_lingual',
               'answer_style': 'claims', 'answer_language': 'ru'}
    f.write(folder / 'api_request.json', request)
    obs, reached, http_status = Observation(folder, settings, policy, case=case), False, None
    with patch.object(f, 'QUESTION', case['question']), patch.object(f, 'PROTOCOL', SCOPE):
        try:
            response = run_route(obs, request)
            http_status = response.status_code
            f.write(folder / 'preparation_api_response.json', {'http_status': response.status_code, 'body': response.json()})
        except f.PreparedBoundary:
            reached = True
        if obs.trace is None or obs.sources is None:
            raise ValueError('Actual experimental API did not expose its preparation trace')
        bindings = f.source_inputs(settings, obs)
    fixed_version()
    size = len(obs.body) if obs.body else 0
    allowed = reached and obs.scope_ok and size <= 100000 and not obs.sources['diagnostics']
    reason = ('ready_unsent' if allowed else 'preparation_api_error' if http_status is not None and http_status != 200
              else 'baseline_preprovider_refusal' if not reached else
              'harness_article_scope_stop' if not obs.scope_ok else 'harness_budget_or_registry_stop')
    bindings.update(f.bindings([BASE / 'input_freeze_v01/manifest.json', BASE / 'input_freeze_v01/questions.json']))
    f.verify(bindings)
    contract = {'case': case, 'generation_reached': reached, 'dispatch_allowed': allowed, 'preparation_status': reason,
        'request_sha256': f.sha(obs.body) if obs.body else None, 'request_bytes': size, 'input_bindings': bindings,
        'transaction_read_only': obs.readonly, 'transaction_end': 'rollback', 'network_denials': policy.denied,
        'reference_read_denials': guard.denied, 'model_calls': 0, 'oauth_calls': 0}
    f.write(folder / 'contract.json', contract)
    f.manifest(folder)
    return {k: contract[k] for k in ('preparation_status', 'dispatch_allowed', 'request_bytes')}


def seal():
    rows = []
    for case in cases():
        folder = BASE / 'prepared_v01' / case['id']
        f.verify_manifest(folder)
        c = read(folder / 'contract.json')
        f.verify(c['input_bindings'])
        if c['case'] != case or c['transaction_read_only'] != 'on' or c['network_denials'] or c['reference_read_denials']:
            raise ValueError('Preparation drift or denied access')
        rows.append({'id': case['id'], 'dispatch_allowed': c['dispatch_allowed'], 'request_sha256': c['request_sha256']})
    digests = [r['request_sha256'] for r in rows if r['dispatch_allowed']]
    if len(digests) != len(set(digests)) or any((LEDGER / d).exists() for d in digests):
        raise FileExistsError('Duplicate/already attempted native in this new scope')
    f.write(BASE / 'approval_v01.json', {'cases': rows, 'maximum_model_attempts': 30, 'maximum_oauth_attempts': 30,
        'raw_user_request': 'Вот сприсок вопросов. Всё как всегда', 'scope_sha256': f.sha(SCOPE.read_bytes()),
        'remaining_allowance_after_closure': 0})
    return {'cases': len(rows), 'eligible_requests': len(digests), 'not_sent': len(rows) - len(digests)}


def send(case, policy):
    if (BASE / 'scope_closed_v01.json').exists():
        raise FileExistsError('Scope closed; resend forbidden')
    approval = read(BASE / 'approval_v01.json')
    if approval['scope_sha256'] != f.sha(SCOPE.read_bytes()):
        raise ValueError('Scope authorization drift')
    prepared = BASE / 'prepared_v01' / case['id']
    f.verify_manifest(prepared)
    c = read(prepared / 'contract.json')
    f.verify(c['input_bindings'])
    row = next(r for r in approval['cases'] if r['id'] == case['id'])
    if row['dispatch_allowed'] != c['dispatch_allowed'] or row['request_sha256'] != c['request_sha256']:
        raise ValueError('Sealed native identity drift')
    folder = BASE / 'live' / case['id']
    folder.mkdir(parents=True, exist_ok=False)
    if not c['dispatch_allowed']:
        result = {'status': c['preparation_status'], 'model_attempts': 0, 'oauth_attempts': 0}
        f.write(folder / 'result.json', result)
        f.manifest(folder)
        return result
    attempt = {'scope': str(SCOPE), 'scope_sha256': f.sha(SCOPE.read_bytes()), 'case_id': case['id'],
        'request_sha256': c['request_sha256'], 'maximum_model_attempts': 1, 'maximum_oauth_attempts': 1}
    with patch.object(f, 'LEDGER', LEDGER):
        slot = f.reserve(c['request_sha256'], attempt)
    f.write(folder / 'attempt.json', attempt)
    obs = Observation(folder, f.configure(), policy, expected=prepared, case=case)
    started = time.perf_counter()
    try:
        with patch.object(f, 'QUESTION', case['question']):
            response = run_route(obs, read(prepared / 'api_request.json'))
        f.write(folder / 'api_response.json', {'http_status': response.status_code, 'body': response.json()})
        body = response.json()
        obs.result.update(http_status=response.status_code,
                          status='runtime_api_result' if response.status_code == 200 else 'runtime_api_error',
                          delivery_status=body.get('delivery_status'))
        fixed_version()
        f.verify(c['input_bindings'])
        obs.result['postflight_hashes'] = 'verified'
    finally:
        if (folder / 'response.bin').exists():
            from app.generation.gigachat import _json
            try:
                native = _json((folder / 'response.bin').read_bytes())
            except (ValueError, UnicodeError) as exc:
                obs.result['native_metadata_parse_error'] = type(exc).__name__
            else:
                if isinstance(native, dict):
                    obs.result.update(returned_model=native.get('model'), usage=native.get('usage'))
        obs.result.update(elapsed_seconds=time.perf_counter() - started, allowance_closed=True, resend_authorized=False,
                          network_denials=policy.denied)
        f.write(folder / 'result.json', obs.result)
        f.write(slot / 'result.json', obs.result)
        f.write(slot / 'closed.json', {'allowance_closed': True, 'resend_authorized': False})
        f.manifest(folder)
    return {k: obs.result.get(k) for k in ('status', 'delivery_status', 'model_attempts', 'oauth_attempts', 'usage')}


def close():
    rows = []
    for cid in IDS:
        path = BASE / 'live' / cid / 'result.json'
        contract = BASE / 'prepared_v01' / cid / 'contract.json'
        digest = read(contract)['request_sha256'] if contract.exists() else None
        reserved = bool(digest and (LEDGER / digest).exists())
        missing = {'status': 'unknown_reserved' if reserved else 'not_dispatched',
                   'model_attempts': None if reserved else 0, 'oauth_attempts': None if reserved else 0}
        rows.append({'id': cid, **(read(path) if path.exists() else missing),
                     'allowance_closed': True, 'resend_authorized': False})
    f.write(BASE / 'scope_closed_v01.json', {'cases': rows, 'remaining_allowance': 0})
    return {'cases': len(rows), 'remaining_allowance': 0}


def batch(mode):
    settings, rows = f.configure(), []
    for case in cases():
        done = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'scripts.kondo_nambu_peng_transfer_20261110',
                               mode, '--case-id', case['id']], cwd=f.ROOT, capture_output=True, encoding='utf-8', check=False)
        folder = BASE / 'worker_logs' / case['id']
        folder.mkdir(parents=True, exist_ok=True)
        for name, value in (('stdout', done.stdout), ('stderr', done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, '[REDACTED]')
            f.save(folder / f'{mode}_{name}.txt', value.encode())
        row = {'id': case['id'], 'exit_code': done.returncode}
        if not done.returncode:
            row.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(row)
        print(json.dumps(row), flush=True)
        if done.returncode:
            break
    f.write(BASE / f'{mode}_batch_v01.json', {'cases': rows, 'finished_all': len(rows) == 30 and not rows[-1]['exit_code']})
    if mode == 'send':
        close()
    return {'stage': mode, 'finished_all': len(rows) == 30 and not rows[-1]['exit_code']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('init', 'prepare', 'prepare-all', 'seal', 'send', 'send-all', 'close'))
    parser.add_argument('--case-id', choices=IDS)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    guard = ReferenceReadGuard()
    if args.mode != 'init':
        sys.addaudithook(guard)
    if args.mode in {'prepare', 'send'} and args.case_id is None:
        parser.error('--case-id required')
    if args.mode == 'init':
        value = initialize()
    elif args.mode.endswith('-all'):
        value = batch(args.mode.removesuffix('-all'))
    elif args.mode == 'seal':
        value = seal()
    elif args.mode == 'close':
        value = close()
    else:
        case = next(c for c in cases() if c['id'] == args.case_id)
        value = prepare(case, policy, guard) if args.mode == 'prepare' else send(case, policy)
    if policy.denied or guard.denied:
        raise RuntimeError('Forbidden reference/network access')
    print(json.dumps(value), flush=True)
