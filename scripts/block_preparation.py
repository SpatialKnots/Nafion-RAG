"""Freeze, run and review the read-only whole-block preparation experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.block_run import export, prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r, e = sub.add_parser('prepare'), sub.add_parser('run'), sub.add_parser('export')
    p.add_argument('--parent', type=Path, default=Path('output/records_stage31_20261022/live_v01'))
    p.add_argument('--snapshot', type=Path, default=Path('output/records_stage31_20261022/baseline_final_v01'))
    p.add_argument('--cache-manifest', type=Path, default=Path('output/records_stage29_20261022/runtime_cache_preflight_v01.json'))
    for command in (p, r, e):
        command.add_argument('--output-dir', type=Path, required=True)
    for command in (r, e):
        command.add_argument('--prepared', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.parent, args.snapshot, args.cache_manifest, args.output_dir)
    elif args.action == 'run':
        result = run(args.prepared, args.output_dir)
    else:
        result = export(args.prepared, args.captured, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
