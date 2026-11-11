"""Separate bounded query-rewriting experiment; one native attempt per stage/case."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlencode

from scripts import gigachat_answer_smoke as f
from scripts import query_rewriting_experiment as qr
from scripts import run_satoh_fan_qa_20261110 as baseline

BASE = f.ROOT / "output/query_rewriting_20261110"
SCOPE = f.ROOT / "docs/records/query_rewriting_experiment_2026-11-10_v0.1.md"
TESTS = f.ROOT / "tests/unit/test_query_rewriting_experiment.py"
IDS = baseline.IDS
USER = "Вот давай как раз и сделаем это. на примере этих вопросов мы и проверим эгу гипотезу применения query rewriting"
KNOWN = baseline.KNOWN | {"rewrite_rejected", "identical_native_reuse"}


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


@contextmanager
def constants():
    with patch.object(baseline, "BASE", BASE), patch.object(baseline, "SCOPE", SCOPE), \
            patch.object(baseline, "VERSION", qr.VERSION), patch.object(baseline, "TESTS", TESTS), \
            patch.object(f, "PROTOCOL", SCOPE), patch.object(f, "VERSION", qr.VERSION):
        yield


def cases():
    f.verify_manifest(BASE / "input_freeze_v01")
    frozen = read(BASE / "input_freeze_v01/runtime.json")
    f.verify(frozen["input_bindings"])
    rows = read(BASE / "input_freeze_v01/questions.json")["cases"]
    if [c["id"] for c in rows] != list(IDS):
        raise ValueError("Case order changed")
    return rows


def initialize():
    settings = f.configure()
    if settings.rag_methods_identity_policy != "disabled":
        raise ValueError("Methods must stay disabled")
    rows = baseline.make_cases(read(baseline.PUBLIC))
    BASE.mkdir(exist_ok=False)
    freeze = BASE / "input_freeze_v01"
    freeze.mkdir()
    paths = [*f.ROOT.joinpath("app").rglob("*.py"), *f.ROOT.joinpath("app").rglob("*.yaml"),
             Path(__file__), Path(qr.__file__), Path(baseline.__file__), Path(f.__file__), TESTS, SCOPE, f.ROOT / "pyproject.toml"]
    bindings = f.bindings(paths)
    for source in paths:
        target = freeze / "source_snapshot" / source.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, source.read_bytes())
    for case in rows:
        if f.sha(Path(case["original_pdf_path"]).read_bytes()) != case["original_pdf_sha256"]:
            raise ValueError("Target PDF changed")
        folder = freeze / "rewrites" / case["id"]
        folder.mkdir(parents=True)
        f.save(folder / "request.json", qr.request(case, settings.rag_model))
        f.manifest(folder)
    f.write(freeze / "questions.json", {"version": qr.VERSION, "cases": rows, "references_included": False})
    f.write(freeze / "runtime.json", {"input_bindings": bindings, "raw_user_authorization": USER,
        "maximum_rewrite_attempts": 20, "maximum_answer_attempts": 20, "maximum_oauth_attempts": 40,
        "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "model": settings.rag_model, "max_output_tokens": 1200, "timeout_seconds": 120})
    f.manifest(freeze)
    return {"cases": 20, "new_model_calls": 0}


def rewrite(case, policy):
    if (BASE / "rewrite_closed_v01.json").exists():
        raise FileExistsError("Rewrite allowance closed")
    for previous in IDS[:IDS.index(case["id"])]:
        if read(BASE / "rewrites" / previous / "result.json")["status"] not in {"rewrite_valid", "rewrite_rejected", "transport_error"}:
            raise ValueError("Unknown preceding rewrite stops dispatch")
    settings = f.configure()
    expected = BASE / "input_freeze_v01/rewrites" / case["id"]
    digest = f.sha((expected / "request.json").read_bytes())
    folder = BASE / "rewrites" / case["id"]
    slot = f.reserve(digest, {"authorization": USER, "stage": "rewrite", "maximum_model_attempts": 1,
                              "output": str(folder), "request_sha256": digest})
    folder.mkdir(parents=True, exist_ok=False)
    obs = f.Observation(folder, settings, policy, expected)
    obs.result["status"] = "unhandled_or_interrupted"
    from app.generation.gigachat import AUTH_URL, CHAT_URL, _json
    from app.generation.providers import GenerationUnavailableError
    from app.generation.service import build_answer_provider

    provider = obs.instrument(build_answer_provider(settings))
    started = time.perf_counter()
    try:
        auth = _json(provider._post(AUTH_URL, urlencode({"scope": settings.gigachat_scope}).encode("ascii"),
                                   "Basic " + provider.credentials, oauth=True))
        token = auth.get("access_token") if isinstance(auth, dict) else None
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise GenerationUnavailableError("Invalid OAuth token")
        raw = provider._post(CHAT_URL, (expected / "request.json").read_bytes(), "Bearer " + token)
        plan = qr.parse_response(raw, case["question_original"])
        f.write(folder / "plan.json", plan)
        obs.result["status"] = "rewrite_valid"
    except ValueError as exc:
        obs.result.update(status="rewrite_rejected", error=str(exc))
    except GenerationUnavailableError as exc:
        obs.result.update(status="transport_error", error=str(exc))
    finally:
        response = folder / "response.bin"
        if response.is_file():
            try:
                envelope = _json(response.read_bytes())
            except (ValueError, UnicodeError):
                obs.result["native_metadata_parse_error"] = True
            else:
                if isinstance(envelope, dict):
                    obs.result.update(usage=envelope.get("usage"), returned_model=envelope.get("model"))
        obs.result.update(elapsed_seconds=time.perf_counter() - started, network_denials=policy.denied,
                          request_sha256=digest, stage="rewrite")
        f.write(folder / "result.json", obs.result)
        f.write(slot / "result.json", obs.result)
        f.write(slot / "rewrite_allowance_closed_v01.json", {"resend_authorized": False})
        f.manifest(folder)
    if obs.result["status"] == "unhandled_or_interrupted":
        raise RuntimeError("Internal rewrite failure; remaining scope must close")
    return {k: obs.result.get(k) for k in ("status", "model_attempts", "oauth_attempts", "usage", "error")}


def close_rewrites():
    rows = []
    for case in cases():
        path = BASE / "rewrites" / case["id"] / "result.json"
        digest = f.sha((BASE / "input_freeze_v01/rewrites" / case["id"] / "request.json").read_bytes())
        uncertain = not path.exists() and (f.LEDGER / digest).exists()
        result = read(path) if path.exists() else {"status": "unknown_reserved" if uncertain else "not_dispatched",
            "model_attempts": None if uncertain else 0, "oauth_attempts": None if uncertain else 0}
        rows.append({"id": case["id"], **result})
    f.write(BASE / "rewrite_closed_v01.json", {"cases": rows, "remaining_allowance": 0})
    return {"cases": len(rows), "statuses": [r["status"] for r in rows]}


def freeze_plans():
    """Require explicit per-question meaning decisions after inspection of all outputs."""
    closed = read(BASE / "rewrite_closed_v01.json")
    if closed["remaining_allowance"] != 0:
        raise ValueError("Rewrite stage must close before meaning review")
    decisions = read(BASE / "meaning_review_v01.json")
    if list(decisions) != list(IDS):
        raise ValueError("All twenty meaning decisions required in original order")
    rows = []
    for case in cases():
        folder = BASE / "rewrites" / case["id"]
        f.verify_manifest(folder)
        result = read(folder / "result.json")
        accepted = result["status"] == "rewrite_valid" and decisions[case["id"]]["accept"] is True
        plan = read(folder / "plan.json") if accepted else None
        if plan is not None:
            qr.validate(plan, case["question_original"])
        rows.append({"id": case["id"], "accepted": accepted, "plan": plan,
                     "decision": decisions[case["id"]], "rewrite_manifest_sha256": f.sha((folder / "manifest.json").read_bytes())})
    folder = BASE / "plans_freeze_v01"
    folder.mkdir()
    f.write(folder / "plans.json", {"cases": rows, "reviewer": "exposed_implementation_agent_not_independent"})
    f.write(folder / "bindings.json", f.bindings([BASE / "meaning_review_v01.json", BASE / "rewrite_closed_v01.json",
        *[p for cid in IDS for p in (BASE / "rewrites" / cid).iterdir() if p.is_file()]]))
    f.manifest(folder)
    return {"accepted": sum(r["accepted"] for r in rows), "cases": 20}


def plan_for(case):
    folder = BASE / "plans_freeze_v01"
    f.verify_manifest(folder)
    f.verify(read(folder / "bindings.json"))
    row = next(c for c in read(folder / "plans.json")["cases"] if c["id"] == case["id"])
    return row["plan"] if row["accepted"] else None


def prepare(case, policy, guard):
    plan = plan_for(case)
    if plan is None:
        folder = BASE / "prepared_v01" / case["id"]
        folder.mkdir(parents=True)
        f.write(folder / "rejected_rewrite.json", {"reason": "rewrite_validation_or_meaning_rejection", "model_calls": 0})
        f.manifest(folder)
        return {"status": "rewrite_rejected", "new_model_calls": 0}
    with qr.activate(case["question"], plan):
        result = baseline.prepare(case, policy, guard)
    return result


def contracts():
    result = {}
    for case in cases():
        folder = BASE / "prepared_v01" / case["id"]
        f.verify_manifest(folder)
        if (folder / "rejected_rewrite.json").exists():
            result[case["id"]] = None
            continue
        c = read(folder / "contract.json")
        f.verify(c["input_bindings"])
        if (c["case"] != case or c["model_calls"] or c["oauth_calls"] or c["transaction_read_only"] != "on"
                or c["transaction_end"] != "rollback" or c["network_denials"] or c["gold_read_denials"]):
            raise ValueError("Invalid prepared contract")
        if c["generation_reached"] and f.sha((folder / "request.json").read_bytes()) != c["request_sha256"]:
            raise ValueError("Frozen native changed")
        result[case["id"]] = c
    return result


def seal():
    cs = contracts()
    approval = {"raw_user_authorization": USER, "scope_sha256": f.sha(SCOPE.read_bytes()),
                "request_sha256": {cid: c["request_sha256"] if c else None for cid, c in cs.items()},
                "maximum_answer_attempts": 20, "retries": 0, "fallbacks": 0,
                "plan_manifest_sha256": f.sha((BASE / "plans_freeze_v01/manifest.json").read_bytes())}
    digests = [x for x in approval["request_sha256"].values() if x]
    if len(digests) != len(set(digests)):
        raise FileExistsError("Duplicate native requests within new scope")
    approval["identical_native_reuse"] = [cid for cid, d in approval["request_sha256"].items() if d and (f.LEDGER / d).exists()]
    f.write(BASE / "answer_approval_v01.json", approval)
    return {"eligible": len(digests), "identical_native_reuse": approval["identical_native_reuse"], "cases": 20}


def send(case, policy):
    if (BASE / "answers_closed_v01.json").exists():
        raise FileExistsError("Answer scope closed")
    for cid in IDS[:IDS.index(case["id"])]:
        if read(BASE / "answers" / cid / "result.json")["status"] not in KNOWN:
            raise RuntimeError("Earlier internal failure stops dispatch")
    cs, approval = contracts(), read(BASE / "answer_approval_v01.json")
    if (approval["raw_user_authorization"] != USER or approval["scope_sha256"] != f.sha(SCOPE.read_bytes())
            or approval["plan_manifest_sha256"] != f.sha((BASE / "plans_freeze_v01/manifest.json").read_bytes())
            or approval["request_sha256"] != {cid: c["request_sha256"] if c else None for cid, c in cs.items()}):
        raise ValueError("Approval drift")
    cid = case["id"]
    folder, original, c = BASE / "answers" / cid, BASE / "prepared_v01" / cid, cs[cid]
    folder.mkdir(parents=True, exist_ok=False)
    if c is None:
        result = {"status": "rewrite_rejected", "model_attempts": 0, "oauth_attempts": 0}
    elif not c["generation_reached"]:
        result = {"status": "gate_rejected", "model_attempts": 0, "oauth_attempts": 0,
                  "answer": read(original / "gate_response.json")["body"]}
    elif cid in approval["identical_native_reuse"]:
        result = {"status": "identical_native_reuse", "model_attempts": 0, "oauth_attempts": 0,
                  "request_sha256": c["request_sha256"], "meaning": "old_response_read_only_after_scope_closure"}
    else:
        approved = folder / "authorized_inputs"
        approved.mkdir()
        for p in original.iterdir():
            if p.name not in {"contract.json", "manifest.json"}:
                shutil.copyfile(p, approved / p.name)
        c = {**c, "authorization": USER, "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
             "input_bindings": {**c["input_bindings"], **f.bindings([*original.iterdir(),
                 BASE / "answer_approval_v01.json", BASE / "plans_freeze_v01/manifest.json"])}}
        f.write(approved / "contract.json", c)
        f.manifest(approved)
        with qr.activate(case["question"], plan_for(case)), patch.object(f, "QUESTION", case["question"]), \
                patch.object(f, "Observation", side_effect=lambda *a, **kw: baseline.ScopeObservation(*a, **kw, target=case)):
            result = f.send(approved, folder / "live", policy)
    f.write(folder / "result.json", result)
    if result["status"] not in KNOWN:
        raise RuntimeError("Internal answer outcome; stop and close remaining allowance")
    return {k: result.get(k) for k in ("status", "model_attempts", "oauth_attempts", "http_status", "usage")}


def close_answers():
    approval = read(BASE / "answer_approval_v01.json")
    rows = []
    for cid in IDS:
        folder = BASE / "answers" / cid
        path = folder / "result.json" if (folder / "result.json").exists() else folder / "live/result.json"
        digest = approval["request_sha256"][cid]
        slot = f.LEDGER / digest if digest else None
        unknown = not path.exists() and slot is not None and slot.exists()
        result = read(path) if path.exists() else {"status": "unknown_reserved" if unknown else "not_dispatched",
            "model_attempts": None if unknown else 0, "oauth_attempts": None if unknown else 0}
        row = {"id": cid, **result, "resend_authorized": False, "allowance_closed": True}
        if slot is not None and slot.exists() and cid not in approval["identical_native_reuse"]:
            f.write(slot / "query_rewriting_answer_closed_v01.json", row)
        rows.append(row)
    f.write(BASE / "answers_closed_v01.json", {"cases": rows, "remaining_allowance": 0})
    return {"cases": 20, "statuses": [r["status"] for r in rows]}


def run_all(mode):
    settings = f.configure()
    rows = []
    for case in cases():
        done = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "scripts.run_query_rewriting_20261110",
            mode, "--case-id", case["id"]], cwd=f.ROOT, capture_output=True, encoding="utf8", check=False)
        folder = BASE / "worker_logs" / case["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for name, value in (("stdout", done.stdout), ("stderr", done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, "[REDACTED]")
            f.save(folder / f"{mode}_{name}.txt", value.encode())
        row = {"id": case["id"], "returncode": done.returncode}
        if done.returncode == 0:
            row.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(row)
        print(json.dumps(row), flush=True)
        if done.returncode:
            break
    f.write(BASE / f"{mode}_batch_v01.json", {"cases": rows, "finished_all": len(rows) == 20 and not rows[-1]["returncode"]})
    if mode == "rewrite":
        close_rewrites()
    if mode == "send":
        close_answers()
    return {"stage": mode, "workers": len(rows), "finished": len(rows) == 20 and not rows[-1]["returncode"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "rewrite", "rewrite-all", "freeze-plans", "prepare", "prepare-all",
                                         "seal", "send", "send-all"))
    parser.add_argument("--case-id", choices=IDS)
    args = parser.parse_args()
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    with constants():
        guard = baseline.GoldReadGuard()
        if args.mode != "init":
            sys.addaudithook(guard)
        if args.mode == "init":
            result = initialize()
        elif args.mode.endswith("-all"):
            result = run_all(args.mode.removesuffix("-all"))
        elif args.mode == "freeze-plans":
            result = freeze_plans()
        elif args.mode == "seal":
            result = seal()
        else:
            if args.case_id is None:
                raise ValueError("Case required")
            case = next(c for c in cases() if c["id"] == args.case_id)
            result = rewrite(case, policy) if args.mode == "rewrite" else (
                prepare(case, policy, guard) if args.mode == "prepare" else send(case, policy))
        if policy.denied or guard.denied:
            raise RuntimeError("Forbidden network/reference read")
        print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
