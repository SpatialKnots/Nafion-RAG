"""One fresh read-only API preparation; stop before any real transport or slot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as transfer
from scripts import peng_surface_20261111 as run


def main(policy, attempt):
    settings = f.configure()
    comparison = run.BASE / 'comparison_v01'
    f.verify_manifest(comparison)
    f.verify(run.read(comparison / 'bindings.json'))
    cid = 'Peng_10'
    case = next(r['case'] for r in run.read(run.previous.CAPTURE / 'cases.json') if r['case']['id'] == cid)
    out = run.BASE / f'fresh_api_v{attempt:02}' / cid
    out.mkdir(parents=True, exist_ok=False)
    api = run.read(comparison / cid / 'api_request.json')
    obs, reached = transfer.Observation(out, settings, policy, case=case), False
    with patch.object(f, 'QUESTION', case['question']):
        try:
            response = transfer.run_route(obs, api)
            f.write(out / 'unexpected_response.json', {'status': response.status_code, 'body': response.json()})
        except f.PreparedBoundary:
            reached = True
    expected = run.read(comparison / cid / 'after.json')['trace']
    if (not reached or obs.trace != expected or not obs.scope_ok or obs.readonly != 'on'
            or obs.body != (comparison / cid / 'request_unsent.json').read_bytes()
            or obs.sources['diagnostics'] or policy.denied):
        raise ValueError('Fresh order/source/native preparation differs')
    result = {'id': cid, 'trace_exact': True, 'native_exact': True, 'registry_diagnostics': obs.sources['diagnostics'],
        'native_bytes': len(obs.body), 'native_sha256': f.sha(obs.body), 'transaction_read_only': obs.readonly,
        'transaction_end': 'rollback', 'network_denials': policy.denied, 'real_model_calls': 0, 'real_oauth_calls': 0,
        'new_slots': 0, 'send_authorized': False, 'scientific_accuracy': None}
    f.verify(run.read(comparison / 'bindings.json'))
    f.write(out / 'result.json', result)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json']))
    f.manifest(out)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, choices=range(1, 10), default=1)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main(policy, args.attempt)
