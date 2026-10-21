"""Audit independent-pilot prerequisites or evaluate declared multi-record references offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.pilot_audit import audit_packet
from app.records.pilot_evaluation import evaluate_pilot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="Verify a historical source-only development packet")
    audit.add_argument("--packet", type=Path, required=True)
    audit.add_argument("--annotator-availability", choices=("unavailable", "not_declared"), default="not_declared")
    evaluation = commands.add_parser("evaluate", help="One-to-one exact reference agreement; not scientific admission")
    evaluation.add_argument("--reference", type=Path, required=True)
    evaluation.add_argument("--prediction", action="append", default=[], metavar="CASE=PATH")
    for command in (audit, evaluation):
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.command == "audit":
        report = audit_packet(args.packet, args.output_dir, annotator_availability=args.annotator_availability,
                              source_root=args.source_root)
    else:
        predictions = {}
        for entry in args.prediction:
            case, separator, path = entry.partition("=")
            if not separator or not case or not path or case in predictions:
                parser.error("Each --prediction must be a unique CASE=PATH")
            predictions[case] = Path(path)
        report = evaluate_pilot(args.reference, predictions, args.output_dir, source_root=args.source_root)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
