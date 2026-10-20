"""Run or evaluate bounded full-record development proposals; no production writes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.extraction import run_extraction
from app.records.full_evaluation import evaluate_extractions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    infer = commands.add_parser("infer", help="One frozen source context and task; local model only")
    infer.add_argument("input", type=Path)
    infer.add_argument("--task-file", type=Path, required=True)
    infer.add_argument("--endpoint", default="http://127.0.0.1:18086")
    infer.add_argument("--model", required=True)
    infer.add_argument("--runtime-manifest", type=Path, required=True)
    infer.add_argument("--max-tokens", type=int, default=4096)
    infer.add_argument("--timeout-seconds", type=int, default=300)
    infer.add_argument("--seed", type=int, default=42)
    infer.add_argument("--wire-format", choices=("full", "compact"), default="full",
                       help="compact v0.1 requests five literal fields from exactly one source region")
    evaluate = commands.add_parser("evaluate", help="Reparse raw responses against a fixed development reference")
    evaluate.add_argument("--reference", type=Path, required=True)
    evaluate.add_argument("--run", action="append", default=[], metavar="CASE=PATH")
    for command in (infer, evaluate):
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.command == "infer":
        result = run_extraction(
            args.input, args.output_dir, task=args.task_file.read_text(encoding="utf-8"),
            endpoint=args.endpoint, model=args.model, runtime_manifest=args.runtime_manifest,
            source_root=args.source_root, max_tokens=args.max_tokens, timeout_seconds=args.timeout_seconds, seed=args.seed,
            wire_format=args.wire_format,
        )
        print(json.dumps(result, ensure_ascii=False))
        if result["status"] != "integrity_valid":
            raise SystemExit(1)
    else:
        runs = {}
        for item in args.run:
            case_id, separator, path = item.partition("=")
            if not separator or not case_id or not path or case_id in runs:
                parser.error("Each --run must be a unique CASE=PATH")
            runs[case_id] = Path(path)
        report = evaluate_extractions(args.reference, runs, args.output_dir, source_root=args.source_root)
        print(json.dumps(report["summary"], ensure_ascii=False))
        if report["summary"]["failed_or_missing_cases"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
