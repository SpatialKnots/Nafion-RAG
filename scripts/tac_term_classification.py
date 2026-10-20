"""Generate and validate draft source-bound classification sidecars and saved subsets."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.terms.classification import AUTOMATIC_VERSION, CONTEXT_VERSION, PHRASE_VERSION, VERSION, ManualInput, Taxonomy, classify_article
from scripts.tac_experiment import digest, validate_profiles, write_new
from scripts.tac_term_contexts import validate_contexts, verify_pdfs

LEGACY_TAXONOMY = Path(__file__).resolve().parents[1] / "app/terms/taxonomy_v01.json"
DEFAULT_TAXONOMY = Path(__file__).resolve().parents[1] / "app/terms/taxonomy_v04.json"


def build_classification(contexts: dict[str, Any], taxonomy: dict[str, Any], contexts_hash: str,
                         taxonomy_hash: str, manual_data: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = Taxonomy.model_validate(taxonomy)
    automatic = policy.schema_version != "tac_terms_taxonomy_v0.1"
    if automatic and manual_data is not None:
        raise ValueError("Automatic Terms classification does not accept manual input")
    manual = ManualInput.model_validate(manual_data) if manual_data is not None else None
    if manual and (manual.contexts_sha256 != contexts_hash or manual.taxonomy_sha256 != taxonomy_hash):
        raise ValueError("Manual classification frozen input mismatch")
    targets = {u["use_id"]: a["article_id"] for a in contexts["articles"] for u in a["uses"]}
    if manual and any(p.use_id not in targets for p in manual.proposals):
        raise ValueError("Manual classification unknown target")
    rows = [classify_article(a, policy, taxonomy_hash, [p for p in manual.proposals if targets[p.use_id] == a["article_id"]]
                             if manual else []) for a in contexts["articles"]]
    views = [{"view_id": f"{axis}:{category}", "filters": {axis: category}, "sort": "rank", "taxonomy_sha256": taxonomy_hash,
              "contexts_sha256": contexts_hash, "review_revision_cutoff": 0, "state": "frozen_proposals_only"}
             for axis, categories in policy.categories.items() for category in categories]
    version = CONTEXT_VERSION if policy.schema_version == "tac_terms_taxonomy_v0.3" else AUTOMATIC_VERSION if automatic else VERSION
    if policy.schema_version == 'tac_terms_taxonomy_v0.4':
        version = PHRASE_VERSION
    return {"schema": version,
            "state": "proposed_not_scientifically_accepted", "contexts_sha256": contexts_hash,
            "taxonomy_sha256": taxonomy_hash, "taxonomy": taxonomy, "manual_input": manual_data,
            "manual_sha256": digest(json.dumps(manual_data, sort_keys=True, ensure_ascii=False).encode()),
            "saved_views": views, "articles": rows}


def validate_classification(contexts: dict[str, Any], data: dict[str, Any], contexts_hash: str) -> dict[str, dict[str, Any]]:
    # Embedded taxonomy has a file-byte hash binding plus a canonical content binding.
    if (data.get("schema") not in {VERSION, AUTOMATIC_VERSION, CONTEXT_VERSION, PHRASE_VERSION}
            or data.get("state") != "proposed_not_scientifically_accepted"):
        raise ValueError("Classification schema/state mismatch")
    if digest(json.dumps(data["taxonomy"], sort_keys=True, ensure_ascii=False).encode()) != data.get("taxonomy_content_sha256"):
        raise ValueError("Classification taxonomy content mismatch")
    expected = build_classification(contexts, data["taxonomy"], contexts_hash, data["taxonomy_sha256"], data["manual_input"])
    if any(data.get(key) != value for key, value in expected.items()):
        raise ValueError("Classification source/policy/assignment/view mismatch")
    return {a["article_id"]: a for a in data["articles"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "profiles", "inventory", "contexts", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--manual", type=Path, help="Legacy v0.1 replay only; disabled for automatic taxonomies")
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    paths = {name: getattr(args, name) for name in ("snapshot", "profiles", "inventory", "contexts", "taxonomy")}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    values = {name: json.loads(value) for name, value in raw.items()}
    hashes = {name: digest(value) for name, value in raw.items()}
    validate_profiles(values["snapshot"], values["profiles"], hashes["snapshot"])
    validate_contexts(values["snapshot"], values["profiles"], values["inventory"], values["contexts"], hashes["inventory"])
    if values["contexts"]["snapshot_sha256"] != hashes["snapshot"] or values["contexts"]["profiles_sha256"] != hashes["profiles"]:
        raise ValueError("Classification frozen input checksum mismatch")
    pdfs = verify_pdfs(values["snapshot"], args.source_root)
    data = build_classification(values["contexts"], values["taxonomy"], hashes["contexts"], hashes["taxonomy"],
                                json.loads(args.manual.read_bytes()) if args.manual else None)
    data["taxonomy_content_sha256"] = digest(json.dumps(data["taxonomy"], sort_keys=True, ensure_ascii=False).encode())
    data["provenance"] = {"created_at": datetime.now(UTC).isoformat(), "input_sha256": hashes,
                          "source_pdf_hashes": pdfs,
                          "code_sha256": {name: digest(Path(name).read_bytes()) for name in
                                          ("app/terms/classification.py", "scripts/tac_term_classification.py")}}
    validate_classification(values["contexts"], data, hashes["contexts"])
    write_new(args.output, data)
    print(json.dumps({"documents": len(data["articles"]), "assignments": sum(len(a["assignments"]) for a in data["articles"]),
                      "sha256": digest(args.output.read_bytes())}))


if __name__ == "__main__":
    main()
