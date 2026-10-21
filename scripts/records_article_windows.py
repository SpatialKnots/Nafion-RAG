"""Plan complete article-scope bounded source contexts offline; no model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.article_windows import MAX_CONTEXT_CHARS, export_article_windows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--max-context-characters", type=int, default=MAX_CONTEXT_CHARS)
    args = parser.parse_args()
    report = export_article_windows(args.scope, args.output_dir, source_root=args.source_root,
                                    max_chars=args.max_context_characters)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
