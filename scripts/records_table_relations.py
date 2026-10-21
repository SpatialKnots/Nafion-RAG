"""Export the complete frozen table history with source relation diagnostics, without inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.table_relations_export import export_relation_audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage22-prepared", type=Path, default=Path("output/records_stage22_20261021/prepared_v01"))
    for stage in (20, 21, 22):
        parser.add_argument(f"--stage{stage}-run", type=Path, default=Path(f"output/records_stage{stage}_20261021/live_v01"))
    parser.add_argument("--windows", type=Path, default=Path("output/records_stage19_20261021/run_v01"))
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = export_relation_audit(args.stage22_prepared, args.stage22_run, args.stage21_run, args.stage20_run,
                                   args.windows, args.output_dir, source_root=args.source_root)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
