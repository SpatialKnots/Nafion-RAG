"""Only new policy tests, offline; preserve every run and its input hashes."""

import argparse
import sys
from pathlib import Path

import pytest

from scripts import gigachat_answer_smoke as files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--no-http", action="store_true")
    args = parser.parse_args()
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__),
             files.ROOT / "tests/unit/test_methods_identity_runtime.py"]
    bindings = files.bindings(paths)
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    files.configure()
    tests = ["tests/unit/test_methods_identity_runtime.py", "-q", "-p", "no:cacheprovider",
             "--basetemp", str(args.basetemp), "--junitxml", str(args.junit)]
    if args.no_http:
        tests += ["-k", "not asgi"]
    code = pytest.main(tests)
    files.verify(bindings)
    files.write(args.junit.with_suffix(".scope.json"), {"exit_code": int(code), "external_network_denials": policy.denied,
                "inputs": bindings, "real_model_calls": 0, "real_oauth_calls": 0})
    if policy.denied:
        raise ValueError("External network attempted")
    sys.exit(code)


if __name__ == "__main__":
    main()
