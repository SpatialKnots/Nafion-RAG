"""Prepare immutable Terms review snapshots, export views, and backup/restore decisions."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.terms.review_bundle import backup, graph_view, render_graph, render_table, restore
from app.terms.review_store import SCHEMA, code_hashes, latest, register_snapshot, sha
from scripts.tac_experiment import validate_profiles
from scripts.tac_review_html import render_table as make_table
from scripts.tac_term_contexts import validate_contexts, verify_pdfs
from scripts.tac_terms_graph import ASSETS, attach_classification, project_graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    for name in ("snapshot", "profiles", "inventory", "contexts", "classification", "metadata", "boundary-review"):
        prepare.add_argument(f"--{name}", type=Path, required=True)
    prepare.add_argument("--source-root", type=Path, default=Path("."))
    for command in (prepare, sub.add_parser("backup"), sub.add_parser("restore"), sub.add_parser("export")):
        command.add_argument("--root", type=Path, default=Path("data/reviews/terms"))
        if command.prog.endswith("backup") or command.prog.endswith("restore"):
            command.add_argument("--archive", type=Path, required=True)
        elif command.prog.endswith("export"):
            command.add_argument("--sid", required=True)
            command.add_argument("--cutoff", type=int)
            command.add_argument("--graph", type=Path, required=True)
            command.add_argument("--table", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "backup":
        backup(args.root, args.archive)
        print(json.dumps({"backup": str(args.archive)}))
        return
    if args.command == "restore":
        restore(args.archive, args.root)
        print(json.dumps({"restored": str(args.root)}))
        return
    if args.command == "export":
        if args.graph.exists() or args.table.exists():
            raise FileExistsError("Terms export outputs must be new")
        snapshot, graph = graph_view(args.root, args.sid, cutoff=args.cutoff)
        cutoff = graph["review"]["revision_cutoff"]
        table = render_table(snapshot, args.sid, latest(args.root, args.sid, cutoff), cutoff)
        for path, text in ((args.table, table), (args.graph, render_graph(snapshot, graph, args.table.resolve().as_uri()))):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as stream:
                stream.write(text)
        print(json.dumps({"snapshot": args.sid, "cutoff": cutoff, "graph": str(args.graph), "table": str(args.table)}))
        return
    names = ("snapshot", "profiles", "inventory", "contexts", "classification", "metadata", "boundary_review")
    paths = {name: getattr(args, name) for name in names}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    data = {name: json.loads(value) for name, value in raw.items()}
    hashes = {name: sha(value) for name, value in raw.items()}
    validate_profiles(data["snapshot"], data["profiles"], hashes["snapshot"])
    validate_contexts(data["snapshot"], data["profiles"], data["inventory"], data["contexts"], hashes["inventory"])
    if data["contexts"]["snapshot_sha256"] != hashes["snapshot"] or data["contexts"]["profiles_sha256"] != hashes["profiles"]:
        raise ValueError("Terms review frozen input mismatch")
    pdfs = verify_pdfs(data["snapshot"], args.source_root)
    graph = project_graph(data["snapshot"], data["profiles"], data["contexts"], args.source_root)
    attach_classification(graph, data["contexts"], data["classification"], hashes["contexts"])
    graph["provenance"] = {"input_sha256": hashes, "human_confirmation": "pending", "review_mode": "declared_local"}
    table = make_table(data["snapshot"], data["profiles"], data["metadata"], args.source_root.resolve(), hashes["profiles"],
                       hashes["metadata"], boundary_review=data["boundary_review"], boundary_review_sha256=hashes["boundary_review"],
                       terms=data["inventory"], terms_sha256=hashes["inventory"], term_contexts=data["contexts"],
                       term_contexts_sha256=hashes["contexts"], classification=data["classification"],
                       classification_sha256=hashes["classification"])
    assets = {sha(name.encode()): {"path": name, "sha256": checksum} for name, checksum in pdfs.items()}
    source_root = args.source_root.resolve()
    for href in re.findall(r'href="([^"]+)"', table):
        uri = html.unescape(href).split("#")[0]
        if uri.startswith("file:"):
            path = Path(unquote(urlparse(uri).path.lstrip("/") if re.match(r"^/[A-Za-z]:", urlparse(uri).path) else urlparse(uri).path))
            if not path.resolve().is_relative_to(source_root) or path.suffix.lower() not in {".png", ".pdf"}:
                raise ValueError("Terms table asset outside declared source root")
            if path.suffix.lower() == ".png":
                name = path.resolve().relative_to(source_root).as_posix()
                assets[sha(name.encode())] = {"path": name, "sha256": sha(path.read_bytes())}
    result = {"schema": SCHEMA, "source_root": str(source_root), "graph": graph, "table_html": table,
              "assets": assets, "input_sha256": hashes, "policy_code_sha256": code_hashes(),
              "viewer_assets": {name: (ASSETS / name).read_text(encoding="utf-8") for name in ("graph.js", "graph.css", "template.html")}}
    sid = register_snapshot(args.root, result)
    print(json.dumps({"snapshot_id": sid, "root": str(args.root), "documents": len(graph["articles"]), "terms": graph["totals"]["terms"]}))


if __name__ == "__main__":
    main()
