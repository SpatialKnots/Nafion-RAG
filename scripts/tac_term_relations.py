"""Generate an immutable experimental automatic relation sidecar; no user decisions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.terms.relations import build_relations, validate_relations
from scripts.tac_experiment import digest, validate_profiles, write_new
from scripts.tac_term_classification import validate_classification
from scripts.tac_term_contexts import validate_contexts, verify_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot', 'profiles', 'inventory', 'contexts', 'classification', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=Path('.'))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    raw = {name: getattr(args, name).read_bytes() for name in ('snapshot', 'profiles', 'inventory', 'contexts', 'classification')}
    data = {name: json.loads(value) for name, value in raw.items()}
    hashes = {name: digest(value) for name, value in raw.items()}
    validate_profiles(data['snapshot'], data['profiles'], hashes['snapshot'])
    validate_contexts(data['snapshot'], data['profiles'], data['inventory'], data['contexts'], hashes['inventory'])
    if data['contexts']['snapshot_sha256'] != hashes['snapshot'] or data['contexts']['profiles_sha256'] != hashes['profiles']:
        raise ValueError('Relation pilot frozen input mismatch')
    validate_classification(data['contexts'], data['classification'], hashes['contexts'])
    verify_pdfs(data['snapshot'], args.source_root)
    bindings = dict(hashes, algorithm=digest((Path(__file__).resolve().parents[1] / 'app/terms/relations.py').read_bytes()))
    result = build_relations(data['contexts'], data['classification'], bindings)
    validate_relations(data['contexts'], data['classification'], result, bindings)
    write_new(args.output, result)
    print(json.dumps({'documents': len(result['articles']), 'sha256': digest(args.output.read_bytes()),
                      'relations': sum(len(a['relations']) for a in result['articles']),
                      'proposed': sum(r['state'] == 'proposed' for a in result['articles'] for r in a['relations'])}))


if __name__ == '__main__':
    main()
