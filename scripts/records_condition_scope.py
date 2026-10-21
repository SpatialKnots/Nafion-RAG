"""Export frozen preparation/conditioning/measurement source scopes without inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.condition_scope_export import export_condition_scope


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, default=Path('output/records_stage24_20261021/run_v01'))
    parser.add_argument('--relations', type=Path, default=Path('output/records_stage23_20261021/run_v01'))
    parser.add_argument('--windows', type=Path, default=Path('output/records_stage19_20261021/run_v01'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=Path('.'))
    args = parser.parse_args()
    print(json.dumps(export_condition_scope(args.parent, args.relations, args.windows, args.output_dir,
                                           source_root=args.source_root), ensure_ascii=False))


if __name__ == '__main__':
    main()
