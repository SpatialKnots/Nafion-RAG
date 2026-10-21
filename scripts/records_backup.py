"""Backup, verify and restore an independent record review store (same machine)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.records.backup import create_backup, restore_backup, verify_backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    for action in ("verify", "restore"):
        command = commands.add_parser(action)
        command.add_argument("--backup", type=Path, required=True)
        command.add_argument("--manifest-sha256", required=True)
        if action == "restore":
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "create":
        result = create_backup(args.root, args.output)
    elif args.command == "restore":
        result = restore_backup(args.backup, args.output, args.manifest_sha256)
    else:
        manifest = verify_backup(args.backup, args.manifest_sha256)
        result = {key: manifest[key] for key in ("version", "snapshot_id", "records", "events", "restore_policy")}
        result["verified_files"] = len(manifest["files"])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
