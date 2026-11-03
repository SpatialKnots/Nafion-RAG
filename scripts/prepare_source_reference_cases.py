"""Freeze exposed real reference contexts before executing a chain candidate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import cross_lingual_relation_audit as v1  # noqa: E402
from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import typed_partial_relations as v2  # noqa: E402

REFERENCE_PATTERN = (
    r"\b(?:(?:this|these|the\s+same)\s+(?:mixed\s+)?(?:solvent\s+(?:systems?|dispersions?|mixtures?)|mixtures?|dispersions?)"
    r"|(?:эта|этой|эту|эти|этих|этот|этого)\s+(?:смешанн\w*\s+)?"
    r"(?:смес\w*|дисперси\w*|систем\w*\s+растворител\w*))\b"
)
REAL = ROOT / "docs/records/typed_partial_real_cases_v0.2.json"
PREVIOUS = ROOT / "output/component_context_relation_20261103/review_v04/report.json"
LABELS = {
    "this mixed solvent system": {"binding": True, "complete": False, "basis": "explicit context association; particles unresolved"},
    "these mixed solvent dispersions": {"binding": False, "complete": False, "basis": "possible-model statement; uncertainty"},
}


def prepare(output: Path) -> dict[str, Any]:
    old = json.loads(REAL.read_bytes())
    files.verify(old["bindings"])
    report = json.loads(PREVIOUS.read_bytes())
    articles = {row["article_id"]: row for row in report["articles"]}
    parents, cases = {}, []
    for case in old["cases"]:
        raw = case["parent_text"]
        if files.sha(raw.encode()) != case["parent_sha256"]:
            raise ValueError("Old parent hash differs")
        span = case["raw_span"]
        if raw[span["start"]:span["end"]] != span["text"]:
            raise ValueError("Old raw window differs")
        group = parents.setdefault(case["parent_sha256"], {
            "text": raw, "parent_sha256": case["parent_sha256"], "old_case_ids": [], "addresses": [],
            "provenance": case["provenance"],
        })
        group["old_case_ids"].append(case["id"])
        group["addresses"].extend(case["addresses"])
    for digest, parent in parents.items():
        view = v1.matching_view(parent["text"])
        regions = v2.regions(view.text)
        for match in re.finditer(REFERENCE_PATTERN, view.text, re.I):
            surface = re.sub(r"\s+", " ", match.group()).casefold()
            if surface not in LABELS:
                raise ValueError("Finite real reference inventory changed: " + surface)
            index = next(i for i, (a, b) in enumerate(regions) if a <= match.start() < match.end() <= b)
            a = regions[max(0, index - 1)][0]
            b = regions[min(len(regions) - 1, index + 1)][1]
            span = view.anchor(a, b)
            cases.append({
                "id": "context_" + files.sha(span["text"].encode())[:12],
                "parent_sha256": digest, "raw_span": span,
                "reference_span": view.anchor(match.start(), match.end()), "annotation": LABELS[surface],
                "provenance": parent["provenance"], "addresses": parent["addresses"],
                "old_case_ids": parent["old_case_ids"],
            })
    if len(parents) != 3 or len(cases) != 2 or len(old["cases"]) != 6:
        raise ValueError("Frozen real context inventory changed")
    import fitz

    fresh = []
    for case in [*old["cases"], *cases]:
        source = case["provenance"]
        article = articles[source["article_id"]]
        with fitz.open(article["original_pdf_path"]) as pdf:
            pages = [pdf[i - 1].get_text() for i in range(source["page_start"], source["page_end"] + 1)]
        if not any(case["raw_span"]["text"] in raw for raw in [*pages, "\n".join(pages), "\n\n".join(pages)]):
            raise ValueError("Fresh real context differs: " + case["id"])
        fresh.append(case["id"])
    value = {
        "version": "source_reference_cases_v0.5", "origin": "assistant exposed development source labels, not independent gold",
        "parents": list(parents.values()), "old_cases": old["cases"], "context_cases": cases,
        "fresh_windows_verified": fresh,
        "bindings": files.bindings([Path(__file__), REAL, PREVIOUS,
                                     ROOT / "docs/records/source_reference_chain_protocol_v0.5.md"]),
    }
    files.write(output, value)
    return {"old_windows": 6, "distinct_parents": len(parents), "new_context_windows": len(cases),
            "old_source_addresses": sum(len(p["addresses"]) for p in parents.values()), "fresh_windows": len(fresh)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))
