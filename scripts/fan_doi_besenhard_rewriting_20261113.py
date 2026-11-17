"""Explicit rewriting-v0.2 profile for the frozen thirty-question comparison."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz

from scripts import prepare_fan_doi_besenhard_20261113 as baseline
from scripts import query_rewriting_experiment as qr_old
from scripts import query_rewriting_v02 as qr
from scripts import run_query_rewriting_20261110 as engine

f = baseline.f
BASE = f.ROOT / "output/fan_doi_besenhard_rewriting_20261113"
FREEZE = BASE / "input_freeze_v01"
PROTOCOL = f.ROOT / "docs/records/fan_doi_besenhard_rewriting_2026-11-13_v0.1.md"
LEDGER = f.ROOT / "data/experiments/fan_doi_besenhard_rewriting_20261113"
TESTS = f.ROOT / "tests/unit/test_fan_doi_besenhard_rewriting.py"
TITLE_PATTERNS = {
    "Fan": (1, r"Non-flammable electrolyte enables Li-metal\s+batteries with aggressive cathode chemistries"),
    "Doi": (2, r"Fluoroalkyl Ether-diluted Dimethyl Carbonate-based Electrolyte\s+"
            r"Solutions for High-voltage Operation of LiNi0\.5Co0\.2Mn0\.3O2\s+Electrodes in Lithium Ion Batteries"),
    "Besenhard": (1, r"Advances in Battery Technology: Rechargeable\s+Magnesium Batteries and Novel Negative-\s*"
                  r"Electrode Materials for Lithium Ion Batteries"),
}


def read(path):
    return json.loads(path.read_bytes())


def title_context(paper, page_number, pattern):
    path = Path(paper["original_pdf_path"])
    baseline.require(f.sha(path.read_bytes()) == paper["original_pdf_sha256"], "Original PDF changed")
    with fitz.open(path) as pdf:
        text = pdf[page_number - 1].get_text("text")
    matches = list(re.finditer(pattern, text))
    baseline.require(len(matches) == 1, "Scientific title absent or ambiguous")
    match = matches[0]
    title = re.sub(r"\s+", " ", match[0]).strip()
    context = {"article_id": paper["article_id"], "title": title,
               "title_sha256": f.sha(title.encode()), "original_pdf_sha256": paper["original_pdf_sha256"]}
    qr.context_valid(context)
    return context, {"pdf_page": page_number, "page_text_sha256": f.sha(text.encode()),
                     "start": match.start(), "end": match.end(), "raw_title": match[0], "page_text": text,
                     "original_pdf_path": str(path)}


def initialize():
    baseline.require(not BASE.exists(), "Comparison already initialized")
    rows = baseline.verify_runtime()
    settings = f.configure()
    contexts, proofs = {}, {}
    for label, (page, pattern) in TITLE_PATTERNS.items():
        case = next(c for c in rows if c["label"] == label)
        contexts[label], proofs[label] = title_context(case, page, pattern)
    paths = [*baseline.app_paths(), f.ROOT / "pyproject.toml", Path(__file__), TESTS, PROTOCOL,
             Path(qr.__file__), Path(qr_old.__file__), Path(engine.__file__), Path(f.__file__),
             Path(baseline.__file__), Path(baseline.route.__file__),
             f.ROOT / "docs/cross_lingual_glossary.yaml", baseline.FREEZE / "questions.json",
             baseline.FREEZE / "manifest.json"]
    paths += [Path(c["original_pdf_path"]) for c in rows]
    baseline_paths = []
    for case in rows:
        folder = baseline.BASE / "prepared_v01" / case["id"]
        f.verify_manifest(folder)
        baseline_paths += [folder / "contract.json", folder / "manifest.json"]
    bindings = f.bindings(paths + baseline_paths)
    FREEZE.mkdir(parents=True)
    f.write(FREEZE / "questions.json", {"cases": rows, "references_included": False})
    f.write(FREEZE / "bindings.json", bindings)
    f.write(FREEZE / "title_contexts.json", {"contexts": contexts, "proofs": proofs})
    requests = []
    for case in rows:
        folder = FREEZE / "rewrites" / case["id"]
        folder.mkdir(parents=True)
        native = qr.request(case, settings.rag_model, contexts[case["label"]])
        baseline.require(len(native) <= 100000, "Rewrite request exceeds review ceiling")
        f.save(folder / "request.json", native)
        f.manifest(folder)
        requests.append({"id": case["id"], "request_sha256": f.sha(native), "request_bytes": len(native)})
    f.write(FREEZE / "runtime.json", {"version": qr.VERSION, "input_bindings": bindings,
        "raw_user_instruction": "Подключи метод", "registered_cases": 30,
        "profile": "explicit_isolated_process_rewriting_v02; same experimental required-fields API",
        "model": settings.rag_model, "max_output_tokens": 1200, "per_http_timeout_seconds": 120,
        "prospective_rewrite_model_limit": 30, "prospective_rewrite_oauth_limit": 30,
        "current_live_allowance": 0, "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "answer_live_scope": "not_opened; review exact native requests after rewriting/meaning review",
        "baseline_preserved": str(baseline.BASE), "source_level_independence": "not_established",
        "implementation_assistant_exposed_to_references": True, "scientific_accuracy": None,
        "actual_cost": None, "rewrite_requests": requests})
    f.save(FREEZE / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(FREEZE)
    return {"cases": 30, "verified_titles": len(contexts), "rewrite_requests": len(requests),
            "total_request_bytes": sum(r["request_bytes"] for r in requests), "model_calls": 0, "oauth_calls": 0}


def cases():
    f.verify_manifest(FREEZE)
    f.verify(read(FREEZE / "bindings.json"))
    rows = read(FREEZE / "questions.json")["cases"]
    baseline.require([c["id"] for c in rows] == baseline.IDS, "Question identities/order changed")
    baseline.require({str(p.resolve()) for p in baseline.app_paths()}
                     == {p for p in read(FREEZE / "bindings.json") if Path(p).is_relative_to(f.ROOT / "app")},
                     "Application file set changed")
    return rows


class ReferenceGuard:
    def __init__(self):
        self.denied = []

    def __call__(self, event, args):
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        allowed_output = (path.is_relative_to(BASE) and not any(
            part.startswith(("review_", "assessment_", "private_")) for part in path.relative_to(BASE).parts))
        allowed_old = (path.is_relative_to(baseline.FREEZE) or path.is_relative_to(baseline.BASE / "prepared_v01")
                       or path == baseline.INVENTORY)
        forbidden = (path == baseline.USER_FILE or path.name.casefold().startswith("ariadne_qa_")
                     or path.is_relative_to(baseline.PRIVATE))
        if path.is_relative_to(f.ROOT / "output"):
            forbidden |= not (allowed_output or allowed_old)
        if path.is_relative_to(f.ROOT / "docs/records"):
            forbidden |= path not in {PROTOCOL, baseline.PROTOCOL}
        if forbidden:
            self.denied.append(str(path))
            raise PermissionError("Rewriting worker cannot read reference or assessment files")


def authorize(instruction):
    rows = cases()
    baseline.require(bool(instruction.strip()), "An actual new user authorization is required")
    baseline.require(not (BASE / "rewrite_closed_v01.json").exists(), "Closed scope cannot reopen")
    f.write(BASE / "rewrite_authorization_v01.json", {"raw_user_authorization": instruction,
        "scope_sha256": f.sha(PROTOCOL.read_bytes()), "freeze_sha256": f.sha((FREEZE / "manifest.json").read_bytes()),
        "case_ids": [c["id"] for c in rows], "maximum_rewrite_attempts": 30, "maximum_oauth_attempts": 30,
        "automatic_retries": 0, "answer_authorization": False})
    return {"maximum_rewrite_attempts": 30, "maximum_oauth_attempts": 30, "answer_authorization": False}


@contextmanager
def rewrite_environment():
    rows = cases()
    authorization = read(BASE / "rewrite_authorization_v01.json")
    baseline.require(authorization["scope_sha256"] == f.sha(PROTOCOL.read_bytes())
        and authorization["freeze_sha256"] == f.sha((FREEZE / "manifest.json").read_bytes())
        and authorization["case_ids"] == baseline.IDS
        and authorization["maximum_rewrite_attempts"] == authorization["maximum_oauth_attempts"] == 30
        and authorization["answer_authorization"] is False, "Rewrite authorization differs from frozen scope")
    contexts = read(FREEZE / "title_contexts.json")["contexts"]
    by_question = {c["question_original"]: contexts[c["label"]] for c in rows}
    facade = SimpleNamespace(parse_response=lambda raw, question: qr.parse_response(raw, question, by_question[question]))
    with patch.object(engine, "BASE", BASE), patch.object(engine, "SCOPE", PROTOCOL), \
            patch.object(engine, "IDS", baseline.IDS), patch.object(engine, "cases", cases), \
            patch.object(engine, "qr", facade), patch.object(engine, "USER", authorization["raw_user_authorization"]), \
            patch.object(f, "LEDGER", LEDGER), patch.object(f, "VERSION", qr.VERSION):
        yield


def freeze_plans():
    rows = cases()
    f.verify_manifest(BASE / "rewrite_closed_v01")
    f.verify(read(BASE / "rewrite_closed_v01/bindings.json"))
    closed = read(BASE / "rewrite_closed_v01.json")
    baseline.require(closed["remaining_allowance"] == 0, "Rewrite stage must close first")
    decisions = read(BASE / "meaning_review_v01.json")
    baseline.require(set(decisions) == set(baseline.IDS), "Meaning review required for all thirty cases")
    plans, bound_paths = [], [BASE / "meaning_review_v01.json", BASE / "rewrite_closed_v01.json"]
    for case in rows:
        folder = BASE / "rewrites" / case["id"]
        result = read(folder / "result.json") if (folder / "result.json").exists() else None
        if result is not None:
            f.verify_manifest(folder)
            bound_paths += list(p for p in folder.iterdir() if p.is_file())
        decision = decisions[case["id"]]
        baseline.require(type(decision.get("accept")) is bool and isinstance(decision.get("reason"), str)
                         and bool(decision["reason"].strip()), "Missing explicit meaning decision")
        plan = read(folder / "plan.json") if result and result["status"] == "rewrite_valid" else None
        baseline.require(not decision["accept"] or plan is not None, "Cannot accept missing/invalid rewrite")
        if plan is not None:
            qr.validate(plan, case["question_original"])
        plans.append({"id": case["id"], "accepted": decision["accept"],
                      "plan": plan if decision["accept"] else None, "decision": decision})
    folder = BASE / "plans_freeze_v01"
    folder.mkdir(exist_ok=False)
    f.write(folder / "plans.json", {"cases": plans, "reviewer": "exposed_implementation_agent_not_independent"})
    f.write(folder / "bindings.json", f.bindings(bound_paths))
    f.manifest(folder)
    return {"cases": len(plans), "accepted": sum(r["accepted"] for r in plans)}


def load_plan(case):
    folder = BASE / "plans_freeze_v01"
    f.verify_manifest(folder)
    f.verify(read(folder / "bindings.json"))
    row = next(r for r in read(folder / "plans.json")["cases"] if r["id"] == case["id"])
    if not row["accepted"]:
        return None
    plan = qr.validate(row["plan"], case["question_original"])
    baseline.require(plan["article_context"]["article_id"] == case["article_id"]
                     and plan["article_context"]["original_pdf_sha256"] == case["original_pdf_sha256"], "Plan article drift")
    return plan


@contextmanager
def activate(case, plan):
    """A fresh worker confines the historical adapter's patches to one request."""
    qr.validate(plan, case["question_original"])
    baseline.require(plan["article_context"]["article_id"] == case["article_id"]
                     and plan["article_context"]["original_pdf_sha256"] == case["original_pdf_sha256"], "Plan article drift")
    with qr.activate(case["question"], plan):
        yield


def prepare(case, policy, guard):
    plan = load_plan(case)
    if plan is None:
        folder = BASE / "prepared_v01" / case["id"]
        folder.mkdir(parents=True, exist_ok=False)
        f.write(folder / "rewrite_rejected.json", {"id": case["id"], "model_calls": 0,
                                                  "reason": "rewrite_or_meaning_review_rejected"})
        f.manifest(folder)
        return {"id": case["id"], "status": "rewrite_rejected"}
    with patch.object(baseline, "BASE", BASE), patch.object(baseline, "FREEZE", FREEZE), \
            patch.object(baseline, "PROTOCOL", PROTOCOL), activate(case, plan):
        result = baseline.prepare(case, policy, guard)
    load_plan(case)
    folder = BASE / "answer_plan_bindings_v01" / case["id"]
    folder.mkdir(parents=True, exist_ok=False)
    f.write(folder / "bindings.json", f.bindings([BASE / "plans_freeze_v01/manifest.json",
        BASE / "plans_freeze_v01/plans.json", BASE / "prepared_v01" / case["id"] / "manifest.json"]))
    f.manifest(folder)
    return result


def rewrite_all():
    outcomes = []
    with rewrite_environment():
        try:
            for case in cases():
                log = BASE / "worker_logs_v01" / case["id"]
                log.mkdir(parents=True, exist_ok=False)
                result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", __spec__.name,
                                         "rewrite", "--case-id", case["id"]], cwd=f.ROOT,
                                        capture_output=True, text=True, encoding="utf-8", check=False)
                settings = f.configure()
                for name, value in (("stdout", result.stdout), ("stderr", result.stderr)):
                    for secret in (settings.gigachat_credentials, settings.database_url):
                        if secret:
                            value = value.replace(secret, "[REDACTED]")
                    f.save(log / (name + ".txt"), value.encode())
                row = {"id": case["id"], "exit_code": result.returncode}
                if result.returncode == 0:
                    row.update(json.loads(result.stdout.strip().splitlines()[-1]))
                outcomes.append(row)
                print(json.dumps(row), flush=True)
                if result.returncode or row.get("status") == "transport_error":
                    break
        finally:
            engine.close_rewrites()
            closure = BASE / "rewrite_closed_v01"
            closure.mkdir(exist_ok=False)
            f.write(closure / "bindings.json", f.bindings([BASE / "rewrite_closed_v01.json"]))
            f.manifest(closure)
    f.write(BASE / "rewrite_batch_v01.json", {"cases": outcomes, "remaining_allowance": 0})
    return {"workers": len(outcomes), "remaining_allowance": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "authorize-rewrites", "rewrite", "rewrite-all", "freeze-plans", "prepare"))
    parser.add_argument("--case-id", choices=baseline.IDS)
    parser.add_argument("--user-instruction")
    args = parser.parse_args()
    policy, guard = f.NetworkPolicy(), ReferenceGuard()
    sys.addaudithook(policy)
    if args.mode != "init":
        sys.addaudithook(guard)
    if args.mode == "init":
        result = initialize()
    elif args.mode == "authorize-rewrites":
        baseline.require(args.user_instruction is not None, "Actual authorization text required")
        result = authorize(args.user_instruction)
    elif args.mode == "rewrite-all":
        result = rewrite_all()
    elif args.mode == "freeze-plans":
        result = freeze_plans()
    else:
        baseline.require(args.case_id is not None, "Case ID required")
        case = next(c for c in cases() if c["id"] == args.case_id)
        if args.mode == "rewrite":
            with rewrite_environment():
                result = engine.rewrite(case, policy)
        else:
            result = prepare(case, policy, guard)
    baseline.require(not policy.denied and not guard.denied, "Forbidden network/reference access")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
