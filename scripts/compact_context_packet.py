"""Freeze and review compact source JSON with full local diagnostics; no API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.compact_context_run import export, prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r, e = [sub.add_parser(name) for name in ('prepare', 'run', 'export')]
    p.add_argument('--parent', type=Path, default=Path('output/records_stage37_20261023/run_v02'))
    p.add_argument('--challenges', type=Path, default=Path('output/records_stage37_20261023/retention_challenges_v01.json'))
    r.add_argument('--prepared', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    for command in (p, r, e):
        command.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.parent, args.challenges, args.output_dir)
    elif args.action == 'run':
        result = run(args.prepared, args.output_dir)
    else:
        result = export(args.captured, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
