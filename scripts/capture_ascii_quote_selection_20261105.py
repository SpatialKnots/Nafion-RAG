"""Question-only, read-only native ID preparation. There is no send mode."""

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import capture_reference_quote_runtime_20261105 as preparation
from scripts import gigachat_answer_smoke as files

PROTOCOL = files.ROOT / "docs/records/ascii_quote_selection_protocol_2026-11-05_v0.1.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("Q01", "Q05"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    original = files.source_inputs

    def bound_inputs(*args, **kwargs):
        return {**original(*args, **kwargs), **files.bindings([Path(__file__), PROTOCOL])}

    with patch.object(preparation, "PROTOCOL", PROTOCOL), patch.object(files, "source_inputs", bound_inputs):
        result = preparation.capture(args.case, args.output, policy)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
