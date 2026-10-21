"""Freeze and run an offline transfer probe of unchanged stage25 source-event rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.condition_transfer_export import prepare_transfer, run_transfer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--scope', type=Path, default=Path('output/records_stage18_20261021/run_v01'))
    prepare.add_argument('--windows', type=Path, default=Path('output/records_stage19_20261021/run_v01'))
    prepare.add_argument('--control', type=Path, default=Path('output/records_stage25_20261021/run_v02'))
    prepare.add_argument('--source-root', type=Path, default=Path('.'))
    prepare.add_argument('--output-dir', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('--prepared', type=Path, required=True)
    run.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = (prepare_transfer(args.scope, args.windows, args.control, args.output_dir, source_root=args.source_root)
              if args.action == 'prepare' else run_transfer(args.prepared, args.output_dir))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
