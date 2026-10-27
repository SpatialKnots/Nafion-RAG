"""Prepare/run/export source-origin diagnostics using local frozen files only."""

import argparse
import json
from pathlib import Path

from app.evaluation.source_origin_run import export, prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r, e = [sub.add_parser(n) for n in ('prepare', 'run', 'export')]
    p.add_argument('--parent', type=Path, default=Path('output/records_stage42_20261026/run_v01'))
    p.add_argument('--checks', type=Path, required=True)
    r.add_argument('--prepared', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    for cmd in (p, r, e):
        cmd.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.parent, args.checks, args.output_dir)
    elif args.action == 'run':
        result = run(args.prepared, args.output_dir)
    else:
        result = export(args.captured, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
