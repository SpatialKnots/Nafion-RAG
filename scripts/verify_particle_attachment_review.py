"""Verify atomic source anchors and unchanged v0.6 results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts import particle_attachment_audit as v7  # noqa: E402
from scripts import source_reference_chains_v06 as v6  # noqa: E402
from scripts.verify_cross_lingual_relation_review import check_span  # noqa: E402
from scripts.verify_source_reference_review_v06 import check_chains  # noqa: E402
from scripts.verify_typed_partial_relation_review import verify as verify_structure  # noqa: E402

ATOMIC_FIELDS = {"atomic_sources", "particle_relations", "particle_requirements_met", "exact_particle_groups"}


def base_result(analysis: dict[str, Any]) -> dict[str, Any]:
    return {**{k: v for k, v in analysis.items() if k not in ATOMIC_FIELDS}, "version": v6.VERSION}


def check_atoms(question: str, analysis: dict[str, Any], sources: list[dict[str, Any]]) -> int:
    check_chains(question, base_result(analysis), sources)
    count = 0

    def walk(value: Any, raw: str) -> None:
        nonlocal count
        if isinstance(value, dict):
            if {"start", "end", "text"} <= value.keys():
                check_span(raw, value)
                count += 1
            for key, item in value.items():
                if key in {"scientific_admission", "chemical_identity_established", "performed_established",
                           "material_owner_established", "value_owner_established", "owner_established"} and item:
                    raise ValueError("Atomic audit invented a scientific owner/admission")
                walk(item, raw)
        elif isinstance(value, list):
            for item in value:
                walk(item, raw)

    for source in analysis["atomic_sources"]:
        walk(source, sources[source["evidence_index"]]["text"])
    if analysis != v7.audit(question, sources, baseline_adequate=analysis["baseline_adequate"]):
        raise ValueError("Exact atomic replay differs")
    return count


def verify(folder: Path, junit: Path) -> dict[str, Any]:
    qa = verify_structure(folder, junit)
    report = json.loads((folder / "report.json").read_bytes())
    count = 0
    for row in report["records"]:
        count += check_atoms(row["question"], row["analysis"], row["full_evidence"] or [])
    for row in [*report["atomic_controls"], *report["real_atomic_records"], *report["older_control_replays"]]:
        count += check_atoms(row["question"], row["analysis"], row["sources"])
    packet = json.loads((ROOT / "docs/records/particle_attachment_cases_v0.7.json").read_bytes())
    files.verify(packet["bindings"])
    import fitz

    for case in packet["cases"]:
        check_span(case["page_text"], case["raw_span"])
        with fitz.open(case["provenance"]["original_pdf_path"]) as pdf:
            raw = pdf[case["provenance"]["pdf_page"] - 1].get_text()
        if files.sha(raw.encode()) != case["page_text_sha256"] or case["raw_span"]["text"] not in raw:
            raise ValueError("Fresh atomic source window differs")
    prior = json.loads((ROOT / "docs/records/source_reference_cases_v0.5.json").read_bytes())
    files.verify(prior["bindings"])
    articles = {a["article_id"]: a for a in report["articles"]}
    for case in prior["context_cases"]:
        source = case["provenance"]
        with fitz.open(articles[source["article_id"]]["original_pdf_path"]) as pdf:
            pages = [pdf[i - 1].get_text() for i in range(source["page_start"], source["page_end"] + 1)]
        if not any(case["raw_span"]["text"] in raw for raw in [*pages, "\n".join(pages), "\n\n".join(pages)]):
            raise ValueError("Fresh previous chain context differs")
    qa.update(atomic_raw_spans_verified=count, fresh_atomic_windows=len(packet["cases"]), exact_atomic_base_replay="passed",
              fresh_previous_chain_windows=len(prior["context_cases"]),
              bindings={**qa["bindings"], **files.bindings([Path(__file__)])})
    return qa


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.review, args.junit)
    files.write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
