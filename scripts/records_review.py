"""Initialize, inspect, export or serve the separate full-record revision editor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from app.records.revision_store import export_review, initialize_store, load_state, review_csv
from app.records.revision_ui import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Freeze saved bundles into a fresh independent review directory")
    init.add_argument("--inputs", type=Path, nargs="+", required=True)
    init.add_argument("--source-root", type=Path, default=Path("."))
    inspect = commands.add_parser("inspect", help="Validate sources and read persisted history")
    export = commands.add_parser("export", help="Write revision-aware JSON/CSV to a fresh output directory")
    export.add_argument("--output-dir", type=Path, required=True)
    serve = commands.add_parser("serve", help="Run local editor, bound to 127.0.0.1")
    serve.add_argument("--port", type=int, default=8767)
    for command in (init, inspect, export, serve):
        command.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "init":
        print(json.dumps({"snapshot_id": initialize_store(args.inputs, args.root, source_root=args.source_root)}))
    elif args.command == "serve":
        load_state(args.root)
        uvicorn.run(create_app(args.root), host="127.0.0.1", port=args.port)
    elif args.command == "inspect":
        data = load_state(args.root)
        print(json.dumps({"snapshot_id": data["snapshot_id"], "stale_code": data["stale_code"],
                          "records": [{key: item[key] for key in ("record_key", "revision", "declared_review_status")}
                                      for item in data["records"]]}, ensure_ascii=False))
    else:
        if args.output_dir.exists():
            raise FileExistsError(f"Export directory already exists: {args.output_dir}")
        data = export_review(args.root)
        csv_text = review_csv(data)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        with (args.output_dir / "review.json").open("x", encoding="utf-8", newline="") as stream:
            stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        with (args.output_dir / "review.csv").open("x", encoding="utf-8", newline="") as stream:
            stream.write(csv_text)
        print(json.dumps({"records": len(data["records"]), "scientific_admission": "not_evaluated"}))


if __name__ == "__main__":
    main()
