"""Network-audited local regression runner; external connections are forbidden."""

import json
import sys

import pytest

from scripts.gigachat_answer_smoke import NetworkPolicy

if __name__ == "__main__":
    policy = NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    status = pytest.main(sys.argv[1:])
    print(json.dumps({"pytest_exit_code": int(status), "network_denials": policy.denied, "real_model_calls": 0}))
    raise SystemExit(1 if policy.denied else status)
