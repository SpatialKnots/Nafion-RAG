"""Export source-bound article development tasks without model inference or scientific admission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.article_scope import export_article_scope


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--screening", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    report = export_article_scope(args.packet, args.screening, args.output_dir, source_root=args.source_root)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
