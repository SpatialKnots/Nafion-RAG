"""Affected tests with external-network denial; no real model/OAuth scope."""

import argparse
import json
import sys
from pathlib import Path

import pytest

from scripts import gigachat_answer_smoke as files
from scripts.test_structured_answers_20261105 import TEST_FILES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--basetemp", type=Path, required=True)
    args = parser.parse_args()
    paths = [files.ROOT / "tests/unit" / name for name in (*TEST_FILES, "test_context_completion.py",
             "test_condition_context_service.py", "test_source_paraphrases.py")]
    bindings = files.bindings([*paths, Path(__file__)])
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    files.configure()
    code = pytest.main([*[str(p) for p in paths], "-q", "-p", "no:cacheprovider",
                       "--basetemp", str(args.basetemp), "--junitxml", str(args.junit)])
    files.verify(bindings)
    files.write(args.junit.with_suffix(".scope.json"), {"external_network_denials": policy.denied,
                "new_live_authorization": False, "test_bindings": bindings, "exit_code": int(code)})
    if policy.denied:
        raise ValueError("Unexpected external network attempt in tests")
    print(json.dumps({"exit_code": int(code), "external_network_denials": []}), flush=True)
    sys.exit(code)


if __name__ == "__main__":
    main()
