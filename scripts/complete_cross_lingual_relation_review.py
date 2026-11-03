"""Expose exact near-relation failures without changing the frozen analyzer."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.run_cross_lingual_relation_audit import render  # noqa: E402


def complete(source: Path, output: Path) -> dict[str, Any]:
    files.verify_manifest(source)
    report = json.loads((source / "report.json").read_bytes())
    files.verify(report["bindings"])
    reason_counts: Counter[str] = Counter()
    near_count = 0
    for record in report["records"]:
        near = []
        for evidence in record["analysis"]["sources"]:
            raw = record["full_evidence"][evidence["evidence_index"]]
            for region in evidence["regions"]:
                reason_counts.update(region["diagnostics"])
                if not region["owner_links"] and not region["relation_links"]:
                    continue
                if raw["text"][region["span"]["start"] : region["span"]["end"]] != region["span"]["text"]:
                    raise ValueError("Near-relation raw anchor differs")
                near.append(
                    {
                        "evidence_index": evidence["evidence_index"],
                        "provenance": {
                            key: raw[key] for key in ("article_id", "chunk_id", "title", "doi", "page_start", "page_end", "source_type")
                        },
                        "raw_span": region["span"],
                        "missing_roles": region["missing_roles"],
                        "status": region["status"],
                        "diagnostics": region["diagnostics"],
                        "scientific_admission": False,
                    }
                )
        if near:
            record["near_relation_failures"] = near
            near_count += len(near)
    summary = report["summary"]
    summary["diagnostic_findings"] = {
        "scope": "post-hoc failure inspection; repeated contexts counted separately; no new labels or analyzer changes",
        "near_relation_span_observations": near_count,
        "all_scoped_region_reason_counts": dict(reason_counts),
        "observed_gaps": [
            "An explicit Nafion particle morphology relation with a named water/2-propanol ratio "
            "lacks literal solvent and dispersion cues locally.",
            "The finite abbreviation list splits a real source statement after ca.; correcting this alone was not evaluated.",
            "48 constructed behavior checks do not establish coverage of real scientific prose.",
            "Zero candidate recovery prohibits treating this analyzer as a gate replacement or veto.",
        ],
    }
    summary["experiment_verified_bindings"] = summary["verified_bindings"]
    report["bindings"].update(files.bindings([Path(__file__), source / "manifest.json", source / "report.json"]))
    summary["verified_bindings"] = len(report["bindings"])
    files.verify(report["bindings"])
    report["presentation_amendment"] = "exact near-relation failure windows; original algorithm and all decisions unchanged"
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "source_snapshot"
    snapshot.mkdir()
    files.save(snapshot / Path(__file__).name, Path(__file__).read_bytes())
    files.write(output / "report.json", report)
    render(report, output)
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(complete(args.source, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
