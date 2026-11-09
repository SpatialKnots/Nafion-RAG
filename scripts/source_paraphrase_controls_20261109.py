"""Artificial rewrites of exposed real source anchors; never independent gold."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from app.generation.providers import Evidence
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE

FREEZE = files.ROOT / "output/source_paraphrases_20261109/freeze_v01"


def build() -> list[dict]:
    files.verify_manifest(FREEZE)
    corpus = read(CORPUS_BASE / "Q01/corpus.json")
    windows = read(FREEZE / "source_windows.json")
    controls = []
    for role, cid in (("gas_synthesis", "Q02"), ("eis_medium", "Q02"), ("hold_observation", "Q04")):
        window, = [w for w in windows if w["case_id"] == cid and w["role"] == role]
        anchor, trace = window["anchor"], read(FREEZE / f"{cid}_current.json")["trace"]
        sources = [asdict(Evidence(**{**e, "source_type": "main_text", "text": corpus[e["chunk_id"]]["full_text"]}))
                   for e in trace["evidence"]]
        g = anchor["groups"]
        if role == "gas_synthesis":
            positive = (f"Li foils were treated with O2 gas at temperatures from {g['low']} °C "
                        f"to {g['high']} °C for {g['hours']} hour.")
            alternatives = [("between", positive.replace("from ", "between ").replace(" °C to ", " °C and ")),
                            ("linebreaks", positive.replace(" ", "\n"))]
            negatives = [("material", positive.replace("Li foils", "Na foils")),
                         ("gas", positive.replace("O2 gas", "N2 gas")),
                         ("operation", positive.replace("treated with", "dried in")),
                         ("unit", positive.replace("°C", "K")),
                         ("duration_missing", positive[:positive.index(" for ")] + "."),
                         ("other_operation", positive.replace(" for ", ". The pellets were annealed for ")),
                         ("negation", positive.replace("were treated", "were not treated")),
                         ("future", positive.replace("were treated", "will be treated"))]
        elif role == "eis_medium":
            positive = (f"electrolyte containing {g['concentration']} M LiPF6 in EC/DEC "
                        f"({g['left']}/{g['right']} by volume)")
            alternatives = [("whitespace", positive.replace(" ", "\n")),
                            ("volume_ratio", positive.replace("by volume", "volume ratio"))]
            negatives = [("molality", positive.replace(" M ", " m ")),
                         ("salt", positive.replace("LiPF6", "NaPF6")),
                         ("solvent", positive.replace("EC/DEC", "EC/DMC")),
                         ("basis", positive.replace("by volume", "by mass")),
                         ("basis_missing", positive.replace(" by volume", "")),
                         ("negative_number", positive.replace(g["concentration"] + " M", "-" + g["concentration"] + " M")),
                         ("other_operation", positive.replace(" in EC/DEC ", ". Solvent was prepared in EC/DEC ")),
                         ("not_used", "We did not use " + positive)]
        else:
            positive = (f"An isothermal treatment lasting {g['days']} days was performed at {g['temperature']} ◦C. "
                        "This treatment did not change the measured W values.")
            alternatives = [("conducted", positive.replace("performed", "conducted")),
                            ("linebreaks", positive.replace(" ", "\n"))]
            negatives = [("operation", positive.replace("isothermal treatment", "isothermal drying")),
                         ("unit", positive.replace("◦C", "K")),
                         ("future", positive.replace("was performed", "will be performed")),
                         ("negation", positive.replace("was performed", "was not performed")),
                         ("opposite_result", positive.replace("did not change", "changed")),
                         ("observation_missing", positive[:positive.index("This treatment")]),
                         ("other_subject", positive.replace("This treatment did not", "Another sample did not")),
                         ("intervening_operation", positive.replace("This treatment", "The samples were dried. This treatment"))]
        variants = [("original", anchor["text"], True), ("positive", positive, True)]
        variants += [(name, text, True) for name, text in alternatives]
        variants += [(name, text, False) for name, text in negatives]
        variants += [(prefix, prefix + " " + positive, False)
                     for prefix in ("Hypothetically,", "It is not true that", "We planned", "We assume")]
        for name, replacement, expected in variants:
            rewritten = []
            for e in sources:
                if e["chunk_id"] == anchor["chunk_id"]:
                    if e["text"][anchor["start"]:anchor["end"]] != anchor["text"]:
                        raise ValueError("Real source offset changed")
                    text = e["text"][:anchor["start"]] + replacement + e["text"][anchor["end"]:]
                    rewritten.append({**e, "text": text})
                else:
                    rewritten.append(e)
            controls.append({"id": role + ":" + name, "role": role, "question": trace["retrieval"]["query"],
                             "origin": "exposed_real_anchor_with_constructed_rewrite" if name != "original" else "exposed_real_source",
                             "expected_eligible": expected, "sources": rewritten,
                             "original_anchor": anchor, "replacement": replacement})
    return controls


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adverse", action="store_true")
    args = parser.parse_args()
    controls = build()
    if args.adverse:
        additions = []
        for original in [c for c in controls if c["id"].endswith(":positive")]:
            role = original["role"]
            for change in ("prior_work", "other_sample", "formula_case"):
                text = original["replacement"]
                if change == "prior_work":
                    text = "Previous work reported that " + text
                elif change == "other_sample":
                    text = "For another sample, " + text
                else:
                    before, after = {"gas_synthesis": ("Li foils", "li foils"), "eis_medium": ("LiPF6", "LIPF6"),
                                     "hold_observation": (" W ", " w ")}[role]
                    text = text.replace(before, after)
                sources = [{**e, "text": e["text"].replace(original["replacement"], text)} for e in original["sources"]]
                additions.append({**original, "id": role + ":" + change, "replacement": text,
                                  "sources": sources, "expected_eligible": False})
        controls.extend(additions)
    files.write(args.output, controls)


if __name__ == "__main__":
    main()
