"""Freeze unchanged service/native inputs and app sources; no live send mode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts.source_paraphrases_20261109 import run as compare_service

BASE = files.ROOT / "output/source_role_assembly_20261109"
PROTOCOL = files.ROOT / "docs/records/source_role_assembly_protocol_2026-11-09_v0.1.md"


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
        files.verify_manifest(BASE / "freeze_v01")
    summary = compare_service(output / "service", freeze=False)
    if not freeze:
        for name in [*(f"Q{i:02}_current.json" for i in range(1, 6)), *(f"old/{i:03}.json" for i in range(76)),
                     *(f"Q{i:02}_native_unsent.json" for i in range(1, 6))]:
            if (BASE / "freeze_v01/service" / name).read_bytes() != (output / "service" / name).read_bytes():
                raise ValueError("Stage baseline changed: " + name)
    files.verify(bindings)
    files.write(output / "bindings.json", bindings)
    files.write(output / "summary.json", summary)
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
    print(json.dumps({k: v for k, v in summary.items() if k not in {"regressions", "native_unsent"}}), flush=True)


if __name__ == "__main__":
    main()
