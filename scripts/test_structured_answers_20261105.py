"""Affected tests with an external-network audit guard; no live model scope."""

import argparse
import json
import sys
from pathlib import Path

import pytest

from scripts import gigachat_answer_smoke as files

TEST_FILES = (
    "test_answer_facts.py", "test_answer_fidelity.py", "test_ascii_quote_selection.py", "test_ascii_baseline_snapshot.py",
    "test_reference_quotes.py", "test_source_reference.py", "test_reference_quote_service.py", "test_requested_context.py",
    "test_requested_context_service.py", "test_benchmark_retrieval_replay_20261105.py", "test_explicit_reference_retrieval_20261105.py",
    "test_generation.py", "test_evidence_retention.py", "test_reranking.py", "test_retrieval_ablation_labels.py",
    "test_user_benchmark_comparison_20261104.py", "test_gigachat_generation.py", "test_answer_presentation.py",
    "test_ui_routes.py", "test_structured_facts.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--basetemp", type=Path, required=True)
    args = parser.parse_args()
    paths = [files.ROOT / "tests/unit" / name for name in TEST_FILES]
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
        raise ValueError("Unexpected external-network attempt in tests")
    print(json.dumps({"exit_code": int(code), "external_network_denials": []}), flush=True)
    sys.exit(code)


if __name__ == "__main__":
    main()
