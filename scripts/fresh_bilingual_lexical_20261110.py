"""Two explicit read-only experimental API preflights, stopped before external transport."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import bilingual_lexical_admission_20261110 as run
from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as transfer


def main(cid, policy):
    settings = f.configure()
    comparison = run.BASE / 'comparison_v03'
    f.verify_manifest(comparison)
    f.verify(run.read(comparison / 'bindings.json'))
    case = next(c for c in run.read(run.QUESTIONS)['cases'] if c['id'] == cid)
    folder = run.BASE / 'fresh_api_v01' / cid
    folder.mkdir(parents=True, exist_ok=False)
    api = run.read(run.PARENT / cid / 'api_request.json')
    observation = transfer.Observation(folder, settings, policy, case=case)
    reached = False
    with patch.object(f, 'QUESTION', case['question']):
        try:
            response = transfer.run_route(observation, api)
            f.write(folder / 'unexpected_api_response.json', {'status': response.status_code, 'body': response.json()})
        except f.PreparedBoundary:
            reached = True
    expected = run.read(comparison / cid / 'after.json')['trace']
    if (not reached or observation.trace != expected or not observation.scope_ok or observation.readonly != 'on'
            or observation.body != (comparison / cid / 'request_unsent.json').read_bytes() or policy.denied):
        raise ValueError('Fresh API/source/native preparation differs from frozen comparison: ' + cid)
    f.verify(run.read(comparison / 'bindings.json'))
    result = {'id': cid, 'fresh_API_preparation': True, 'all_selected_match': True,
        'trace_exact_frozen_comparison': True, 'native_exact_frozen_comparison': True,
        'native_bytes': len(observation.body), 'native_sha256': f.sha(observation.body),
        'transaction_read_only': observation.readonly, 'transaction_end': 'rollback',
        'network_denials': policy.denied, 'model_POSTs': 0, 'OAuth_exchanges': 0,
        'new_slots': 0, 'send_authorized': False, 'scientific_accuracy': None}
    f.write(folder / 'result.json', result)
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), comparison / 'manifest.json', run.QUESTIONS]))
    f.manifest(folder)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('Nambu_02', 'Nambu_04'), required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main(args.case, policy)
