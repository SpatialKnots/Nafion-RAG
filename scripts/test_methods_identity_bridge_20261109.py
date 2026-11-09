"""Only new read-only audit tests; original app sources must remain byte-identical."""

import argparse
import json
import sys
from pathlib import Path

import pytest

from scripts import gigachat_answer_smoke as files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", required=True, type=Path)
    args = parser.parse_args()
    source = files.ROOT / "output/methods_identity_bridge_20261109/probe_v01/bindings.json"
    previous = json.loads(source.read_bytes())
    app = {p: d for p, d in previous.items() if Path(p).is_relative_to(files.ROOT / "app")}
    files.verify(app)
    inputs = files.bindings([files.ROOT / "scripts/methods_identity_bridge_20261109.py", Path(__file__),
        files.ROOT / "scripts/methods_bridge_controls_20261109.py", files.ROOT / "tests/unit/test_methods_identity_bridge.py",
        files.ROOT / "output/methods_identity_bridge_20261109/controls_v02.json"])
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    code = pytest.main(["tests/unit/test_methods_identity_bridge.py", "-q", "-p", "no:cacheprovider", "--junitxml", str(args.junit)])
    files.verify(app)
    files.verify(inputs)
    files.write(args.junit.with_suffix(".scope.json"), {"exit_code": int(code), "external_network_denials": policy.denied,
        "unchanged_app_bindings": app, "input_bindings": inputs, "old_full_suite_rerun": False})
    if policy.denied:
        raise ValueError("External network attempted")
    sys.exit(code)


if __name__ == "__main__":
    main()
