"""Prepare or run the frozen four-case multi-record development smoke."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.records.multi_run import prepare_smoke, run_smoke


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Freeze exact source/request inputs without inference")
    prepare.add_argument("--windows", type=Path, required=True)
    prepare.add_argument("--source-root", type=Path, default=Path("."))
    run = commands.add_parser("run", help="At most four fixed HTTPS calls; stop at first failure")
    run.add_argument("--prepared", type=Path, required=True)
    for command in (prepare, run):
        command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_smoke(args.windows, args.output_dir, source_root=args.source_root)
    else:
        from dotenv import dotenv_values

        config = dotenv_values(".env")
        key = (os.getenv("OPENAI_API_KEY") or os.getenv("RAG_OPENAI_API_KEY")
               or config.get("OPENAI_API_KEY") or config.get("RAG_OPENAI_API_KEY") or "")
        result = run_smoke(args.prepared, args.output_dir, api_key=key)
        print(json.dumps(result["summary"], ensure_ascii=False))
        if result["summary"]["failed"] or result["final_source_integrity"]["status"] != "verified":
            raise SystemExit(1)
        return
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
