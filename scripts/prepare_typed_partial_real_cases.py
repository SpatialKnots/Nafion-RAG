"""Freeze all previous near-relation source windows; no candidate execution."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402

RECIPE = ROOT / "docs/records/typed_partial_real_recipe_v0.2.json"
SOURCE = ROOT / "output/cross_lingual_relation_20261102/review_v03"
ABBREVIATION = re.compile(r"\b(?:ca|wt|vol|fig|eq|no|мас|ос|рис|табл)\.\s*$", re.I)


def prepare(output: Path) -> dict[str, Any]:
    files.verify_manifest(SOURCE)
    report = json.loads((SOURCE / "report.json").read_bytes())
    files.verify(report["bindings"])
    recipe = json.loads(RECIPE.read_bytes())
    grouped: dict[str, Any] = {}
    for record in report["records"]:
        for near in record.get("near_relation_failures", []):
            span = near["raw_span"]
            digest = files.sha(span["text"].encode())
            source = record["full_evidence"][near["evidence_index"]]
            raw = source["text"]
            if raw[span["start"] : span["end"]] != span["text"]:
                raise ValueError("Historical source span differs")
            group = grouped.setdefault(
                digest,
                {
                    "old_span": span,
                    "parent_text": raw,
                    "parent_sha256": files.sha(raw.encode()),
                    "provenance": near["provenance"],
                    "addresses": [],
                },
            )
            group["addresses"].append(
                {
                    "case_id": record["case_id"],
                    "arm": record["arm"],
                    "window_qualifier": record["window_qualifier"],
                    "evidence_index": near["evidence_index"],
                    "provenance": near["provenance"],
                }
            )
    annotations = {row["sha256"]: row for row in recipe["annotations"]}
    if set(grouped) != set(annotations):
        raise ValueError("Frozen six-span recipe differs from previous observations")
    cases = []
    for digest, annotation in annotations.items():
        group = grouped[digest]
        span, raw = group["old_span"], group["parent_text"]
        start, end = span["start"], span["end"]
        if annotation.get("extend_ca_sentence"):
            if not span["text"].rstrip().endswith("ca."):
                raise ValueError("Expected the declared ca.-truncated span")
            for terminal in re.finditer(r"[.!?](?=\s|$)", raw[end:]):
                point = end + terminal.end()
                if not ABBREVIATION.search(raw[:point]):
                    end = point
                    break
            else:
                raise ValueError("No true next sentence terminal")
        cases.append(
            {
                "id": "real_" + digest[:12],
                "old_raw_text_sha256": digest,
                "annotation": annotation,
                "raw_span": {"start": start, "end": end, "text": raw[start:end]},
                **group,
            }
        )
    dataset = {
        "version": recipe["version"],
        "origin": recipe["origin"],
        "cases": cases,
        "bindings": files.bindings([Path(__file__), RECIPE, SOURCE / "manifest.json", SOURCE / "report.json"]),
    }
    files.write(output, dataset)
    return {
        "cases": len(cases),
        "source_addresses": sum(len(row["addresses"]) for row in cases),
        "positive_development_relations": sum(row["annotation"]["partial_relation"] for row in cases),
        "output": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
