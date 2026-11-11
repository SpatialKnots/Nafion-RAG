"""Declared diagnostic inputs; synthetic preparations retain frozen raw parents."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read

BASE = files.ROOT / "output/answer_requirements_20261109"


def parent(case: dict) -> dict:
    """Synthetic preparation wrapper, not a new DB or production preparation."""
    return {"version": "answer_preparation_v0.1", "question": case["question"], "status": "blocked",
        "generation_performed": False, "external_request_constructed": False, "network_ready": False,
        "blocking_reasons": ["source_registry_unproven"], "baseline_allowed": False,
        "baseline_metadata": {"retrieval": {"explicit_source_reference": case["reference"]}},
        "evidence": copy.deepcopy(case["sources"]), "sources": {"chunks": {s["chunk_id"]: {
            "article_id": s["article_id"], "text_layer": case["layers"].get(s["chunk_id"]),
            "page_start": s["page_start"], "page_end": s["page_end"], "source_type": s["source_type"], "text": s["text"]}
            for s in case["sources"]}, "chunk_layers": copy.deepcopy(case["layers"]), "pages": {}, "diagnostics": []},
        "scope": {"page_registry_proven": False}, "scientific_admission": "not_evaluated"}


def build() -> list[dict]:
    data = read(files.ROOT / "output/source_role_assembly_20261109/controls_v01.json")
    real = read(files.ROOT / "output/methods_identity_bridge_20261109/controls_v02.json")[0]
    cases = [{"id": "exposed_real_full_packet", "origin": "synthetic_preparation_real_raw",
              "parent": parent(real), "expected_identity": "textual_contract_available"}]
    expected = {"complete": "textual_contract_available", "duplicate_parent": "textual_contract_available"}
    for case in data["constructed"]:
        cases.append({"id": case["id"], "origin": "constructed", "parent": parent(case),
                      "expected_identity": expected.get(case["id"], "identity_unresolved")})
    for name in ("cue_only", "no_cues", "missing_registry", "unsupported_query"):
        p = parent(real)
        if name in {"cue_only", "no_cues"}:
            for source in p["evidence"]:
                source["text"] = ("Electrolyte capacity and coulombic efficiency were discussed without an extracted numeric result."
                                  if name == "cue_only" else "Unrelated selected context.")
                p["sources"]["chunks"][source["chunk_id"]]["text"] = source["text"]
        elif name == "missing_registry":
            p["sources"]["chunks"] = {}
        else:
            p["question"] += " при температуре 17 градусов"
        cases.append({"id": name, "origin": "constructed", "parent": p, "expected_identity": "identity_unresolved"})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files.write(args.output, build())


if __name__ == "__main__":
    main()
