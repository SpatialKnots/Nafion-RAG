"""Two fresh read-only API preparations with no real provider dispatch."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as transfer
from scripts import peng_glyph_binding_20261111 as run

IDS = ('Peng_05', 'Peng_08')


def check(cid, policy):
    settings = f.configure()
    comparison = run.BASE / 'comparison_v02'
    f.verify_manifest(comparison)
    f.verify(run.read(comparison / 'bindings.json'))
    case = next(r['case'] for r in run.read(run.old_run.CAPTURE / 'cases.json') if r['case']['id'] == cid)
    folder = run.BASE / 'fresh_api_v02' / cid
    folder.mkdir(parents=True, exist_ok=False)
    api = run.read(comparison / cid / 'api_request.json')
    obs, reached = transfer.Observation(folder, settings, policy, case=case), False
    with patch.object(f, 'QUESTION', case['question']):
        try:
            response = transfer.run_route(obs, api)
            f.write(folder / 'unexpected_response.json', {'status': response.status_code, 'body': response.json()})
        except f.PreparedBoundary:
            reached = True
    expected = run.read(comparison / cid / 'after.json')['trace']
    if (not reached or obs.trace != expected or not obs.scope_ok or obs.readonly != 'on'
            or obs.body != (comparison / cid / 'request_unsent.json').read_bytes()
            or obs.sources['diagnostics'] or policy.denied):
        raise ValueError('Fresh glyph/source/native preparation differs: ' + cid)
    f.verify(run.read(comparison / 'bindings.json'))
    result = {'id': cid, 'fresh_API_preparation': True, 'trace_exact': True, 'native_exact': True,
        'registry_diagnostics': obs.sources['diagnostics'], 'native_bytes': len(obs.body), 'native_sha256': f.sha(obs.body),
        'transaction_read_only': obs.readonly, 'transaction_end': 'rollback', 'network_denials': policy.denied,
        'model_calls': 0, 'oauth_calls': 0, 'new_slots': 0, 'send_authorized': False, 'accuracy': None}
    f.write(folder / 'result.json', result)
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json']))
    f.manifest(folder)
    print(json.dumps(result))


def batch():
    settings, rows = f.configure(), []
    for cid in IDS:
        done = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'scripts.fresh_peng_glyph_binding_20261111',
                               '--case', cid], cwd=f.ROOT, capture_output=True, encoding='utf-8')
        logs = run.BASE / 'fresh_logs_v02' / cid
        logs.mkdir(parents=True, exist_ok=False)
        for name, value in (('stdout', done.stdout), ('stderr', done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, '[REDACTED]')
            f.save(logs / (name + '.txt'), value.encode())
        if done.returncode:
            raise RuntimeError('Fresh API preparation failed; see saved logs: ' + cid)
        rows.append(run.read(run.BASE / 'fresh_api_v02' / cid / 'result.json'))
    f.write(run.BASE / 'fresh_api_v02/batch.json', rows)
    print(json.dumps({'fresh_API_preparations': len(rows), 'model_calls': 0, 'oauth_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=IDS)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    batch() if args.case is None else check(args.case, policy)
