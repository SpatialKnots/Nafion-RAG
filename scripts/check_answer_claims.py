"""Compare explicit local assertions to a pinned evidence packet, without generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.generation.answer_evidence_packet import load_packet
from app.generation.claim_checks import build_checks, save_checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True, help="Separately trusted current requirement-preparation JSON")
    parser.add_argument("--claims", type=Path, required=True, help="Explicit structured claim list, not answer prose")
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--output", type=Path, required=True, help="New report file; existing files are never overwritten")
    args = parser.parse_args()
    parent, claims = json.loads(args.parent.read_bytes()), json.loads(args.claims.read_bytes())
    packet = load_packet(args.packet, parent, expected_packet_id=args.packet_id)
    report = build_checks(packet, parent, claims, expected_packet_id=args.packet_id)
    save_checks(args.output, report, packet, parent, claims, expected_packet_id=args.packet_id, expected_report_id=report["report_id"])
    print(json.dumps({"report_id": report["report_id"], "claims_checked": len(report["results"]),
                      "scientific_validity": report["scientific_validity"]}))


if __name__ == "__main__":
    main()
