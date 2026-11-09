"""Fresh Q03 read-only preparation, stopped before external transport; no send mode."""

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import capture_reference_quote_runtime_20261105 as preparation
from scripts import gigachat_answer_smoke as files

PROTOCOL = files.ROOT / "docs/records/condition_context_completion_amendment_2026-11-06_v0.2.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    original = files.source_inputs

    def bound_inputs(*a, **kw):
        return {**original(*a, **kw), **files.bindings([Path(__file__), PROTOCOL])}

    with patch.object(preparation, "PROTOCOL", PROTOCOL), patch.object(files, "source_inputs", bound_inputs):
        result = preparation.capture("Q03", args.output, policy)
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
