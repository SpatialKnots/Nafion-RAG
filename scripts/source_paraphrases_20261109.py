"""Freeze/compare the actual offline service; no send mode or real provider calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_answer_fidelity_20261105 import native
from scripts.check_condition_context_20261106 import replay
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE, OLD
from scripts.review_retrieval_ablation import unpack

ROOT = files.ROOT
BASE = ROOT / "output/source_paraphrases_20261109"
PREVIOUS = ROOT / "output/condition_context_completion_20261106/review_v02"
PROTOCOL = ROOT / "docs/records/source_paraphrases_protocol_2026-11-09_v0.1.md"


def run(output: Path, *, freeze: bool) -> dict:
    settings = files.configure()
    output.mkdir(parents=True, exist_ok=False)
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"),
             Path(__file__), PROTOCOL]
    bindings = files.bindings(paths)
    if freeze:
        for source in paths:
            target = output / "source_snapshot" / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            files.save(target, source.read_bytes())
    else:
        files.verify_manifest(BASE / "freeze_v01")
    corpus, articles = read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")
    bindings.update(files.bindings([CORPUS_BASE / "Q01/corpus.json", CORPUS_BASE / "Q01/articles.json"]))
    windows, comparisons, natives = [], [], {}
    expected = PREVIOUS if freeze else BASE / "freeze_v01"
    for number in range(1, 6):
        cid = f"Q{number:02}"
        path = CORPUS_BASE / cid / "boundaries.json"
        bindings.update(files.bindings([path]))
        result, _ = replay(read(path), settings, corpus, articles)
        suffix = "repaired" if freeze else "current"
        prior = expected / f"{cid}_{suffix}.json"
        identical = result == read(prior)
        files.write(output / f"{cid}_current.json", result)
        if not identical:
            raise ValueError("Full current question trace changed: " + cid)
        natives[cid] = native(cid, result["trace"], settings, output)
        if (output / f"{cid}_native_unsent.json").read_bytes() != (expected / f"{cid}_native_unsent.json").read_bytes():
            raise ValueError("Actual native bytes changed: " + cid)
        if cid in {"Q02", "Q04"}:
            for role in result["trace"]["metadata"]["answer_fidelity"]["requirements"]:
                for anchor in role["anchors"]:
                    raw = corpus[anchor["chunk_id"]]["full_text"]
                    if raw[anchor["start"]:anchor["end"]] != anchor["text"] or files.sha(raw.encode()) != anchor["raw_chunk_sha256"]:
                        raise ValueError("Original raw anchor differs")
                    windows.append({"case_id": cid, "role": role["key"], "anchor": anchor,
                                    "source": corpus[anchor["chunk_id"]]})
        comparisons.append({"id": cid, "full_service_identical": identical, "native_identical": True})
        print(json.dumps({"current": cid, "identical": identical}), flush=True)
    old_corpus, old_articles = read(OLD / "corpus.json"), read(OLD / "articles.json")
    dataset, regressions = read(OLD / "cases.json"), []
    bindings.update(files.bindings([OLD / "corpus.json", OLD / "articles.json", OLD / "cases.json"]))
    (output / "old").mkdir()
    for index, case in enumerate(dataset["cases"]):
        path = OLD / f"cases/{index:03}_baseline.json"
        bindings.update(files.bindings([path]))
        value, _ = replay(unpack(read(path), old_corpus), settings, old_corpus, old_articles)
        files.write(output / f"old/{index:03}.json", value)
        if not freeze and value != read(expected / f"old/{index:03}.json"):
            raise ValueError("Old full service trace changed: " + case["id"])
        regressions.append({"id": case["id"], "full_service_identical": not freeze,
                            "paraphrase_active": bool(value["trace"]["metadata"].get("answer_fidelity", {}).get("source_paraphrases"))})
        if index % 20 == 0:
            print(json.dumps({"old": index + 1}), flush=True)
    files.verify(bindings)
    summary = {"mode": "freeze" if freeze else "compare", "actual_service_executions": 5 + len(regressions),
               "current_comparisons": comparisons, "old_cases": len(regressions), "native_unsent": natives,
               "regressions": regressions, "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0,
               "independent_scientific_accuracy": None}
    files.write(output / "summary.json", summary)
    files.write(output / "bindings.json", bindings)
    files.write(output / "source_windows.json", windows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, freeze=args.freeze)
    if policy.denied:
        raise ValueError("Unexpected external network attempt")
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    files.manifest(args.output)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"regressions", "native_unsent"}}), flush=True)


if __name__ == "__main__":
    main()
