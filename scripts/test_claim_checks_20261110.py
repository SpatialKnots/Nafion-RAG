"""Offline claim-check and affected tests with an external-network denial guard."""

import argparse
import sys
from pathlib import Path

import pytest

from scripts import gigachat_answer_smoke as files
from scripts.test_answer_requirements_20261109 import EXTRA
from scripts.test_structured_answers_20261105 import TEST_FILES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--new-only", action="store_true")
    args = parser.parse_args()
    names = ("test_claim_checks.py",) if args.new_only else (*TEST_FILES, *EXTRA,
        "test_answer_evidence_packet.py", "test_bounded_context_action.py", "test_claim_checks.py")
    paths = [files.ROOT / "tests/unit" / name for name in names]
    bindings = files.bindings([*paths, Path(__file__), files.ROOT / "output/answer_requirements_20261109/controls_v01.json"])
    app_bindings = files.bindings([*files.ROOT.joinpath("app").rglob("*.py")])
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    files.configure()
    code = pytest.main([*[str(p) for p in paths], "-q", "-p", "no:cacheprovider", "--tb=short",
                       "--basetemp", str(args.basetemp), "--junitxml", str(args.junit)])
    files.verify(bindings)
    files.verify(app_bindings)
    files.write(args.junit.with_suffix(".scope.json"), {"exit_code": int(code), "test_bindings": bindings,
                "app_bindings": app_bindings, "external_network_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    sys.exit(code)


if __name__ == "__main__":
    main()
