"""Prepare, run or replay a bounded property/protocol/condition association comparison."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.records.protocol_association_run import export, prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--parent', type=Path, default=Path('output/records_stage27_20261022/run_v01'))
    for action in (p, sub.add_parser('run'), sub.add_parser('export')):
        action.add_argument('--output-dir', type=Path, required=True)
        if action != p:
            action.add_argument('--prepared', type=Path, required=True)
        if action.prog.endswith(' export'):
            action.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.parent, args.output_dir, source_root=Path.cwd())
    elif args.action == 'export':
        result = export(args.prepared, args.run_dir, args.output_dir)
    else:
        from dotenv import dotenv_values
        config = dotenv_values('.env')
        key = (os.getenv('OPENAI_API_KEY') or os.getenv('RAG_OPENAI_API_KEY')
               or config.get('OPENAI_API_KEY') or config.get('RAG_OPENAI_API_KEY') or '')
        result = run(args.prepared, args.output_dir, api_key=key)
    print(json.dumps(result, ensure_ascii=False))
    if result.get('statuses', {}).get('failed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
