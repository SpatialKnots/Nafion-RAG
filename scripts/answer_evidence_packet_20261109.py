"""Freeze/compare inference separately from the diagnostic evidence packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts.source_role_assembly_20261109 import run as compare_service

BASE = files.ROOT / "output/answer_evidence_packet_20261109"
PROTOCOL = files.ROOT / "docs/records/answer_evidence_packet_protocol_2026-11-09_v0.1.md"


def run(output: Path, *, freeze: bool) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), *files.ROOT.joinpath("app").rglob("*.yaml"),
             PROTOCOL, Path(__file__), files.ROOT / "output/answer_requirements_20261109/controls_v01.json"]
    bindings = files.bindings(paths)
    if freeze:
        for source in paths:
            target = output / "source_snapshot" / source.relative_to(files.ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            files.save(target, source.read_bytes())
    else:
        files.verify_manifest(BASE / "freeze_v01")
    summary = compare_service(output / "service", freeze=False)
    files.verify(bindings)
    files.write(output / "bindings.json", bindings)
    files.write(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.output, freeze=args.freeze)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in {"regressions", "native_unsent"}}), flush=True)


if __name__ == "__main__":
    main()
