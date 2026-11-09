"""Constructed labelled roles plus an unchanged real unresolved case."""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from pathlib import Path

from app.generation.providers import Evidence
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE

QUESTION = ("Каков состав разработанного Smith и Jones (2021) электролита с фторированным эфиром и карбонатами "
            "и какие результаты циклирования были получены с ним в ячейках Li‖FePO₄ и Li‖Ag?")
ARTICLE = "00000000-0000-0000-0000-000000000001"
TEXTS = [
    "Smith and Jones 2021\nABSTRACT:\nElectrolyte MIX-A.\nA fluorinated ether and carbonate electrolyte contains "
    "0.6 M LiBF4 in ABC/dimethyl carbonate/DEF (2:3:4 by volume). We added 0.1 M lithium difluoro(oxalato)borate "
    "as a film-forming additive, so that a new bifunctional electrolyte of 0.7 M has been obtained.\n\nKEYWORDS: control.",
    "3. RESULTS\nElectrolyte MIX-A.\nThe electrolyte enables Li||FePO4 batteries to maintain nearly 71% capacity "
    "after 43 cycles when charged to 3.2 V under the current density of 3 mA g−1.\n",
    "4. CONCLUSION\nElectrolyte MIX-A.\nLi||Ag half-cells maintain about 83% coulombic efficiency after being "
    "charged/discharged 29 times under 4 mA cm−2 current density and 2 mAh cm−2 lithium deposition amount per cycle.\n",
]


def build() -> dict:
    sources = [asdict(Evidence(f"E{i}", ARTICLE, f"constructed-{i}", "Constructed assembly control", None, i, i,
                              "main_text", text, 0.8, "constructed", {}, {})) for i, text in enumerate(TEXTS, 1)]
    original = {"id": "complete", "question": QUESTION, "sources": sources,
                "reference": {"resolved": True, "article_id": ARTICLE},
                "layers": {e["chunk_id"]: "original" for e in sources}, "expected_complete": True, "origin": "constructed"}
    controls = [original]
    mutations = [
        ("different_label", 2, "MIX-A", "MIX-B"),
        ("missing_marker", 2, "Electrolyte MIX-A.\n", ""),
        ("different_cell", 2, "Li||Ag", "Li||Cu"),
        ("missing_duration", 2, "29 times", "unknown times"),
        ("future", 2, "half-cells maintain", "half-cells will maintain"),
        ("negation", 2, "half-cells maintain", "half-cells do not maintain"),
        ("prior_work", 2, "Li||Ag", "Previous work reported that Li||Ag"),
        ("other_sample", 2, "Li||Ag", "For another sample, Li||Ag"),
        ("wrong_current_unit", 2, "mA cm−2", "mA g−1"),
        ("inconsistent_composition", 0, "0.7 M", "0.8 M"),
        ("wrong_author", 0, "Smith and Jones", "Smith and Brown"),
        ("missing_identity", 0, "Smith and Jones 2021", ""),
        ("paragraph_break", 2, "Li||Ag", "\n\nLi||Ag"),
    ]
    for label, index, before, after in mutations:
        case = copy.deepcopy(original)
        case.update(id=label, expected_complete=False)
        case["sources"][index]["text"] = case["sources"][index]["text"].replace(before, after)
        controls.append(case)
    for kind in ("different_work", "different_layer", "different_type", "unresolved_reference", "unsupported_query",
                 "conflicting_value", "conflicting_label", "duplicate_parent"):
        case = copy.deepcopy(original)
        case.update(id=kind, expected_complete=kind == "duplicate_parent")
        if kind == "different_work":
            case["sources"][2]["article_id"] = "00000000-0000-0000-0000-000000000002"
        elif kind == "different_layer":
            case["layers"][sources[2]["chunk_id"]] = "ocr"
        elif kind == "different_type":
            case["sources"][2]["source_type"] = "other"
        elif kind == "unresolved_reference":
            case["reference"]["resolved"] = False
        elif kind == "unsupported_query":
            case["question"] += " при температуре 17 градусов"
        else:
            extra = copy.deepcopy(sources[2])
            extra.update(chunk_id="constructed-4", citation_id="E4")
            extra["text"] = extra["text"].replace("83%", "84%") if kind == "conflicting_value" else extra["text"]
            extra["text"] = extra["text"].replace("MIX-A", "MIX-B") if kind == "conflicting_label" else extra["text"]
            case["sources"].append(extra)
            case["layers"][extra["chunk_id"]] = "original"
        controls.append(case)
    corpus = read(CORPUS_BASE / "Q01/corpus.json")
    real_ids = ("5289509d-77cc-40a1-b3a2-f450d52b4457", "ce11b3ba-76fa-421f-b023-1f2aa033d7e4",
                "32bf43d3-f0cf-4dac-9ca0-ee0cba730301")
    real_sources = [asdict(Evidence(f"E{i}", r["article_id"], r["chunk_id"], r["title"], r["doi"],
                      r["page_start"], r["page_end"], r["source_type"], r["full_text"], 0, "real_frozen_control", {}, {}))
                    for i, r in enumerate((corpus[k] for k in real_ids), 1)]
    current = read(files.ROOT / "output/natural_source_grammar_20261109/compare_v01/service/Q01_current.json")
    question = current["trace"]["retrieval"]["query"]
    real = {"id": "real_Lin_explicit_label_missing", "question": question, "sources": real_sources,
            "reference": {"resolved": True, "article_id": real_sources[0]["article_id"]},
            "layers": {k: corpus[k]["text_layer"] for k in real_ids}, "expected_complete": False,
            "origin": "unchanged_exposed_real_sources_not_independent_gold"}
    return {"constructed": controls, "real": real}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    files.write(args.output, build())


if __name__ == "__main__":
    main()
