"""Freeze real development windows and separate constructed mutations."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.natural_source_grammar_20261109 import FREEZE, evidence
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE


def build() -> dict:
    files.verify_manifest(FREEZE)
    audit = read(FREEZE / "recipe_audit.json")
    corpus = read(CORPUS_BASE / "Q01/corpus.json")
    articles = read(CORPUS_BASE / "Q01/articles.json")
    new_ids = ("196589cc-d956-43d7-af92-82a55c33f517", "32bf43d3-f0cf-4dac-9ca0-ee0cba730301",
               "afe4cc69-bdfc-42b4-83c0-56013deb3276")
    natural = []
    for chunk in new_ids:
        row = corpus[chunk]
        start = row["full_text"].index("At the same time, it also makes")
        end = row["full_text"].index("per cycle.", start) + len("per cycle.")
        natural.append({"id": "natural_conclusion_" + chunk, "recipe": "coulombic", "source": asdict(evidence(row)),
                        "expected_complete": True, "expected_before": False,
                        "preliminary_annotation": "complete_explicit_CE_role_grammar_miss_not_independent_gold",
                        "raw_span": {"start": start, "end": end, "text": row["full_text"][start:end]}})
    for row in audit["rows"]:
        if row["recipe"] == "coulombic" and row["complete"]:
            natural.append({"id": "natural_legacy_" + row["source"]["chunk_id"], "recipe": "coulombic",
                            "source": asdict(evidence(row["source"])), "expected_complete": True, "expected_before": True,
                            "preliminary_annotation": "legacy_role_positive_not_independent_gold",
                            "raw_span": row["rendering"]["facts"][0]["support"]})
    for chunk, recipe, reason in (
        (new_ids[1], "capacity", "conclusion_capacity_clause_has_no_cycle_count"),
        ("1a6ebd67-86b8-4c06-bb24-83860c38ded3", "dispersion_method", "descriptive_conclusion_has_no_complete_preparation_chain"),
        ("2f76a7e0-3367-472d-a470-3f38e67d7e65", "coulombic", "different_cell_no_complete_areal_CE_conditions"),
        ("0961e1eb-fb9f-4751-a7ee-9b626a10eba3", "coulombic", "requirements_and_other_result_forms_outside_finite_role"),
    ):
        row = corpus[chunk]
        natural.append({"id": "natural_incomplete_" + recipe + "_" + chunk, "recipe": recipe,
                        "source": asdict(evidence(row)), "expected_complete": False, "expected_before": False,
                        "preliminary_annotation": reason, "raw_span": {"start": 0, "end": len(row["full_text"]),
                                                                                   "text": row["full_text"]}})
    original = natural[1]["raw_span"]["text"]
    # Mutations are constructed controls; only unchanged original is a real source.
    mutations = [
        ("negative_predicate", "makes", "does not make"),
        ("future", "makes", "will make"),
        ("missing_approximation", "or so", "exactly"),
        ("other_property", "coulombic eﬃciency", "capacity retention"),
        ("wrong_unit_current", "mA cm−2", "mA g−1"),
        ("wrong_unit_capacity", "mAh cm−2", "mAh g−1"),
        ("missing_cycles", "200 times", "unknown times"),
        ("wrong_operation", "lithium deposition", "lithium cleaning"),
        ("wrong_chemistry_case", "Li||Cu", "li||Cu"),
        ("intervening_operation", "current density and", "current density. Another sample was used with"),
        ("negative_value", "98%", "-98%"),
    ]
    controls = []
    for label, before, after in mutations:
        if before not in original:
            raise ValueError("Declared mutation surface absent: " + before)
        controls.append({"id": label, "text": original.replace(before, after), "expected_complete": False,
                         "origin": "constructed_mutation_of_exposed_real_conclusion"})
    for prefix in ("Hypothetically,", "We assume", "Previous work reported that", "For another sample,",
                   "It is not true that", "We planned"):
        controls.append({"id": "prefix_" + prefix, "text": prefix + " " + original, "expected_complete": False,
                         "origin": "constructed_mutation_of_exposed_real_conclusion"})
    controls.extend([
        {"id": "varied_values", "text": original.replace("98%", "87%").replace("200 times", "37 times")
                     .replace("1 mA cm−2", "2 mA cm−2").replace("1 mAh cm−2", "3 mAh cm−2"),
         "expected_complete": True, "origin": "constructed_varied_values"},
        {"id": "whitespace", "text": original.replace("\n", " "), "expected_complete": True,
         "origin": "constructed_whitespace_only"},
    ])
    pdf_bindings, pages, source_spans = {}, {}, []
    for case in natural:
        src = case["source"]
        article = articles[src["article_id"]]
        path = Path(article["original_pdf_path"])
        digest = files.sha(path.read_bytes())
        if digest != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        pdf_bindings[str(path)] = digest
        with fitz.open(path) as pdf:
            texts = []
            for number in range(src["page_start"], src["page_end"] + 1):
                raw = pdf[number - 1].get_text()
                pages[(str(path), number)] = {"path": str(path), "page": number, "sha256": files.sha(raw.encode())}
                texts.append(raw)
        matches = [(src["page_start"] + i, raw.index(case["raw_span"]["text"])) for i, raw in enumerate(texts)
                   if case["raw_span"]["text"] in raw]
        source_spans.append({"case_id": case["id"], "span_literal_in_fresh_pages": matches,
                             "note": "full chunk may span pages; original narrow CE spans must map exactly"})
        if case["id"].startswith(("natural_conclusion", "natural_legacy")) and not matches:
            raise ValueError("Narrow CE raw span absent from fresh original pages")
    return {"natural": natural, "constructed": controls, "original_CE_excerpt": original,
            "source_pdf_bindings": pdf_bindings, "fresh_pages": list(pages.values()), "fresh_spans": source_spans,
            "limitations": "assistant preliminary role labels, exposed corpus; repeated source spans are not independent positives"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files.write(args.output, build())


if __name__ == "__main__":
    main()
