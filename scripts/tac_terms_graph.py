"""Export an offline, source-bound Terms graph from the frozen TAC contexts."""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.terms.classification import category_members, normalize
from scripts.tac_experiment import digest, validate_profiles
from scripts.tac_term_classification import validate_classification
from scripts.tac_term_contexts import validate_contexts, verify_pdfs

VERSION = "tac_terms_graph_v0.1"
CLASSIFIED_VERSION = "tac_terms_graph_v0.2"
ASSETS = Path(__file__).with_name("terms_graph")


def pdf_uri(name: str, root: Path) -> str:
    path = (root / name).resolve()
    if path.suffix.lower() != ".pdf" or not path.is_relative_to(root.resolve()):
        raise ValueError(f"Terms graph PDF outside declared source root: {name}")
    return path.as_uri()


def project_graph(snapshot: dict[str, Any], profiles: dict[str, Any], contexts: dict[str, Any], root: Path) -> dict[str, Any]:
    """Project structural memberships; never merge local term identities or assign scientific categories.

    Call only after validating the frozen inputs. Counts are distinct local term IDs,
    not mention counts. T/A/C overlap is retained, including zero-sized sections.
    """
    articles = {a["article_id"]: a for a in snapshot["articles"]}
    predicted = {p["article_id"]: p for p in profiles["profiles"]}
    result: list[dict[str, Any]] = []
    for number, row in enumerate(contexts["articles"], 1):
        identifier = row["article_id"]
        article, profile = articles[identifier], predicted[identifier]
        source_contexts = {c["context_id"]: c for c in row["contexts"]}
        groups = []
        for kind in ("T", "A", "C"):
            context_ids = [c["context_id"] for c in row["contexts"] if c["kind"] == kind]
            members = sorted({u["term_id"] for u in row["uses"] if source_contexts[u["context_id"]]["kind"] == kind})
            groups.append({"id": f"section:{identifier}:{kind}", "kind": kind, "term_ids": members,
                           "count": len(members), "context_ids": context_ids,
                           "section_status": profile.get("section_status", {}).get(kind)})
        terms = [{**t, "groups": [g["kind"] for g in groups if t["term_id"] in g["term_ids"]]} for t in row["terms"]]

        def source_links(source: dict[str, Any]) -> dict[str, Any]:
            page = source["page_number"]
            return {**source, "original_href": f"{pdf_uri(source['original_pdf_path'], root)}#page={page}",
                    "layer_href": f"{pdf_uri(source['layer_pdf_path'], root)}#page={page}"}

        result.append({"article_id": identifier, "number": number,
                       "title": profile["metadata_title"] or article["title"],
                       "title_status": "frozen_profile_metadata_title" if profile["metadata_title"] else "snapshot_title_fallback",
                       "count": len(terms), "terms": terms, "groups": groups,
                       "original_pdf_path": article["original_pdf_path"], "original_pdf_sha256": article["original_pdf_sha256"],
                       "original_href": pdf_uri(article["original_pdf_path"], root),
                       "contexts": [{**c, "source": source_links(c["source"])} for c in row["contexts"]],
                       "mentions": [{**m, "source": source_links(m["source"])} for m in row["mentions"]],
                       "uses": row["uses"], "containment": row["containment"], "diagnostics": row["diagnostics"]})
    return {"schema": VERSION, "state": "unclassified_structural_groups", "count_unit": "distinct_article_local_term_id",
            "circle_area": "proportional_to_unfiltered_group_count_within_current_view", "articles": result,
            "totals": {"articles": len(result), "terms": sum(a["count"] for a in result),
                       "mentions": sum(len(a["mentions"]) for a in result), "contexts": sum(len(a["contexts"]) for a in result)}}


def render_graph(data: dict[str, Any], review_href: str | None = None) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    review = (f'<a href="{html.escape(review_href, quote=True)}" target="_blank" rel="noopener">Таблица TAC ↗</a>'
              if review_href else "")
    # Replace each placeholder exactly once; data cannot become a second template pass.
    replacements = {"@@STYLE@@": (ASSETS / "graph.css").read_text(encoding="utf-8"), "@@DATA@@": payload,
                    "@@SCRIPT@@": (ASSETS / "graph.js").read_text(encoding="utf-8"), "@@REVIEW@@": review}
    return re.sub(r"@@(?:STYLE|DATA|SCRIPT|REVIEW)@@", lambda match: replacements[match.group()], template)


def attach_classification(data: dict[str, Any], contexts: dict[str, Any], classification: dict[str, Any], contexts_hash: str) -> None:
    records = validate_classification(contexts, classification, contexts_hash)
    data.update(schema=CLASSIFIED_VERSION, state="draft_classification_proposals",
                taxonomy=classification["taxonomy"], saved_views=classification["saved_views"])
    for article in data["articles"]:
        record = records[article["article_id"]]
        article["assignments"] = record["assignments"]
        article["category_groups"] = {axis: [{**g, "id": f"{axis}:{article['article_id']}:{g['category']}",
                                             "kind": g["category"]} for g in groups] for axis, groups in record["groups"].items()}
        memberships: dict[str, dict[str, set[str]]] = {}
        for assignment in record["assignments"]:
            memberships.setdefault(assignment["term_id"], {}).setdefault(assignment["axis"], set()).update(category_members(assignment))
        mentions = {m["mention_id"]: m["source"] for m in article["mentions"]}
        uses = {u["use_id"]: u for u in article["uses"]}
        for term in article["terms"]:
            term["sort_key"] = normalize(term["label"])
            term["memberships"] = {axis: sorted(categories) for axis, categories in memberships[term["term_id"]].items()}
            term["first_source"] = list(min((mentions[uses[i]["mention_id"]]["page_number"], mentions[uses[i]["mention_id"]]["start"])
                                            for i in term["use_ids"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "profiles", "inventory", "contexts", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--review", type=Path)
    parser.add_argument("--classification", type=Path, help="Optional source-bound draft classification sidecar")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    paths = {name: getattr(args, name) for name in ("snapshot", "profiles", "inventory", "contexts")}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    inputs = {name: json.loads(value) for name, value in raw.items()}
    hashes = {name: digest(value) for name, value in raw.items()}
    validate_profiles(inputs["snapshot"], inputs["profiles"], hashes["snapshot"])
    validate_contexts(inputs["snapshot"], inputs["profiles"], inputs["inventory"], inputs["contexts"], hashes["inventory"])
    if inputs["contexts"]["snapshot_sha256"] != hashes["snapshot"] or inputs["contexts"]["profiles_sha256"] != hashes["profiles"]:
        raise ValueError("Terms graph frozen input checksum mismatch")
    pdfs = verify_pdfs(inputs["snapshot"], args.source_root)
    data = project_graph(inputs["snapshot"], inputs["profiles"], inputs["contexts"], args.source_root)
    if args.classification:
        classification_raw = args.classification.read_bytes()
        attach_classification(data, inputs["contexts"], json.loads(classification_raw), hashes["contexts"])
        hashes["classification"] = digest(classification_raw)
        paths["classification"] = args.classification
    sources = [Path(__file__), *(ASSETS / name for name in ("template.html", "graph.css", "graph.js"))]
    if args.classification:
        sources += [Path("app/terms/classification.py"), Path("scripts/tac_term_classification.py")]
    data["provenance"] = {"created_at": datetime.now(UTC).isoformat(), "input_sha256": hashes,
                          "input_paths": {name: str(path) for name, path in paths.items()},
                          "code_sha256": {p.name: digest(p.read_bytes()) for p in sources}, "verified_pdf_files": len(pdfs),
                          "human_confirmation": "pending"}
    review_href = None
    if args.review:
        if not args.review.is_file():
            raise FileNotFoundError(args.review)
        review_href = args.review.resolve().as_uri()
        data["provenance"]["review_sha256"] = digest(args.review.read_bytes())
    output = render_graph(data, review_href)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(output)
    print(json.dumps({**data["totals"], "schema": data["schema"], "output": str(args.output),
                      "sha256": digest(args.output.read_bytes()), "bytes": args.output.stat().st_size}))


if __name__ == "__main__":
    main()
