"""Fresh read-only production search for the two repaired question families."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

from scripts import benchmark_retrieval_capture_20261105 as capture
from scripts import gigachat_answer_smoke as files

PROTOCOL = files.ROOT / "docs/records/requested_context_runtime_protocol_2026-11-05_v0.1.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("Q03", "Q04"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    with patch.object(capture, "PROTOCOL", PROTOCOL):
        result = capture.capture(args.case, args.output, policy)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
