"""Freeze or execute the diagnostic-only stage33 context-risk audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.context_risks_run import prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r = sub.add_parser('prepare'), sub.add_parser('run')
    p.add_argument('--parent', type=Path, default=Path('output/records_stage32_20261022/live_v01'))
    p.add_argument('--snapshot', type=Path, default=Path('output/records_stage32_20261022/baseline_final_v01'))
    r.add_argument('--prepared', type=Path, required=True)
    for command in (p, r):
        command.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.parent, args.snapshot, args.output_dir) if args.action == 'prepare' else run(args.prepared, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
