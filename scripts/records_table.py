"""Export saved full-record proposals, exact evidence and automatic checks offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.table_export import export_table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True, help="Declared scope; include zero-record bundles")
    parser.add_argument("--output-dir", type=Path, required=True, help="Fresh directory; refuses overwrite")
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    report = export_table(args.inputs, args.output_dir, source_root=args.source_root)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
