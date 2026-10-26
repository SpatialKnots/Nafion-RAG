"""Freeze and review whole-unit query selection; never send a model request."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.query_context_selection_run import export, prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r, e = [sub.add_parser(name) for name in ('prepare', 'run', 'export')]
    p.add_argument('--parent', type=Path, default=Path('output/records_stage39_20261024/run_v01'))
    p.add_argument('--checks', type=Path, required=True)
    r.add_argument('--prepared', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    for command in (p, r, e):
        command.add_argument('--output-dir', type=Path, required=True)
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
