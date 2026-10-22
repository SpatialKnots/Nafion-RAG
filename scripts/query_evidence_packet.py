"""Freeze, capture without generation, and export query evidence packet comparisons."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.evaluation.query_packet_run import capture, export, prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--associations-prepared', type=Path, default=Path('output/records_stage28_20261022/prepared_v01'))
    p.add_argument('--associations-run', type=Path, default=Path('output/records_stage28_20261022/live_v01'))
    c, e = sub.add_parser('capture'), sub.add_parser('export')
    for command in (p, c, e):
        command.add_argument('--output-dir', type=Path, required=True)
    for command in (c, e):
        command.add_argument('--prepared', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.associations_prepared, args.associations_run, args.output_dir)
    elif args.action == 'capture':
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        result = capture(args.prepared, args.output_dir)
    else:
        result = export(args.prepared, args.captured, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
