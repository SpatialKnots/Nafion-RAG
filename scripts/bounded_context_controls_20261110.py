"""Declared synthetic missing-CE controls; original full real packet is no-gap."""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from pathlib import Path

from app.generation.answer_evidence_packet import build_packet
from app.generation.answer_requirements import build_requirements
from app.generation.preparation_routes import PreparationRequest
from app.retrieval.search import SearchResult
from scripts import gigachat_answer_smoke as files
from scripts.answer_requirements_controls_20261109 import parent
from scripts.benchmark_retrieval_capture_20261105 import read


def inputs() -> list[dict]:
    data = read(files.ROOT / "output/source_role_assembly_20261109/controls_v01.json")["constructed"][0]
    base = copy.deepcopy(data)
    base["sources"] = base["sources"][:2]
    p = parent(base)
    scope = PreparationRequest(question=p["question"], collection="offline_fixture", method="exact",
                               answer_language="ru").model_dump(mode="json")
    e = data["sources"][2]
    candidate = asdict(SearchResult(e["article_id"], e["chunk_id"], e["title"], e["doi"], e["page_start"], e["page_end"],
        e["source_type"], e["text"], 0.0, "bounded_coulombic_context", full_text=e["text"], text_layer=data["layers"][e["chunk_id"]]))
    cases = [{"id": "missing_CE_unique", "parent": p, "request_scope": scope, "rows": [candidate], "expected_added": True}]
    for name, changes in (("wrong_work", {"article_id": "foreign"}), ("wrong_layer", {"text_layer": "ocr"}),
            ("wrong_type", {"source_type": "figure_caption"}), ("wrong_page", {"page_start": 4, "page_end": 4}),
            ("missing_raw", {"full_text": None})):
        cases.append({**copy.deepcopy(cases[0]), "id": name, "rows": [{**candidate, **changes}], "expected_added": False})
    for name, before, after in (("wrong_label", "MIX-A", "MIX-B"), ("wrong_cell", "Li||Ag", "Li||Cu"),
            ("wrong_unit", "4 mA cm−2", "4 mA cm−1"), ("future", "Electrolyte MIX-A.", "Electrolyte MIX-A.\nWe plan to report that"),
            ("negation", "Electrolyte MIX-A.", "Electrolyte MIX-A.\nWe did not observe that")):
        if before not in candidate["full_text"]:
            raise ValueError("Declared mutation absent: " + name)
        altered = {**candidate, "full_text": candidate["full_text"].replace(before, after)}
        altered["snippet"] = altered["full_text"]
        cases.append({**copy.deepcopy(cases[0]), "id": name, "rows": [altered], "expected_added": False})
    other = {**candidate, "chunk_id": "constructed-conflict", "full_text": candidate["full_text"].replace("83%", "81%")}
    other["snippet"] = other["full_text"]
    cases.append({**copy.deepcopy(cases[0]), "id": "conflicting_values", "rows": [candidate, other], "expected_added": False})
    duplicate = {**candidate, "chunk_id": "constructed-duplicate", "full_text": candidate["full_text"] + "\n"}
    cases.append({**copy.deepcopy(cases[0]), "id": "equivalent_duplicate", "rows": [duplicate, candidate], "expected_added": True})
    cases.append({**copy.deepcopy(cases[0]), "id": "empty_pool", "rows": [], "expected_added": False})
    cases.append({**copy.deepcopy(cases[0]), "id": "overflow", "rows": [candidate] * 13, "expected_added": False})
    return cases


def packet(case):
    p = copy.deepcopy(case["parent"])
    wrapper = {"version": "answer_requirements_preparation_v0.1", "preparation": p,
               "requirements": build_requirements(p, case["request_scope"]), "generation_performed": False,
               "external_request_constructed": False, "network_ready": False}
    return build_packet(wrapper)


def registry(source):
    return {"chunks": {source.chunk_id: {"article_id": source.article_id, "page_start": source.page_start,
        "page_end": source.page_end, "source_type": source.source_type, "text": source.text, "text_layer": "original"}},
        "chunk_layers": {source.chunk_id: "original"}, "pages": {}, "diagnostics": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files.write(args.output, inputs())


if __name__ == "__main__":
    main()
