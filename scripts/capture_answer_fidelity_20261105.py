"""Fresh read-only preparations; no send mode or external transport."""

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import capture_reference_quote_runtime_20261105 as preparation
from scripts import gigachat_answer_smoke as files

PROTOCOL = files.ROOT / "docs/records/answer_fidelity_protocol_2026-11-05_v0.1.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("Q02", "Q04"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    original = files.source_inputs

    def bound_inputs(*a, **kw):
        return {**original(*a, **kw), **files.bindings([Path(__file__), PROTOCOL])}

    with patch.object(preparation, "PROTOCOL", PROTOCOL), patch.object(files, "source_inputs", bound_inputs):
        value = preparation.capture(args.case, args.output, policy)
    print(json.dumps(value, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
