"""Immutable real inputs plus separately marked artificial bridge mutations."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read


def build() -> list[dict]:
    real = read(files.ROOT / "output/source_role_assembly_20261109/controls_v01.json")["real"]
    real = {**real, "id": "real_unchanged", "expected_candidate": True}
    cases = [real]
    mutations = [
        ("wrong_salt", 1, "1.2\nM LiPF6", "1.2\nM LiBF4"),
        ("molality", 1, "1.2\nM LiPF6", "1.2\nm LiPF6"),
        ("wrong_solvent", 1, "FEC/DMC/HFE", "FEC/DMC/XYZ"),
        ("wrong_volume_ratio", 1, "1:1:1 by volume", "1:1:2 by volume"),
        ("wrong_ratio_basis", 1, "by volume", "by mass"),
        ("wrong_DMC_alias", 1, "carbonate (DMC)", "carbonate (ZZZ)"),
        ("wrong_additive_alias", 0, "borate (LiDFOB)", "borate (LiBOB)"),
        ("wrong_additive", 1, "LiDFOB", "LiBOB"),
        ("wrong_base", 1, "separately added to FDH-1.2M-LiPF6", "separately added to FD-1.2M-LiPF6"),
        ("dose_only_swap", 1, "0.05, 0.15, and 0.3", "0.15, 0.05, and 0.3"),
        ("product_only_swap", 1, "FDH-1.25M-LiPD,\nFDH-1.35M-LiPD", "FDH-1.35M-LiPD,\nFDH-1.25M-LiPD"),
        ("missing_respectively", 1, "respectively.", "in a different order."),
        ("missing_separately", 1, "were\nseparately added", "were\nadded"),
        ("missing_section", 1, "2.1. Material Preparation.", "2.1. Planned Preparation."),
        ("missing_boundary", 1, "2.2. Material Characterization.", "Further characterization."),
        ("foreign_context", 1, "In addition, 0.05", "Previous work reported that In addition, 0.05"),
        ("planned_context", 1, "In addition, 0.05", "We planned that In addition, 0.05"),
        ("target_unknown", 2, "electrolyte FDH-1.35M-LiPD,", "electrolyte TGT-UNKNOWN,"),
        ("CE_cell", 2, "Li||Cu", "Li||Ag"),
        ("CE_value", 2, "98%", "87%"),
        ("CE_cycles", 2, "200 times", "201 times"),
        ("structural_hyphen_removed", 1, "FDH-1.2M-\nLiPF6", "FDH-1.2M\nLiPF6"),
    ]
    for name, index, before, after in mutations:
        case = copy.deepcopy(real)
        if before not in case["sources"][index]["text"]:
            raise ValueError("Declared mutation absent: " + name)
        case.update(id=name, expected_candidate=False, origin="constructed_negative")
        case["sources"][index]["text"] = case["sources"][index]["text"].replace(before, after)
        cases.append(case)
    for variant in ("joint_permutation", "opaque_target_code", "different_work", "different_layer"):
        case = copy.deepcopy(real)
        case.update(id=variant, expected_candidate=variant in {"joint_permutation", "opaque_target_code"}, origin="constructed")
        if variant == "joint_permutation":
            case["sources"][1]["text"] = case["sources"][1]["text"].replace("0.05, 0.15, and 0.3", "0.15, 0.05, and 0.3").replace(
                "FDH-1.25M-LiPD,\nFDH-1.35M-LiPD", "FDH-1.35M-LiPD,\nFDH-1.25M-LiPD")
        elif variant == "opaque_target_code":
            for source in case["sources"]:
                source["text"] = source["text"].replace("FDH-1.35M-LiPD", "TGT-999-LiPD")
        elif variant == "different_work":
            case["sources"][1]["article_id"] = "different-work"
        else:
            case["layers"][case["sources"][1]["chunk_id"]] = "ocr"
        cases.append(case)
    changed = copy.deepcopy(real)
    changed.update(id="coherent_numeric_change", expected_candidate=True, origin="constructed_positive")
    changed["sources"][0]["text"] = changed["sources"][0]["text"].replace("1.2 M LiPF6", "0.8 M LiPF6").replace(
        "added 0.15 M", "added 0.2 M").replace("new\nbifunctional electrolyte of 1.35 M", "new\nbifunctional electrolyte of 1.0 M")
    changed["sources"][1]["text"] = changed["sources"][1]["text"].replace("dissolving 1.2\nM", "dissolving 0.8\nM").replace(
        "0.05, 0.15, and 0.3", "0.05, 0.2, and 0.3")
    cases.append(changed)
    changed = copy.deepcopy(real)
    changed.update(id="coherent_base_reordering", expected_candidate=True, origin="constructed_positive")
    original = ("EC/dimethyl carbonate (DMC) (1:1 by volume), FEC/\nDMC (1:1 by volume), and FEC/DMC/HFE (1:1:1 by volume)")
    replacement = ("FEC/DMC/HFE (1:1:1 by volume), FEC/DMC (1:1 by volume), "
                   "and EC/dimethyl carbonate (DMC) (1:1 by volume)")
    if original not in changed["sources"][1]["text"]:
        raise ValueError("Declared base-order surface absent")
    changed["sources"][1]["text"] = changed["sources"][1]["text"].replace(original, replacement).replace(
        "ED-1.2M-LiPF6, FD-1.2M-LiPF6, and FDH-1.2M-\nLiPF6", "FDH-1.2M-LiPF6, FD-1.2M-LiPF6, and ED-1.2M-LiPF6")
    cases.append(changed)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    files.write(args.output, build())


if __name__ == "__main__":
    main()
