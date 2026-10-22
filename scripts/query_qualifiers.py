"""Freeze and compare explicit query qualifier coverage without retrieval or generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.query_qualifiers_run import export, prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--packets-prepared', type=Path, default=Path('output/records_stage29_20261022/prepared_v01'))
    p.add_argument('--captured', type=Path, default=Path('output/records_stage29_20261022/capture_v02'))
    e = sub.add_parser('export')
    e.add_argument('--prepared', type=Path, required=True)
    for command in (p, e):
        command.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.packets_prepared, args.captured, args.output_dir) if args.action == 'prepare' else export(
        args.prepared, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
