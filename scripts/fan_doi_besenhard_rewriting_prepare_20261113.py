"""Read-only answer preparation with stable baseline hash-read permissions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import fan_doi_besenhard_rewriting_20261113 as r

f = r.f
OLD_FREEZE = r.baseline.FREEZE.resolve()
OLD_PREPARED = (r.baseline.BASE / "prepared_v01").resolve()
EXTENSION = r.BASE / "execution_prepare_v01"
TESTS = f.ROOT / "tests/unit/test_rewriting_preparation_guard.py"


class StableReferenceGuard(r.ReferenceGuard):
    def __call__(self, event, args):
        if event == "open" and not isinstance(args[0], int):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.is_relative_to(OLD_FREEZE) or path.is_relative_to(OLD_PREPARED):
                return
        return super().__call__(event, args)


def initialize():
    r.cases()
    f.verify_manifest(r.BASE / "plans_freeze_v01")
    EXTENSION.mkdir(exist_ok=False)
    f.write(EXTENSION / "bindings.json", f.bindings([Path(__file__), TESTS,
        r.BASE / "preparation_guard_probe_v01.json", r.BASE / "plans_freeze_v01/manifest.json"]))
    f.write(EXTENSION / "correction.json", {
        "issue": "frozen profile temporarily patches baseline module constants during preparation",
        "probe": "original baseline hash-read permissions disappear under those temporary constants",
        "correction": "capture original input-freeze/prepared roots before activation; permit their hash reads",
        "references_or_assessment_reads_allowed": False,
        "scientific_or_application_changes": False, "original_frozen_files_rewritten": False,
        "old_freeze": str(OLD_FREEZE), "old_prepared": str(OLD_PREPARED)})
    f.save(EXTENSION / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(EXTENSION)
    return {"preparation_extension": "stable_read_permissions_v01", "model_calls": 0}


def verify():
    f.verify_manifest(EXTENSION)
    f.verify(r.read(EXTENSION / "bindings.json"))


def batch():
    verify()
    rows = []
    for case in r.cases():
        folder = r.BASE / "worker_logs_prepare_v01" / case["id"]
        folder.mkdir(parents=True, exist_ok=False)
        done = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", __spec__.name,
                               "prepare", "--case-id", case["id"]], cwd=f.ROOT,
                              capture_output=True, text=True, encoding="utf-8", check=False)
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
    result = {"cases": rows, "finished_all": len(rows) == 30 and all(c["exit_code"] == 0 for c in rows),
              "new_answer_model_calls": 0, "new_oauth_calls": 0}
    f.write(r.BASE / "prepare_batch_v01.json", result)
    return {"finished_all": result["finished_all"], "cases": len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "prepare", "prepare-all"))
    parser.add_argument("--case-id", choices=r.baseline.IDS)
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "init":
        result = initialize()
    elif args.mode == "prepare-all":
        result = batch()
    else:
        verify()
        r.baseline.require(args.case_id is not None, "Case required")
        case = next(c for c in r.cases() if c["id"] == args.case_id)
        guard = StableReferenceGuard()
        sys.addaudithook(guard)
        result = r.prepare(case, policy, guard)
        r.baseline.require(not guard.denied, "Forbidden reference read")
    r.baseline.require(not policy.denied, "Forbidden network")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
