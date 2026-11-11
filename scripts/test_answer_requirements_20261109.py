"""Offline requirement-map tests plus prior affected scope; external network denied."""

import argparse
import sys
from pathlib import Path

import pytest

from scripts import gigachat_answer_smoke as files
from scripts.test_structured_answers_20261105 import TEST_FILES

EXTRA = ("test_context_completion.py", "test_condition_context_service.py", "test_source_paraphrases.py",
    "test_natural_source_grammar.py", "test_source_role_assembly.py", "test_methods_identity_bridge.py",
    "test_methods_identity_runtime.py", "test_answer_preparation.py", "test_bibliography_api.py",
    "test_block_preparation.py", "test_risk_preparation.py", "test_answer_requirements.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--new-only", action="store_true")
    args = parser.parse_args()
    paths = [files.ROOT / "tests/unit" / name for name in (("test_answer_requirements.py",) if args.new_only else (*TEST_FILES, *EXTRA))]
    bindings = files.bindings([*paths, Path(__file__), files.ROOT / "output/answer_requirements_20261109/controls_v01.json"])
    app_bindings = files.bindings([*files.ROOT.joinpath("app").rglob("*.py")])
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    files.configure()
    code = pytest.main([*[str(p) for p in paths], "-q", "-p", "no:cacheprovider", "--tb=short",
                       "--basetemp", str(args.basetemp), "--junitxml", str(args.junit)])
    files.verify(bindings)
    files.verify(app_bindings)
    files.write(args.junit.with_suffix(".scope.json"), {"exit_code": int(code), "external_network_denials": policy.denied,
                "test_bindings": bindings, "app_bindings": app_bindings, "real_model_calls": 0, "real_oauth_exchanges": 0})
    if policy.denied:
        raise ValueError("External network attempted")
    sys.exit(code)


if __name__ == "__main__":
    main()
