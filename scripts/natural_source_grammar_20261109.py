"""Natural-source recipe audit and unchanged full-service comparison; offline only."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from app.generation.fact_recipes import RECIPES
from app.generation.fact_types import FactPatternError
from app.generation.providers import Evidence
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.source_paraphrases_20261109 import run as compare_service

BASE = files.ROOT / "output/natural_source_grammar_20261109"
FREEZE = BASE / "freeze_v02"
PROTOCOL = files.ROOT / "docs/records/natural_source_grammar_protocol_2026-11-09_v0.1.md"
CUES = {
    "composition": r"film[\s-]*forming\s+additive|bifunctional\s+electrolyte",
    "capacity": r"capacity\s+retention|batteries\s+to\s+maintain",
    "coulombic": r"coulombic\s+e(?:ﬃ|ffi)ciency|half.cells\s+maintain",
    "dispersion_method": r"azeotropic|ethanol.free",
    "casting": r"recast\s+membrane|recast\s+film",
    "conductivity_table": r"EIS\s+analysis|Water\s+content",
}


def evidence(row: dict) -> Evidence:
    return Evidence("E1", row["article_id"], row["chunk_id"], row["title"], row["doi"],
                    row["page_start"], row["page_end"], "main_text", row["full_text"], 0, "frozen_recipe_audit", {}, {})


def audit() -> dict:
    corpus = read(CORPUS_BASE / "Q01/corpus.json")
    rows = []
    for row in corpus.values():
        for recipe, pattern in CUES.items():
            cues = [{"start": m.start(), "end": m.end(), "text": m.group()}
                    for m in re.finditer(pattern, row["full_text"], re.I)]
            if not cues:
                continue
            result = {"recipe": recipe, "source": row, "raw_chunk_sha256": files.sha(row["full_text"].encode()), "cues": cues}
            if recipe in {"dispersion_method", "casting", "conductivity_table"}:
                # Explicit, already exposed Q05 selectors; not inferred scientific ownership.
                params = {"grade": "Nafion-117", "product": "b1", "comparator": "NCD"}
                result["selector_scope"] = "exposed_Q05_selectors_not_generic_other_work_extraction"
            else:
                params = {}
            try:
                rendered = RECIPES[recipe](evidence(row), params)
            except FactPatternError as exc:
                result.update(complete=False, reason=str(exc))
            else:
                result.update(complete=True, rendering=rendered.data())
            rows.append(result)
    return {"corpus_rows": len(corpus), "works": len({r["article_id"] for r in corpus.values()}), "rows": rows,
            "warning": "cue presence and recipe refusal are diagnostics, not automatic scientific labels"}


def run(output: Path, *, freeze: bool) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), *files.ROOT.joinpath("app").rglob("*.yaml"), Path(__file__), PROTOCOL]
    bindings = files.bindings(paths)
    if freeze:
        for path in paths:
            target = output / "source_snapshot" / path.relative_to(files.ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            files.save(target, path.read_bytes())
    else:
        files.verify_manifest(FREEZE)
    results = audit()
    files.write(output / "recipe_audit.json", results)
    service = compare_service(output / "service", freeze=False)
    if not freeze:
        before = FREEZE / "service"
        for name in [*(f"Q{i:02}_current.json" for i in range(1, 6)), *(f"old/{i:03}.json" for i in range(76)),
                     *(f"Q{i:02}_native_unsent.json" for i in range(1, 6))]:
            if (before / name).read_bytes() != (output / "service" / name).read_bytes():
                raise ValueError("Stage baseline changed: " + name)
    summary = {"natural_recipe_observations": len(results["rows"]), "corpus_rows": results["corpus_rows"],
               "works": results["works"], "complete_recipe_observations": sum(r["complete"] for r in results["rows"]),
               "service_executions": service["actual_service_executions"], "real_model_oauth_slots": 0}
    files.verify(bindings)
    files.write(output / "summary.json", summary)
    files.write(output / "bindings.json", bindings)
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
        raise ValueError("External network attempted")
    files.write(args.output / "network.json", {"denials": policy.denied})
    files.manifest(args.output)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
