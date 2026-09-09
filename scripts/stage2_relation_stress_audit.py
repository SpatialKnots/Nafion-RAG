"""Audit synthetic counterexamples; these are not PDF evidence or acceptance gold.

Run from the repository root with ``python -m scripts.stage2_relation_stress_audit``.
The default run records disagreements without failing; --check exits 1 when any
scientific-support expectation disagrees with the adequacy heuristic.
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from app.generation.evidence_adequacy import assess_evidence_adequacy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("docs/evidence_relation_stress_cases.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--local-links-candidate", action="store_true",
                        help="Evaluate the rejected local-link veto offline; production decisions remain in actual.")
    args = parser.parse_args()
    raw = args.cases.read_bytes()
    fixture = json.loads(raw)
    if fixture["provenance"] != "synthetic_not_corpus_evidence":
        raise ValueError("This audit requires explicitly synthetic fixtures")
    records = []
    seen = set()
    for case in fixture["cases"]:
        if case["id"] in seen:
            raise ValueError(f"Duplicate case ID: {case['id']}")
        seen.add(case["id"])
        if type(case["expected_adequate"]) is not bool:
            raise ValueError(f"Expected a boolean label: {case['id']}")
        result = assess_evidence_adequacy(case["question"], [SimpleNamespace(text=t) for t in case["texts"]])
        evaluated = result.adequate
        if args.local_links_candidate:
            evaluated = evaluated and all(
                detail["local_link_candidate_indices"] for detail in result.relation_requirements["details"].values()
            )
        records.append({**case, "actual": asdict(result), "evaluated_adequate": evaluated,
                        "agrees": evaluated == case["expected_adequate"]})
    if not records:
        raise ValueError("No stress cases supplied")
    summary = {
        "total": len(records),
        "agreement": sum(r["agrees"] for r in records),
        "false_accepts": sum(r["evaluated_adequate"] and not r["expected_adequate"] for r in records),
        "false_refusals": sum(not r["evaluated_adequate"] and r["expected_adequate"] for r in records),
        "out_of_scope": sum(not r["actual"]["relation_requirements"]["required"] for r in records),
    }
    report = {
        "provenance": fixture["provenance"],
        "mode": "lexical_adequacy_no_retrieval_no_generation",
        "decision_policy": "local_links_candidate" if args.local_links_candidate else "production",
        "cases_sha256": hashlib.sha256(raw).hexdigest(),
        "implementation_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [Path("app/generation/evidence_adequacy.py"),
                         Path("app/generation/relation_requirements.py"), Path("app/generation/required_concepts.py")]
        },
        "summary": summary,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    if args.check and summary["agreement"] != summary["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
