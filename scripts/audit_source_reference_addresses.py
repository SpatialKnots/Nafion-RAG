"""Audit inherited near-span addresses against actual frozen evidence texts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402

PACKET = ROOT / "docs/records/source_reference_cases_v0.5.json"
PREVIOUS = ROOT / "output/component_context_relation_20261103/review_v04/report.json"


def audit() -> dict[str, Any]:
    packet, report = json.loads(PACKET.read_bytes()), json.loads(PREVIOUS.read_bytes())
    files.verify(packet["bindings"])
    index = {(r["case_id"], r["arm"], r["window_qualifier"]): r for r in report["records"]}
    rows = []
    for parent in packet["parents"]:
        contexts = [c for c in packet["context_cases"] if c["parent_sha256"] == parent["parent_sha256"]]
        for address in parent["addresses"]:
            row = index[address["case_id"], address["arm"], address["window_qualifier"]]
            source = row["full_evidence"][address["evidence_index"]]
            raw = source["text"]
            checks = []
            for context in contexts:
                text = context["raw_span"]["text"]
                start = raw.find(text)
                checks.append({"context_id": context["id"], "present": start >= 0,
                               "span": {"start": start, "end": start + len(text), "text": text} if start >= 0 else None})
            rows.append({"inherited_address": address, "actual_provenance": {k: v for k, v in source.items() if k != "text"},
                         "declared_parent_sha256": parent["parent_sha256"], "actual_text_sha256": files.sha(raw.encode()),
                         "full_parent_identical": files.sha(raw.encode()) == parent["parent_sha256"], "context_checks": checks})
    return {
        "version": "source_reference_address_audit_v0.5",
        "basis": "inherited addresses describe old near-span observations; full-parent/context identity checked separately",
        "rows": rows, "addresses": len(rows), "same_parent": sum(r["full_parent_identical"] for r in rows),
        "different_parent": sum(not r["full_parent_identical"] for r in rows),
        "context_address_checks": sum(len(r["context_checks"]) for r in rows),
        "context_present": sum(c["present"] for r in rows for c in r["context_checks"]),
        "context_absent": sum(not c["present"] for r in rows for c in r["context_checks"]),
        "bindings": files.bindings([Path(__file__), PACKET, PREVIOUS]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    files.write(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"rows", "bindings"}}, ensure_ascii=False, indent=2))
