"""Declared harness correction: permit hashing the source-only corpus inventory."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts import prepare_fan_doi_besenhard_20261113 as prep

f = prep.f
EXECUTION = prep.BASE / "execution_overlay_v02"


class InventoryHashGuard(prep.ReferenceGuard):
    def __call__(self, event, args):
        if event == "open" and not isinstance(args[0], int):
            path = Path(prep.os.fsdecode(args[0])).resolve()
            if path == prep.INVENTORY.resolve():
                return
        return super().__call__(event, args)


def initialize():
    prep.verify_runtime()
    EXECUTION.mkdir(exist_ok=False)
    f.write(EXECUTION / "correction.json", {
        "failed_attempt": str(prep.BASE / "worker_logs_v01/F1/stderr.txt"),
        "failure": "Reference guard denied source-only inventory during frozen binding hash verification",
        "application_or_question_changes": False, "prior_freeze_rewritten": False,
        "correction": "Allow exactly the pinned inventory path for hash verification; no inventory parse in worker",
        "extra_allowed_path": str(prep.INVENTORY), "new_model_calls": 0, "new_oauth_calls": 0})
    f.save(EXECUTION / "executed_script.py", Path(__file__).read_bytes())
    f.write(EXECUTION / "bindings.json", f.bindings([Path(__file__),
        f.ROOT / "tests/unit/test_fan_doi_besenhard_inventory_guard.py"]))
    f.manifest(EXECUTION)
    return {"harness_overlay": "v02", "application_changes": 0}


def verify():
    f.verify_manifest(EXECUTION)
    f.verify(prep.read(EXECUTION / "bindings.json"))


def batch():
    verify()
    rows = []
    for case in prep.verify_runtime():
        folder = prep.BASE / "worker_logs_v02" / case["id"]
        folder.mkdir(parents=True, exist_ok=False)
        done = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", __spec__.name,
                               "prepare", "--case-id", case["id"]], cwd=f.ROOT,
                              capture_output=True, text=True, encoding="utf-8", check=False, timeout=240)
        settings = f.configure()
        for name, value in (("stdout", done.stdout), ("stderr", done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, "[REDACTED]")
            f.save(folder / (name + ".txt"), value.encode())
        row = {"id": case["id"], "exit_code": done.returncode}
        if done.returncode == 0:
            row.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(row)
        print(json.dumps(row), flush=True)
        if done.returncode:
            break
    result = {"cases": rows, "finished_all": len(rows) == 30 and all(r["exit_code"] == 0 for r in rows)}
    f.write(prep.BASE / "preparation_batch_v02.json", result)
    return {"finished_all": result["finished_all"], "workers": len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "prepare", "prepare-all"))
    parser.add_argument("--case-id", choices=prep.IDS)
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "init":
        result = initialize()
    elif args.mode == "prepare-all":
        result = batch()
    else:
        verify()
        case = next(c for c in prep.verify_runtime() if c["id"] == args.case_id)
        guard = InventoryHashGuard()
        sys.addaudithook(guard)
        result = prep.prepare(case, policy, guard)
    prep.require(not policy.denied, "Forbidden network")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
