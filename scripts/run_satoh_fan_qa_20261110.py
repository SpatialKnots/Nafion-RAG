"""One bounded twenty-question production check; fresh processes and no automatic retries."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts import gigachat_answer_smoke as files

ROOT = files.ROOT
BASE = ROOT / "output/satoh_fan_qa_run_20261110"
SCOPE = ROOT / "docs/records/satoh_fan_qa_run_scope_2026-11-10_v0.1.md"
PUBLIC = ROOT / "output/satoh_fan_qa_20261110/intake_v02/questions_only.json"
TESTS = ROOT / "tests/unit/test_satoh_fan_qa_run.py"
VERSION = "satoh_fan_production_check_v0.1"
IDS = tuple(f"{label}_{i:02}" for label in ("Satoh", "Fan") for i in range(1, 11))
KNOWN = {"runtime_answered", "runtime_http_error", "provider_abstained", "gate_rejected"}
PDFS = {"Satoh": ROOT / "data/pdf/6689166e7e160336_Satoh_2013.pdf", "Fan": ROOT / "data/pdf/59bfbd00f345b750_Fan_2018.pdf"}
IDENTITIES = {
    "Satoh": ("58254395-e523-498c-96e5-4b9acaf3640d", "6689166e7e16033604a1e701b49813ab9f53ca3705d5dddf1a433f324edad12e"),
    "Fan": ("b867282d-52ba-4b92-91a4-664693cdcf0b", "59bfbd00f345b750c812985c2cb38d9e3ac45e39858d82c542a292d7f810119c"),
}


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


class GoldReadGuard:
    def __init__(self) -> None:
        self.denied: list[str] = []

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if path == SCOPE.resolve() or path.is_relative_to(BASE.resolve()):
            return
        forbidden = (path.name.casefold() == "ariadne_qa_satoh_2013_fan_2018.md"
                     or path.is_relative_to(ROOT / "output") or path.is_relative_to(ROOT / "docs/records"))
        if forbidden:
            self.denied.append(str(path))
            raise PermissionError("Reference/prior review reads are forbidden in preparation/inference")


def make_cases(public: dict[str, Any]) -> list[dict[str, Any]]:
    if public.get("version") != "satoh_fan_development_intake_v0.1" or [c.get("id") for c in public["cases"]] != list(IDS):
        raise ValueError("Expected exact ordered twenty-question public intake")
    allowed = {"id", "question_verbatim", "article_context_declared", "article_id", "original_pdf_sha256",
               "suggested_scoped_question_unsent", "augmentation", "request_constructed", "model_call_authorized"}
    result = []
    for row in public["cases"]:
        if set(row) != allowed or not isinstance(row["question_verbatim"], str) or not row["question_verbatim"].strip():
            raise ValueError("Question-only record has unsupported fields or empty question")
        label = row["id"].split("_")[0]
        if (row["article_id"], row["original_pdf_sha256"]) != IDENTITIES[label]:
            raise ValueError("Public case article/PDF identity differs from selected paper")
        year = "2013" if label == "Satoh" else "2018"
        result.append({"id": row["id"], "question_original": row["question_verbatim"],
            "question": f"По статье {label} ({year}): " + row["question_verbatim"],
            "article_id": row["article_id"], "original_pdf_sha256": row["original_pdf_sha256"],
            "original_pdf_path": str(PDFS[label]),
            "augmentation": "explicit_supplied_article_context_parentheses_for_existing_citation_grammar"})
    return result


def load_cases() -> list[dict[str, Any]]:
    data = read(BASE / "input_freeze_v01/questions.json")
    cases = data["cases"]
    if data["version"] != VERSION or [c["id"] for c in cases] != list(IDS):
        raise ValueError("Frozen case list changed")
    return cases


class ScopeObservation(files.Observation):
    def __init__(self, *args: Any, target: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.target = target
        self.fake_oauth_calls = 0
        self.native_boundary_calls = 0

    def observe(self, session: Any, retrieval: Any, evidence: Any, metadata: Any) -> None:
        foreign = [e for e in evidence if e.article_id != self.target["article_id"]]
        if foreign:
            files.write(self.folder / "scope_mismatch.json", {"expected_article": self.target["article_id"],
                "observed": [{"article_id": e.article_id, "chunk_id": e.chunk_id} for e in foreign]})
            raise ValueError("Selected evidence contains an article outside the declared single-paper scope")
        super().observe(session, retrieval, evidence, metadata)
        for region in self.sources["pages"].values():
            if (region["article_id"] != self.target["article_id"]
                    or region["original_pdf_sha256"] != self.target["original_pdf_sha256"]):
                raise ValueError("Source registry original PDF differs from declared single-paper identity")
        if self.sources["diagnostics"]:
            raise ValueError("Unresolved source registry diagnostics prevent dispatch")

    def instrument(self, provider: Any) -> Any:
        if self.expected is not None:
            return super().instrument(provider)
        from app.generation.gigachat import AUTH_URL, CHAT_URL

        def post(url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
            if oauth:
                if url != AUTH_URL or self.fake_oauth_calls:
                    raise ValueError("Unexpected/repeated offline OAuth boundary")
                self.fake_oauth_calls += 1
                return b'{"access_token":"offline-preparation-placeholder"}'
            if url != CHAT_URL or self.native_boundary_calls:
                raise ValueError("Unexpected/repeated native boundary")
            self.native_boundary_calls += 1
            self.body = body
            files.save(self.folder / "request.json", body)
            raise files.PreparedBoundary()

        provider._post = post
        return provider


def initialize() -> dict[str, Any]:
    settings = files.configure()
    if settings.rag_methods_identity_policy != "disabled":
        raise ValueError("Methods policy must remain disabled")
    cases = make_cases(read(PUBLIC))
    BASE.mkdir(parents=True, exist_ok=False)
    folder = BASE / "input_freeze_v01"
    folder.mkdir()
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"), Path(__file__), TESTS, SCOPE,
             ROOT / "scripts/gigachat_answer_smoke.py", ROOT / "pyproject.toml"]
    bindings = files.bindings(paths)
    for case in cases:
        if files.sha(Path(case["original_pdf_path"]).read_bytes()) != case["original_pdf_sha256"]:
            raise ValueError("Selected PDF changed before initialization")
    for source in paths:
        target = folder / "source_snapshot" / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        files.save(target, source.read_bytes())
    files.write(folder / "questions.json", {"version": VERSION, "cases": cases,
        "public_intake_sha256": files.sha(PUBLIC.read_bytes()), "reference_answers_included": False})
    files.write(folder / "runtime.json", {"version": VERSION, "input_bindings": bindings,
        "raw_user_instruction": "Начинаем проверку?", "scope_sha256": files.sha(SCOPE.read_bytes()),
        "maximum_model_attempts": 20, "maximum_oauth_attempts": 20,
        "new_model_calls": 0, "new_slots": 0, "authorization_sealed": False})
    files.verify(bindings)
    files.manifest(folder)
    return {"cases": len(cases), "new_model_calls": 0, "new_slots": 0}


def prepare(case: dict[str, Any], policy: files.NetworkPolicy, guard: GoldReadGuard) -> dict[str, Any]:
    files.verify_manifest(BASE / "input_freeze_v01")
    frozen = read(BASE / "input_freeze_v01/runtime.json")
    files.verify(frozen["input_bindings"])
    settings = files.configure()
    from sqlalchemy import text

    from app.db.session import SessionLocal
    from app.generation import service

    folder = BASE / "prepared_v01" / case["id"]
    folder.mkdir(parents=True, exist_ok=False)
    request = {"question": case["question"], "collection": settings.default_collection, "top_k": 5,
               "method": "hybrid_cross_lingual", "answer_style": "claims", "answer_language": "ru"}
    files.write(folder / "api_request.json", request)
    observation = ScopeObservation(folder, settings, policy, target=case)
    factory = service.build_answer_provider
    reached = False
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '120s'"))
        readonly = session.execute(text("SHOW transaction_read_only")).scalar_one()
        if readonly != "on":
            raise ValueError("Read-only transaction required")
        with patch.object(files, "QUESTION", case["question"]), patch.object(files, "PROTOCOL", SCOPE), \
                patch.object(service, "build_answer_provider", side_effect=lambda s: observation.instrument(factory(s))):
            try:
                result = service.answer_question(session, settings, **request,
                    trace_observer=lambda r, e, m: observation.observe(session, r, e, m))
                files.write(folder / "gate_response.json", {"http_status": 200, "body": service.answer_response_to_dict(result)})
            except files.PreparedBoundary:
                reached = True
            bindings = files.source_inputs(settings, observation)
        session.rollback()
    if observation.trace is None or observation.sources is None or policy.denied or guard.denied:
        raise ValueError("Missing trace or forbidden reference/network access")
    size = len(observation.body) if observation.body else 0
    if size > 100000:
        raise ValueError("Native request exceeds100000 bytes; clipping forbidden")
    if reached and (observation.fake_oauth_calls, observation.native_boundary_calls) != (1, 1):
        raise ValueError("Unexpected offline boundary counts")
    bindings.update(frozen["input_bindings"])
    bindings.update(files.bindings([BASE / "input_freeze_v01/manifest.json", BASE / "input_freeze_v01/questions.json"]))
    files.verify(bindings)
    contract = {"version": VERSION, "case": case, "generation_reached": reached,
        "request_sha256": files.sha(observation.body) if observation.body else None, "request_bytes": size,
        "input_bindings": bindings, "preparation_status": "ready_unsent" if reached else "production_gate_rejected",
        "transaction_read_only": readonly, "transaction_end": "rollback", "model_calls": 0, "oauth_calls": 0,
        "maximum_model_attempts": 0, "maximum_oauth_attempts": 0, "new_slots": 0,
        "model": settings.rag_model, "max_output_tokens": settings.rag_gigachat_max_tokens,
        "timeout_seconds": settings.rag_timeout_seconds, "network_denials": policy.denied, "gold_read_denials": guard.denied,
        "simulated_oauth_boundaries": observation.fake_oauth_calls, "captured_native_boundaries": observation.native_boundary_calls,
        "source_registry_diagnostics": observation.sources["diagnostics"]}
    files.write(folder / "contract.json", contract)
    files.manifest(folder)
    return {k: contract[k] for k in ("preparation_status", "generation_reached", "request_sha256", "request_bytes")}


def preparations() -> dict[str, Any]:
    result = {}
    for case in load_cases():
        folder = BASE / "prepared_v01" / case["id"]
        files.verify_manifest(folder)
        c = read(folder / "contract.json")
        files.verify(c["input_bindings"])
        if (c["case"] != case or c["transaction_read_only"] != "on" or c["transaction_end"] != "rollback"
                or c["network_denials"] or c["gold_read_denials"] or c["source_registry_diagnostics"]
                or any(c[k] for k in ("model_calls", "oauth_calls", "maximum_model_attempts", "maximum_oauth_attempts", "new_slots"))):
            raise ValueError("Preparation is not unchanged question-only/zero-budget/read-only")
        if c["generation_reached"]:
            if c["preparation_status"] != "ready_unsent":
                raise ValueError("Inconsistent generation boundary status")
            raw = (folder / "request.json").read_bytes()
            if files.sha(raw) != c["request_sha256"] or len(raw) != c["request_bytes"] or len(raw) > 100000:
                raise ValueError("Native preparation bytes changed")
            native = json.loads(raw)
            if (native["model"], native["max_tokens"], c["timeout_seconds"]) != ("GigaChat-2-Max", 1200, 120):
                raise ValueError("Native model/token/timeout changed")
        elif (c["preparation_status"] != "production_gate_rejected" or c["request_sha256"] is not None
              or c["request_bytes"] or (folder / "request.json").exists()
              or read(folder / "gate_response.json") != {
                  "http_status": 200, "body": read(folder / "gate_response.json")["body"]}
              or read(folder / "gate_response.json")["body"].get("status") != "insufficient_evidence"):
            raise ValueError("Blocked preparation has a native request or invalid production response")
        result[case["id"]] = c
    return result


def validate_approval(approval: dict[str, Any], contracts: dict[str, Any]) -> None:
    required = {"version": VERSION, "raw_user_instruction": "Начинаем проверку?", "case_ids": list(IDS),
        "request_sha256": {key: c["request_sha256"] for key, c in contracts.items()},
        "maximum_model_attempts": 20, "maximum_oauth_attempts": 20, "model": "GigaChat-2-Max",
        "max_output_tokens": 1200, "timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "scope_sha256": files.sha(SCOPE.read_bytes())}
    if any(approval.get(k) != value for k, value in required.items()):
        raise ValueError("Authorization does not match this new frozen twenty-case scope")


def seal(*, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise PermissionError("Current user instruction to begin twenty-case test required")
    contracts = preparations()
    approval = {"version": VERSION, "raw_user_instruction": "Начинаем проверку?", "case_ids": list(IDS),
        "request_sha256": {key: c["request_sha256"] for key, c in contracts.items()},
        "maximum_model_attempts": 20, "maximum_oauth_attempts": 20, "model": "GigaChat-2-Max",
        "max_output_tokens": 1200, "timeout_seconds": 120, "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "scope_sha256": files.sha(SCOPE.read_bytes()), "recorded_at_utc": datetime.now(UTC).isoformat()}
    validate_approval(approval, contracts)
    digests = [c["request_sha256"] for c in contracts.values() if c["generation_reached"]]
    if len(digests) != len(set(digests)) or any((files.LEDGER / digest).exists() for digest in digests):
        raise FileExistsError("Duplicate/already attempted native body: no reuse of old scopes")
    files.write(BASE / "approval_v01.json", approval)
    return {"cases": len(contracts), "ready": len(digests), "production_gate_rejected": len(contracts) - len(digests)}


def send(case: dict[str, Any], policy: files.NetworkPolicy, *, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise PermissionError("Twenty-case authorization required")
    if (BASE / "scope_closed_v01.json").exists():
        raise FileExistsError("Scope already closed; resend forbidden")
    cid = case["id"]
    for previous in IDS[:IDS.index(cid)]:
        result = read(BASE / previous / "result.json")
        if result.get("status") not in KNOWN:
            raise ValueError("Earlier unknown/failed outcome stops sends")
    contracts = preparations()
    approval = read(BASE / "approval_v01.json")
    validate_approval(approval, contracts)
    folder = BASE / cid
    folder.mkdir(exist_ok=False)
    c = contracts[cid]
    if not c["generation_reached"]:
        result = {"status": "gate_rejected", "model_attempts": 0, "oauth_attempts": 0,
                  "http_status": 200, "answer": read(BASE / "prepared_v01" / cid / "gate_response.json")["body"]}
    else:
        original = BASE / "prepared_v01" / cid
        approved = folder / "authorized_inputs"
        approved.mkdir()
        for p in original.iterdir():
            if p.is_file() and p.name not in {"manifest.json", "contract.json"}:
                shutil.copyfile(p, approved / p.name)
        contract = {**c, "authorization": "new_user_begin_Satoh_Fan_twenty_case_check_2026-11-10",
            "maximum_model_attempts": 1, "maximum_oauth_attempts": 1, "original_preparation": str(original),
            "input_bindings": {**c["input_bindings"], **files.bindings([*original.iterdir(), BASE / "approval_v01.json"])}}
        files.write(approved / "contract.json", contract)
        files.manifest(approved)
        with patch.object(files, "QUESTION", case["question"]), patch.object(files, "PROTOCOL", SCOPE), \
                patch.object(files, "VERSION", VERSION), patch.object(files, "Observation",
                    side_effect=lambda *a, **kw: ScopeObservation(*a, **kw, target=case)):
            result = files.send(approved, folder / "live", policy)
    files.write(folder / "result.json", result)
    if result.get("status") not in KNOWN:
        raise RuntimeError("Unknown/internal outcome stops further dispatch; see preserved result")
    return {"id": cid, **{k: result.get(k) for k in ("status", "http_status", "model_attempts", "oauth_attempts", "usage")}}


def close() -> dict[str, Any]:
    approval = read(BASE / "approval_v01.json")
    rows = []
    for cid in IDS:
        paths = [BASE / cid / "result.json", BASE / cid / "live/result.json"]
        result = next((read(p) for p in paths if p.is_file()), {})
        digest = approval["request_sha256"][cid]
        slot = files.LEDGER / digest if digest else None
        uncertain = not result and slot is not None and slot.exists()
        rows.append({"id": cid, "status": result.get("status", "not_dispatched"),
            "request_sha256": digest,
            "model_attempts": result.get("model_attempts", None if uncertain else 0),
            "oauth_attempts": result.get("oauth_attempts", None if uncertain else 0),
            "resend_authorized": False, "allowance_closed": True})
        if uncertain:
            rows[-1]["status"] = "reserved_outcome_unknown"
        if slot is not None and slot.exists():
            files.write(slot / "scope_closed_satoh_fan_20261110_v01.json", rows[-1])
    unknown = any(r["model_attempts"] is None or r["oauth_attempts"] is None for r in rows)
    value = {"cases": rows, "remaining_allowance": 0, "all_previous_scopes_remain_closed": True,
        "model_attempts": None if unknown else sum(r["model_attempts"] for r in rows),
        "oauth_attempts": None if unknown else sum(r["oauth_attempts"] for r in rows),
        "automatic_retries": 0, "fallbacks": 0, "continuations": 0}
    if not unknown and (value["model_attempts"] > 20 or value["oauth_attempts"] > 20):
        raise ValueError("Batch allowance exceeded")
    files.write(BASE / "scope_closed_v01.json", value)
    return value


def run_all(mode: str, *, authorized: bool) -> dict[str, Any]:
    if mode == "send" and not authorized:
        raise PermissionError("Current authorization required")
    settings = files.configure()
    rows = []
    for case in load_cases():
        command = [sys.executable, "-B", "-X", "utf8", "-m", "scripts.run_satoh_fan_qa_20261110", mode, "--case-id", case["id"]]
        if mode == "send":
            command.append("--authorize-twenty-case-check")
        done = subprocess.run(command, cwd=ROOT, capture_output=True, encoding="utf-8", check=False)
        log = BASE / "worker_logs" / case["id"]
        log.mkdir(parents=True, exist_ok=True)
        for name, content in (("stdout", done.stdout), ("stderr", done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    content = content.replace(secret, "[REDACTED]")
            files.save(log / (mode + "_" + name + ".txt"), content.encode())
        row = {"id": case["id"], "returncode": done.returncode}
        if done.returncode == 0:
            lines = done.stdout.strip().splitlines()
            row.update(json.loads(lines[-1]))
        rows.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        if done.returncode:
            break
    result = {"mode": mode, "cases": rows, "finished_all": len(rows) == 20 and all(r["returncode"] == 0 for r in rows)}
    files.write(BASE / (mode + "_batch_result.json"), result)
    if mode == "send":
        result["scope_closure"] = close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "prepare", "prepare-all", "seal", "send", "send-all", "close"))
    parser.add_argument("--case-id", choices=IDS)
    parser.add_argument("--authorize-twenty-case-check", action="store_true")
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    guard = GoldReadGuard()
    if args.mode != "init":
        sys.addaudithook(guard)
    if args.mode == "init":
        result = initialize()
    elif args.mode in {"prepare-all", "send-all"}:
        result = run_all(args.mode.split("-")[0], authorized=args.authorize_twenty_case_check)
    elif args.mode == "seal":
        result = seal(authorized=args.authorize_twenty_case_check)
    elif args.mode == "close":
        result = close()
    else:
        if args.case_id is None:
            raise ValueError("Case ID required")
        case = next(c for c in load_cases() if c["id"] == args.case_id)
        result = prepare(case, policy, guard) if args.mode == "prepare" else send(
            case, policy, authorized=args.authorize_twenty_case_check)
    if policy.denied or guard.denied:
        raise ValueError("Forbidden network/reference access attempted")
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
