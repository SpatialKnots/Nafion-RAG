"""Freeze/compare offline service inputs for the opt-in Methods policy; no send mode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts.source_role_assembly_20261109 import run as compare_service

BASE = files.ROOT / "output/methods_identity_runtime_20261109"
PROTOCOL = files.ROOT / "docs/records/methods_identity_runtime_protocol_2026-11-09_v0.1.md"


def run(output: Path, *, freeze: bool, enabled: bool) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), *files.ROOT.joinpath("app").rglob("*.yaml"),
             PROTOCOL, Path(__file__), files.ROOT / "output/methods_identity_bridge_20261109/controls_v02.json"]
    bindings = files.bindings(paths)
    if freeze:
        for source in paths:
            target = output / "source_snapshot" / source.relative_to(files.ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            files.save(target, source.read_bytes())
    else:
        files.verify_manifest(BASE / "freeze_v01")
    settings = files.configure()
    before = getattr(settings, "rag_methods_identity_policy", "disabled")
    if enabled:
        from app.generation.methods_identity import POLICY
        settings.rag_methods_identity_policy = POLICY
    try:
        summary = compare_service(output / "service", freeze=False)
    finally:
        if enabled:
            settings.rag_methods_identity_policy = before
    files.verify(bindings)
    files.write(output / "bindings.json", bindings)
    files.write(output / "summary.json", {**summary, "policy_enabled": enabled})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--enabled", action="store_true")
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, freeze=args.freeze, enabled=args.enabled)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"regressions", "native_unsent"}}), flush=True)


if __name__ == "__main__":
    main()
