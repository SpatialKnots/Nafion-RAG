"""Prepare and run the offline frozen RU/EN source-scope comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.condition_multilingual_export import prepare_comparison, run_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--baseline', type=Path, default=Path('output/records_stage26_20261021/run_v01'))
    prepare.add_argument('--source-root', type=Path, default=Path('.'))
    prepare.add_argument('--output-dir', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('--prepared', type=Path, required=True)
    run.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = (prepare_comparison(args.baseline, args.output_dir, source_root=args.source_root) if args.action == 'prepare'
              else run_comparison(args.prepared, args.output_dir))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
