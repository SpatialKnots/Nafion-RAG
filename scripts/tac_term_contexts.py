"""Bind existing complete Terms inventories to frozen source contexts and lexical spans."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.records.sources import file_hash
from app.terms.contexts import build_article, validate_article
from scripts.tac_experiment import digest, validate_profiles, write_new
from scripts.tac_terms import INVENTORY_VERSION, validate_terms

VERSION = "tac_term_contexts_v0.1"
COMPONENTS = ("app/terms/schema.py", "app/terms/contexts.py", "app/records/schema.py")


def validate_contexts(snapshot: dict[str, Any], profiles: dict[str, Any], inventory: dict[str, Any],
                      data: dict[str, Any], inventory_sha256: str) -> dict[str, dict[str, Any]]:
    if (data.get("schema") != VERSION or data.get("inventory_sha256") != inventory_sha256
            or data.get("profiles_sha256") != inventory["profiles_sha256"]
            or data.get("snapshot_sha256") != inventory["snapshot_sha256"]
            or data.get("state") != "unclassified_source_bound_terms"):
        raise ValueError("Terms context schema/input/state mismatch")
    if inventory.get("schema") != INVENTORY_VERSION:
        raise ValueError("Terms contexts require complete inventory v0.1")
    validate_terms(snapshot, profiles, inventory, inventory["profiles_sha256"])
    articles = {a["article_id"]: a for a in snapshot["articles"]}
    predicted = {p["article_id"]: p for p in profiles["profiles"]}
    inventories = {r["article_id"]: r for r in inventory["articles"]}
    rows = data.get("articles", [])
    result = {r["article_id"]: r for r in rows}
    if len(result) != len(rows) or set(result) != set(articles):
        raise ValueError("Terms context article inventory mismatch")
    for identifier, row in result.items():
        validate_article(articles[identifier], predicted[identifier], inventories[identifier], row)
    return result


def verify_pdfs(snapshot: dict[str, Any], root: Path) -> dict[str, str]:
    """Read only PDFs inside the declared source root; verify both original and layer."""
    verified: dict[str, str] = {}
    for article in snapshot["articles"]:
        pairs = [(article["original_pdf_path"], article["original_pdf_sha256"])]
        pairs += [(p["layer_pdf_path"], p["layer_pdf_sha256"]) for p in article["pages"]]
        for name, expected in pairs:
            path = (root / name).resolve()
            if path.suffix.lower() != ".pdf" or not path.is_relative_to(root.resolve()):
                raise ValueError(f"Terms source PDF outside declared root: {name}")
            if name not in verified:
                verified[name] = file_hash(path)
            if verified[name] != expected:
                raise ValueError(f"Terms source PDF checksum mismatch: {name}")
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    raw = [p.read_bytes() for p in (args.snapshot, args.profiles, args.inventory)]
    snapshot, profiles, inventory = [json.loads(r) for r in raw]
    validate_profiles(snapshot, profiles, digest(raw[0]))
    validate_terms(snapshot, profiles, inventory, digest(raw[1]))
    if inventory["schema"] != INVENTORY_VERSION:
        raise ValueError("Terms contexts require complete inventory v0.1")
    pdfs = verify_pdfs(snapshot, args.source_root)
    predicted = {p["article_id"]: p for p in profiles["profiles"]}
    inventories = {r["article_id"]: r for r in inventory["articles"]}
    result = {"schema": VERSION, "created_at": datetime.now(UTC).isoformat(), "state": "unclassified_source_bound_terms",
              "snapshot_sha256": digest(raw[0]), "profiles_sha256": digest(raw[1]), "inventory_sha256": digest(raw[2]),
              "code_sha256": digest(Path(__file__).read_bytes()),
              "component_sha256": {name: digest(Path(name).read_bytes()) for name in COMPONENTS},
              "source_pdf_hashes": pdfs,
              "articles": [build_article(a, predicted[a["article_id"]], inventories[a["article_id"]]).model_dump(mode="json")
                           for a in snapshot["articles"]]}
    validate_contexts(snapshot, profiles, inventory, result, digest(raw[2]))
    write_new(args.output, result)
    print(json.dumps({"documents": len(result["articles"]), **{
        name: sum(len(a[name]) for a in result["articles"]) for name in ("terms", "mentions", "contexts", "uses", "containment")}}))


if __name__ == "__main__":
    main()
