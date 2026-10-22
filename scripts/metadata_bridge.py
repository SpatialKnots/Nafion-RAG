"""Freeze, preview and apply the existing TAC metadata extractor to a bounded scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.metadata.bridge_run import apply, export, prepare, run_preview


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p, r, a, e = [sub.add_parser(n) for n in ('prepare', 'preview', 'apply', 'export')]
    p.add_argument('--parent', type=Path, default=Path('output/records_stage34_20261022/live_v02'))
    p.add_argument('--archive', type=Path, default=Path('output/records_stage34_20261022/baseline_final_v01'))
    p.add_argument('--corpus', type=Path, default=Path('data/experiments/tac/20261012_v01/corpus.json'))
    p.add_argument('--profiles', type=Path, default=Path('data/experiments/tac/20261012_stage06/profiles_final.json'))
    for command in (p, r, a, e):
        command.add_argument('--output-dir', type=Path, required=True)
    for command in (r, a):
        command.add_argument('--prepared', type=Path, required=True)
    a.add_argument('--preview', type=Path, required=True)
    e.add_argument('--captured', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.parent, args.archive, args.corpus, args.profiles, args.output_dir)
    elif args.action == 'preview':
        result = run_preview(args.prepared, args.output_dir)
    elif args.action == 'apply':
        result = apply(args.prepared, args.preview, args.output_dir)
    else:
        result = export(args.captured, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
