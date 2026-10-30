"""Freeze three event requests, then send each once with explicit authorization."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as smoke  # noqa: E402
from scripts.gigachat_event_proposal import VERSION, build_request, catalog, parse_proposal  # noqa: E402

BASE = ROOT / "output/gigachat_event_pilot_20261029"
IDS = ("dispersion_hold_then_spectra", "impedance_equilibrium_criterion", "protonation_missing_time")
PROTOCOL = ROOT / "docs/records/gigachat_event_pilot_protocol_v0.1.md"


def prepare() -> dict:
    settings = smoke.configure()
    parent = ROOT / "output/real_experiment_cases_20261029/review_v02"
    smoke.verify_manifest(parent)
    previous = json.loads((parent / "report.json").read_bytes())
    smoke.verify(previous["bindings"])
    dataset = ROOT / "docs/records/real_experiment_cases_v0.1.json"
    cases = {c["id"]: c for c in json.loads(dataset.read_bytes())["cases"]}
    bindings = {**previous["bindings"], **smoke.bindings([
        Path(__file__), ROOT / "scripts/gigachat_event_proposal.py", ROOT / "tests/unit/test_gigachat_event_proposal.py",
        ROOT / "tests/unit/test_gigachat_event_pilot.py", PROTOCOL, dataset, parent / "report.json", parent / "manifest.json"])}
    if settings.gigachat_ca_bundle_file:
        bindings.update(smoke.bindings([Path(settings.gigachat_ca_bundle_file)]))
    entries, artifacts = [], []
    for case_id in IDS:
        case = cases[case_id]
        source = catalog(case["exact_text"])
        body = smoke.encode(build_request(case["question"], source, model=settings.rag_model,
                                          max_tokens=settings.rag_gigachat_max_tokens))
        if len(body) > 100000 or (smoke.LEDGER / smoke.sha(body)).exists():
            raise ValueError("Request is too large or its global slot was already consumed")
        page = next(p for p in previous["full_source_pages"] if p["article_id"] == case["article_id"]
                    and p["page_number"] == case["page"] and p["text_layer_id"] == case["source"]["text_layer_id"])
        assert page["page_text"][case["page_start_offset"]:case["page_end_offset"]] == source["exact_text"]
        if source["exact_text"].strip() == page["page_text"].strip():
            raise ValueError("Complete source page is outside this excerpt experiment")
        article = None
        # Metadata is read from the frozen source registry, never model-generated.
        registry = json.loads((ROOT / "output/experiment_sentence_links_20261029/review_v02/report.json").read_bytes())
        for row in registry["cases"]:
            for a in json.loads((Path(row["prepared_path"]) / "articles.json").read_bytes()):
                if a["article_id"] == case["article_id"]:
                    article = a
        if article is None:
            raise ValueError("Missing bound source article")
        entries.append({"id": case_id, "request_sha256": smoke.sha(body), "request_bytes": len(body)})
        artifacts.append((case, source, body, page, article))
    BASE.mkdir(parents=True, exist_ok=False)
    for case, source, body, page, article in artifacts:
        folder = BASE / "cases" / case["id"] / "prepared"
        folder.mkdir(parents=True)
        for name, value in (("catalog.json", source), ("case.json", case), ("source_page.json", page), ("article.json", article)):
            smoke.write(folder / name, value)
        smoke.save(folder / "request.json", body)
        smoke.manifest(folder)
        bindings.update(smoke.bindings([p for p in folder.iterdir() if p.is_file()]))
    snapshot = BASE / "source_snapshot_v01"
    for name, digest in bindings.items():
        source_path = Path(name)
        if source_path.is_relative_to(ROOT) and source_path.suffix in {".py", ".md", ".json"} and (
                source_path.relative_to(ROOT).parts[0] in {"app", "scripts", "tests", "docs"}):
            target = snapshot / source_path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = source_path.read_bytes()
            if smoke.sha(raw) != digest:
                raise ValueError("Source changed during snapshot")
            smoke.save(target, raw)
    smoke.manifest(snapshot)
    bindings.update(smoke.bindings([snapshot / "manifest.json"]))
    smoke.verify(bindings)
    study = {"version": VERSION, "authorization": "user_execute_proposed_three_event_extraction_cases_2026-10-29",
             "cases": entries, "bindings": bindings, "maximum_model_attempts": 3, "maximum_oauth_attempts": 3,
             "automatic_retries": 0, "fallbacks": 0, "model": settings.rag_model, "scope": settings.gigachat_scope,
             "max_tokens": settings.rag_gigachat_max_tokens, "timeout_seconds": settings.rag_timeout_seconds,
             "ca_bundle_file": settings.gigachat_ca_bundle_file, "new_model_calls": 0,
             "scientific_acceptance": "not_evaluated"}
    smoke.write(BASE / "study_contract_v01.json", study)
    return {"cases": len(entries), "request_bytes": [c["request_bytes"] for c in entries], "new_model_calls": 0}


def read_study() -> dict:
    study = json.loads((BASE / "study_contract_v01.json").read_bytes())
    if study["version"] != VERSION or tuple(c["id"] for c in study["cases"]) != IDS or (
            study["maximum_model_attempts"] != 3 or study["maximum_oauth_attempts"] != 3):
        raise ValueError("Frozen three-case scope differs")
    smoke.verify(study["bindings"])
    smoke.verify_manifest(BASE / "source_snapshot_v01")
    for c in study["cases"]:
        folder = BASE / "cases" / c["id"] / "prepared"
        smoke.verify_manifest(folder)
        if smoke.sha((folder / "request.json").read_bytes()) != c["request_sha256"]:
            raise ValueError("Native request differs")
    return study


def send(case_id: str, *, authorized: bool, policy: smoke.NetworkPolicy) -> dict:
    if not authorized:
        raise ValueError("Explicit authorization for the three-event pilot required")
    study = read_study()
    settings = smoke.configure()
    if case_id not in IDS or settings.gigachat_ca_bundle_file != study["ca_bundle_file"]:
        raise ValueError("Case or transport settings differ")
    entry = next(c for c in study["cases"] if c["id"] == case_id)
    folder = BASE / "cases" / case_id
    prepared, live = folder / "prepared", folder / "live"
    body = (prepared / "request.json").read_bytes()
    attempt = {"version": VERSION, "request_sha256": entry["request_sha256"], "case": case_id,
               "authorization": study["authorization"], "maximum_model_attempts": 1, "maximum_oauth_attempts": 1,
               "reserved_at_utc": datetime.now(UTC).isoformat(), "output": str(live.resolve())}
    slot = smoke.reserve(entry["request_sha256"], attempt)
    live.mkdir(exist_ok=False)
    smoke.write(live / "attempt.json", attempt)
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider, _json
    from app.generation.providers import GenerationUnavailableError
    provider = GigaChatAnswerProvider(credentials=settings.gigachat_credentials, scope=settings.gigachat_scope,
                                    model=settings.rag_model, timeout_seconds=settings.rag_timeout_seconds,
                                    max_tokens=settings.rag_gigachat_max_tokens, ca_bundle_file=settings.gigachat_ca_bundle_file)
    result = {"version": VERSION, "case": case_id, "status": "interrupted", "model_attempts": 0,
              "oauth_attempts": 0, "automatic_retries": 0, "fallbacks": 0,
              "scientific_acceptance": "not_evaluated", "native_success_http_metadata": "not_exposed_by_transport"}
    token = ""
    started = time.perf_counter()
    try:
        policy.external = True
        result["oauth_attempts"] = 1
        auth = provider._post(AUTH_URL, urlencode({"scope": settings.gigachat_scope}).encode(),
                              "Basic " + settings.gigachat_credentials, oauth=True)
        parsed_auth = _json(auth)
        token = parsed_auth.get("access_token") if isinstance(parsed_auth, dict) else None
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise ValueError("OAuth did not return a valid token")
        result["model_attempts"] = 1
        smoke.save(live / "request.json", body)
        raw = provider._post(CHAT_URL, body, "Bearer " + token)
        smoke.save(live / "response.bin", raw)  # Durable before any parsing.
        native = _json(raw)
        if isinstance(native, dict):
            result.update(returned_model=native.get("model"), usage=native.get("usage"))
            choices = native.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                result["finish_reason"] = choices[0].get("finish_reason")
        source = json.loads((prepared / "catalog.json").read_bytes())
        restored = parse_proposal(raw, source)
        smoke.write(live / "restored.json", restored)
        result["status"] = "integrity_valid_scientific_assignment_unverified"
        smoke.verify(study["bindings"])
    except (GenerationUnavailableError, ValueError, UnicodeError, OSError) as exc:
        message = str(exc)
        for secret in (settings.gigachat_credentials, token):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        result.update(status="output_rejected" if (live / "response.bin").exists() else "transport_failed",
                      error_type=type(exc).__name__, error=message)
    finally:
        policy.external = False
        result.update(elapsed_seconds=time.perf_counter() - started, network_denials=policy.denied,
                      completed_at_utc=datetime.now(UTC).isoformat())
        smoke.write(live / "result.json", result)
        smoke.write(slot / "result.json", result)
        smoke.manifest(live)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "send"))
    parser.add_argument("--case-id", choices=IDS)
    parser.add_argument("--authorize-three-event-pilot", action="store_true")
    args = parser.parse_args()
    policy = smoke.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "prepare":
        result = prepare()
    else:
        if args.case_id is None:
            parser.error("--case-id is required")
        value = send(args.case_id, authorized=args.authorize_three_event_pilot, policy=policy)
        result = {k: value.get(k) for k in ("case", "status", "model_attempts", "oauth_attempts", "finish_reason", "usage", "error")}
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
