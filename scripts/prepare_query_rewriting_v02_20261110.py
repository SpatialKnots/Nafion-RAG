"""Reader-only canonical map ordering fix; preserve original runner/freeze/failure logs."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts import gigachat_answer_smoke as f
from scripts import query_rewriting_experiment as qr
from scripts import run_query_rewriting_20261110 as r


def freeze():
    if r.read(r.BASE / "rewrite_closed_v01.json")["remaining_allowance"]:
        raise ValueError("Rewrite scope must close")
    decisions = r.read(r.BASE / "meaning_review_v01.json")
    if set(decisions) != set(r.IDS):
        raise ValueError("Exactly twenty meaning decisions required")
    rows = []
    for case in r.cases():
        cid = case["id"]
        folder = r.BASE / "rewrites" / cid
        f.verify_manifest(folder)
        result = r.read(folder / "result.json")
        accepted = result["status"] == "rewrite_valid" and decisions[cid]["accept"] is True
        plan = r.read(folder / "plan.json") if accepted else None
        if plan:
            qr.validate(plan, case["question_original"])
        rows.append({"id": cid, "accepted": accepted, "plan": plan, "decision": decisions[cid],
                     "rewrite_manifest_sha256": f.sha((folder / "manifest.json").read_bytes())})
    folder = r.BASE / "plans_freeze_v01"
    folder.mkdir(exist_ok=False)
    f.write(folder / "plans.json", {"cases": rows, "reviewer": "exposed_implementation_agent_not_independent",
        "reader_adapter": "canonical decision map ordered by frozen case IDs; no plan/decision changes"})
    f.write(folder / "bindings.json", f.bindings([Path(__file__), r.BASE / "meaning_review_v01.json",
        r.BASE / "rewrite_closed_v01.json", *[p for cid in r.IDS for p in (r.BASE / "rewrites" / cid).iterdir() if p.is_file()]]))
    f.manifest(folder)
    return {"cases": 20, "accepted": sum(row["accepted"] for row in rows)}


def prepare_all():
    rows = []
    settings = f.configure()
    for case in r.cases():
        done = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "scripts.run_query_rewriting_20261110",
                               "prepare", "--case-id", case["id"]], cwd=f.ROOT,
                              capture_output=True, encoding="utf8", check=False)
        folder = r.BASE / "worker_logs_prepare_v02" / case["id"]
        folder.mkdir(parents=True, exist_ok=False)
        for name, value in (("stdout", done.stdout), ("stderr", done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, "[REDACTED]")
            f.save(folder / (name + ".txt"), value.encode())
        row = {"id": case["id"], "returncode": done.returncode}
        if not done.returncode:
            row.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(row)
        print(json.dumps(row), flush=True)
        if done.returncode:
            break
    value = {"cases": rows, "finished_all": len(rows) == 20 and not rows[-1]["returncode"], "new_model_calls": 0}
    f.write(r.BASE / "prepare_batch_v02.json", value)
    return {"finished_all": value["finished_all"], "new_model_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "prepare-all"))
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    with r.constants():
        guard = r.baseline.GoldReadGuard()
        sys.addaudithook(guard)
        value = freeze() if args.mode == "freeze" else prepare_all()
        if policy.denied or guard.denied:
            raise RuntimeError("Forbidden network/reference access")
    print(json.dumps(value))
