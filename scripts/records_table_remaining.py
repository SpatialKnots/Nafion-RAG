"""Prepare/run the separately frozen remaining 23 numeric source cells."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.records.table_remaining import prepare_remaining, run_remaining


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--parent-prepared", type=Path, required=True)
    prepare.add_argument("--parent-run", type=Path, required=True)
    prepare.add_argument("--source-root", type=Path, default=Path("."))
    run = commands.add_parser("run")
    run.add_argument("--prepared", type=Path, required=True)
    for command in (prepare, run):
        command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_remaining(args.parent_prepared, args.parent_run, args.output_dir, source_root=args.source_root)
    else:
        from dotenv import dotenv_values

        config = dotenv_values(".env")
        key = (os.getenv("OPENAI_API_KEY") or os.getenv("RAG_OPENAI_API_KEY")
               or config.get("OPENAI_API_KEY") or config.get("RAG_OPENAI_API_KEY") or "")
        report = run_remaining(args.prepared, args.output_dir, api_key=key)
        print(json.dumps(report["summary"], ensure_ascii=False))
        if report["summary"]["failed"] or report["final_source_integrity"]["status"] != "verified":
            raise SystemExit(1)
        return
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
