"""Read-only API checks of recovered source context; no external transport permitted."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as transfer
from scripts import refusal_groups_20261110 as capture

IDS = ('Kondo_08', 'Nambu_09')


def check(cid, policy):
    settings = f.configure()
    comparison = capture.BASE / 'comparison_v01'
    f.verify_manifest(comparison)
    f.verify(capture.read(comparison / 'bindings.json'))
    case = next(r['case'] for r in capture.read(capture.BASE / 'capture_v01/cases.json') if r['case']['id'] == cid)
    folder = capture.BASE / 'fresh_api_v01' / cid
    folder.mkdir(parents=True, exist_ok=False)
    api = capture.read(transfer.BASE / 'prepared_v01' / cid / 'api_request.json')
    observation = transfer.Observation(folder, settings, policy, case=case)
    with patch.object(f, 'QUESTION', case['question']):
        response = transfer.run_route(observation, api)
    current = capture.read(comparison / cid / 'after.json')
    f.write(folder / 'api_response.json', {'status': response.status_code, 'body': response.json()})
    if (response.status_code != 200 or observation.trace != current['trace'] or response.json()['answer'] != current['answer']
            or observation.body is not None or observation.readonly != 'on' or not observation.scope_ok or policy.denied):
        raise ValueError('Fresh real API/source recovery differs from frozen comparison: ' + cid)
    f.verify(capture.read(comparison / 'bindings.json'))
    result = {'id': cid, 'fresh_readonly_API_preparation': True, 'HTTP_status': response.status_code,
        'status': response.json()['answer']['status'], 'trace_and_body_exact': True,
        'selected_pages': sorted({p for e in observation.trace['evidence'] for p in range(e['page_start'], e['page_end'] + 1)}),
        'recovered': observation.trace['metadata']['retrieved_raw_preservation'],
        'transaction_read_only': observation.readonly, 'transaction_end': 'rollback',
        'model_calls': 0, 'oauth_calls': 0, 'new_slots': 0, 'network_denials': policy.denied}
    f.write(folder / 'result.json', result)
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json']))
    f.manifest(folder)
    print(json.dumps({k: v for k, v in result.items() if k != 'recovered'}))


def batch():
    settings, rows = f.configure(), []
    for cid in IDS:
        done = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'scripts.fresh_refusal_groups_20261110',
                               '--case', cid], cwd=f.ROOT, capture_output=True, encoding='utf-8')
        logs = capture.BASE / 'fresh_logs_v01' / cid
        logs.mkdir(parents=True, exist_ok=False)
        for name, value in (('stdout', done.stdout), ('stderr', done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, '[REDACTED]')
            f.save(logs / (name + '.txt'), value.encode())
        if done.returncode:
            raise RuntimeError('Fresh source recovery preflight failed; see saved logs: ' + cid)
        rows.append(capture.read(capture.BASE / 'fresh_api_v01' / cid / 'result.json'))
    f.write(capture.BASE / 'fresh_api_v01/batch.json', rows)
    print(json.dumps({'fresh_API_preparations': len(rows), 'all_HTTP200': True, 'model_calls': 0, 'oauth_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=IDS)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    batch() if args.case is None else check(args.case, policy)
