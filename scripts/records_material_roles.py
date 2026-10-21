"""Export separate source-label material/environment role proposals; no inference or candidate changes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.material_roles_export import export_material_roles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=Path("output/records_stage23_20261021/run_v01"))
    parser.add_argument("--windows", type=Path, default=Path("output/records_stage19_20261021/run_v01"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(export_material_roles(args.parent, args.windows, args.output_dir, source_root=args.source_root), ensure_ascii=False))


if __name__ == "__main__":
    main()
