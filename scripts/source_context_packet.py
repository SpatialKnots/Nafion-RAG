"""Freeze, assemble and review source context without database/model requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.source_context_packet_run import export, prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r, e = [sub.add_parser(name) for name in ('prepare', 'run', 'export')]
    p.add_argument('--parent', type=Path, default=Path('output/records_stage34_20261022/live_v02'))
    p.add_argument('--archive', type=Path, default=Path('output/records_stage34_20261022/baseline_final_v01'))
    p.add_argument('--metadata', type=Path, default=Path('output/records_stage35_20261022/applied_v01'))
    p.add_argument('--challenges', type=Path, required=True)
    r.add_argument('--prepared', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    for command in (p, r, e):
        command.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.parent, args.archive, args.metadata, args.challenges, args.output_dir)
    elif args.action == 'run':
        result = run(args.prepared, args.output_dir)
    else:
        result = export(args.captured, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
