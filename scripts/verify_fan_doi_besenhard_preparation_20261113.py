"""Verify immutable receipt, all thirty preparations and fresh PDF page identities."""

from __future__ import annotations

import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import fitz

from scripts import prepare_fan_doi_besenhard_20261113 as prep
from scripts import run_fan_doi_besenhard_preparations_20261113 as runner

f = prep.f


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href")


def verify():
    runner.verify()
    cases = prep.verify_runtime()
    raw = (prep.PRIVATE / "supplied_original.md").read_bytes()
    original = raw.decode("utf-8-sig")
    runtime = prep.read(prep.FREEZE / "runtime.json")
    prep.require(raw == prep.USER_FILE.read_bytes(), "User input changed since receipt")
    prep.require(f.sha(raw) == runtime["reference_document_sha256"], "Reference commitment differs")
    pages, page_observations, pdf_hashes, rows = {}, 0, {}, []
    native_sizes, prospective_cases = [], []
    for case in cases:
        span = case["question_span"]
        prep.require(original[span["start"]:span["end"]] == case["question_original"], "Question span drift")
        folder = prep.BASE / "prepared_v01" / case["id"]
        f.verify_manifest(folder)
        c = prep.read(folder / "contract.json")
        api = prep.read(folder / "api_request.json")
        prep.require(api["question"] == case["question"], "Question changed at API boundary")
        prep.require(c["case"] == case, "Case identity changed")
        prep.require(c["transaction_read_only"] == "on" and c["transaction_end"] == "rollback", "DB not read-only")
        prep.require(not c["network_denials"] and not c["reference_read_denials"], "Forbidden access")
        prep.require(c["model_calls"] == c["oauth_calls"] == c["new_slots"] == 0, "Unexpected live execution")
        prep.require(c["dispatch_allowed"] is False, "Preparation opened live allowance")
        trace = prep.read(folder / "trace.json")
        sources = prep.read(folder / "sources.json")
        prep.require(not sources["diagnostics"], "Source registry unresolved")
        reasons = trace["metadata"].get("evidence_adequacy", {})
        row = {"id": case["id"], "article": case["label"], "preparation_status": c["preparation_status"],
               "scope_matches": c["article_scope_matches"], "adequacy_reason": reasons.get("reason"),
               "matched_terms": reasons.get("matched_terms"), "coverage": reasons.get("coverage")}
        if c["generation_reached"]:
            native = (folder / "request.json").read_bytes()
            request = json.loads(native)
            prep.require(f.sha(native) == c["request_sha256"] and len(native) == c["request_bytes"], "Native drift")
            prep.require(len(native) <= 100000, "Request exceeds ceiling")
            prep.require(request["model"] == "GigaChat-2-Max" and request["max_tokens"] == 1200, "Model/budget drift")
            prep.require(case["question"] in "\n".join(m["content"] for m in request["messages"]), "Question absent")
            native_sizes.append(len(native))
            if c["eligible_for_future_scope"]:
                prospective_cases.append({"id": case["id"], "request_sha256": c["request_sha256"],
                    "request_bytes": c["request_bytes"], "prepared_folder": str(folder.resolve()),
                    "preparation_manifest_sha256": f.sha((folder / "manifest.json").read_bytes())})
        else:
            response = prep.read(folder / "preparation_api_response.json")
            row.update(http_status=response["http_status"], answer_status=response["body"].get("answer", {}).get("status"))
            prep.require(not (folder / "request.json").exists(), "Refusal unexpectedly has native request")
        for region in sources["pages"].values():
            page_observations += 1
            path = Path(region["layer_pdf_path"])
            if str(path) not in pdf_hashes:
                pdf_hashes[str(path)] = f.sha(path.read_bytes())
            prep.require(pdf_hashes[str(path)] == region["layer_pdf_sha256"], "PDF hash drift")
            original_path = Path(region["original_pdf_path"])
            if str(original_path) not in pdf_hashes:
                pdf_hashes[str(original_path)] = f.sha(original_path.read_bytes())
            prep.require(pdf_hashes[str(original_path)] == region["original_pdf_sha256"], "Original PDF drift")
            key = (str(path), region["page_number"])
            if key not in pages:
                with fitz.open(path) as pdf:
                    pages[key] = pdf[region["page_number"] - 1].get_text("text")
            text = pages[key]
            prep.require(text == region["page_text"] and f.sha(text.encode()) == region["page_text_sha256"],
                         "Fresh PDF page differs from captured source")
            prep.require(text[region["start"]:region["end"]] == region["quote"], "Raw source quote drift")
        rows.append(row)
    f.verify_manifest(prep.PRIVATE)
    review = prep.BASE / "review_v01"
    f.verify_manifest(review)
    parser = Links()
    page = (review / "review.html").read_text(encoding="utf-8")
    parser.feed(page)
    for href in parser.links:
        parsed = urlparse(href)
        prep.require(parsed.scheme == "file", "Unexpected nonlocal review link")
        path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", path):
            path = path[1:]
        prep.require(Path(path).is_file(), "Missing review link: " + href)
    result = {"cases_verified": len(rows), "original_question_spans_verified": len(rows),
        "fresh_unique_pdf_pages": len(pages), "source_page_observations": page_observations,
        "pdf_files_hash_verified": len(pdf_hashes), "review_links_verified": len(parser.links),
        "status_counts": dict(Counter(r["preparation_status"] for r in rows)),
        "native_requests": len(native_sizes), "native_total_bytes": sum(native_sizes),
        "native_max_bytes": max(native_sizes, default=0), "new_model_calls": 0, "new_oauth_calls": 0,
        "scientific_scores": None, "independent_accuracy": None, "rows": rows,
        "completion_basis": "thirty individually verified complete preparation manifests and contracts",
        "orchestration_diagnostic": "parent timed out after D8 artifacts completed; D8 not rerun; continued D9..B10",
        "D8_worker_exit_code": None,
        "browser_or_visual_pdf_check": "not_run; text_and_hash_integrity_only"}
    result["by_article"] = {label: dict(Counter(r["preparation_status"] for r in rows if r["article"] == label))
                            for label, _, _ in prep.SOURCES.values()}
    result["adequacy_reasons"] = dict(Counter(r["adequacy_reason"] for r in rows))
    output = prep.BASE / "verification_v01"
    output.mkdir(exist_ok=False)
    f.write(output / "report.json", result)
    f.write(output / "prospective_live_scope.json", {
        "status": "concrete_inputs_ready; new_live_authorization_pending", "current_live_allowance": 0,
        "cases": prospective_cases, "registered_denominator": 30,
        "maximum_model_attempts_if_authorized": len(prospective_cases),
        "maximum_oauth_attempts_if_authorized": len(prospective_cases), "attempts_per_case": 1,
        "model": "GigaChat-2-Max", "max_output_tokens": 1200, "per_http_timeout_seconds": 120,
        "native_byte_ceiling": 100000, "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "monetary_cost": None, "original_reference_sha256": f.sha(raw),
        "candidate_version_id": runtime["candidate_version_id"],
        "input_freeze_manifest_sha256": f.sha((prep.FREEZE / "manifest.json").read_bytes()),
        "harness_overlay_manifest_sha256": f.sha((runner.EXECUTION / "manifest.json").read_bytes()),
        "all_older_live_allowances_remain_closed": True,
        "closure_policy": "close consumed, unused and reserved-unknown allowances; no resend",
        "batch_stop_policy": "transport HTTP503/internal or unknown failure stops remaining sends; record HTTP502 without retry",
        "assessment_policy": "native and delivered output separate; no references to inference; source review after scope closure",
        "authorization_rule_source": "docs/records/answer_priorities_independent_v0.1/README.md step5"})
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(output)
    return {k: v for k, v in result.items() if k != "rows"}


if __name__ == "__main__":
    policy = f.NetworkPolicy()
    prep.sys.addaudithook(policy)
    print(json.dumps(verify(), ensure_ascii=False), flush=True)
    prep.require(not policy.denied, "Forbidden network")
