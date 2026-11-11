"""Freeze the offline candidate before intake of the user's separate evaluation set."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

from scripts import audit_answer_priorities_20261111 as audit
from scripts import gigachat_answer_smoke as f


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    paths = [f.ROOT / "AGENTS.md", f.ROOT / "pyproject.toml"]
    paths += [p for name in ("app", "scripts", "tests", "docs") for p in f.ROOT.joinpath(name).rglob("*")
              if p.is_file() and "__pycache__" not in p.parts]
    bindings = f.bindings(paths)
    for name in bindings:
        source = Path(name)
        target = folder / "source_snapshot" / source.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, source.read_bytes())
    for stage in ("comparison_v01", "history_v01", "wheel_v01", "review_v01"):
        f.verify_manifest(audit.BASE / stage)
    versions = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    payload = {"bindings": bindings, "packages": versions, "python": sys.version,
        "protocol_sha256": f.sha(audit.PROTOCOL.read_bytes()), "independent_set_status": "awaiting_user_set",
        "registered_independent_cases": 0, "new_model_calls": 0, "new_oauth_calls": 0, "new_slots": 0,
        "scientific_accuracy": None, "plan_percent": 75}
    f.write(folder / "version.json", {**payload, "candidate_version_id": f.sha(f.encode(payload))})
    f.write(folder / "bindings.json", bindings)
    f.verify(bindings)
    f.manifest(folder)
    print(json.dumps({"candidate_version_id": f.sha(f.encode(payload)), "source_files": len(bindings),
                      "independent_cases": 0, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
