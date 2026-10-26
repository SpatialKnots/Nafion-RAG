"""Run local frozen sample-class experiments without inference or database calls."""

import argparse
import json
from pathlib import Path

from app.evaluation.sample_scope_run import execute, export, prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--parent', type=Path, default=Path('output/records_stage40_20261024/run_v01'))
    p.add_argument('--checks', type=Path, required=True)
    for name in ('audit', 'select', 'export-audit', 'export-selection'):
        command = commands.add_parser(name)
        command.add_argument('--source', type=Path, required=True)
        command.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.parent, args.checks, args.output_dir)
    elif args.action.startswith('export'):
        result = export(args.source, args.output_dir, select=args.action == 'export-selection')
    else:
        result = execute(args.source, args.output_dir, select=args.action == 'select')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
