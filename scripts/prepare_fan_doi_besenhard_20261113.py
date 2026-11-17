"""Freeze supplied QA and prepare thirty actual API requests; no live send mode."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as route

BASE = f.ROOT / "output/fan_doi_besenhard_20261113"
FREEZE = BASE / "input_freeze_v01"
PRIVATE = BASE / "private_intake_v01"
CANDIDATE = f.ROOT / "output/answer_priorities_20261111/candidate_freeze_v01"
USER_FILE = Path("C:/Users/unive/Downloads/Ariadne_QA_Fan_Doi_Besenhard_30.md")
PROTOCOL = f.ROOT / "docs/records/fan_doi_besenhard_preparation_2026-11-13_v0.1.md"
INVENTORY = f.ROOT / "output/particle_attachment_20261103/review_v01/report.json"
SOURCES = {
    "F": ("Fan", "2018", "10.1038/s41565-018-0183-2"),
    "D": ("Doi", "2018", "10.1039/C8SE00036K"),
    "B": ("Besenhard", "2002", None),
}
IDS = [f"{label}{i}" for label in SOURCES for i in range(1, 11)]


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_document(text):
    """Return only exact question headings, never reference prose or page hints."""
    headings = list(re.finditer(r"^### ([FDB])([1-9]|10)\. ([^\r\n]+)\r?$", text, re.M))
    require([m[1] + m[2] for m in headings] == IDS, "Expected ordered F1..F10, D1..D10, B1..B10")
    cases = []
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[match.end():end]
        require(block.count("**Эталонный ответ:**") == 1, "One reference per question required")
        require(block.count("**Источник:**") == 1, "One source declaration per question required")
        label, year, _ = SOURCES[match[1]]
        cases.append({"id": match[1] + match[2], "label": label,
            "question_original": match[3], "question_span": {"start": match.start(3), "end": match.end(3)},
            "question": f"По статье {label} ({year}): " + match[3],
            "augmentation": "explicit_user_selected_article_context; original_question_verbatim"})
    return cases


def app_paths():
    return sorted(p for p in (f.ROOT / "app").rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts)


def initialize():
    require(not BASE.exists(), "Receipt already exists; never overwrite")
    f.verify_manifest(CANDIDATE)
    candidate = read(CANDIDATE / "version.json")
    paths = app_paths() + [f.ROOT / "pyproject.toml"]
    current = f.bindings(paths)
    require(all(candidate["bindings"].get(p) == h for p, h in current.items()), "Candidate application drift")
    require({p for p in candidate["bindings"] if Path(p).is_relative_to(f.ROOT / "app")}
            == {str(p.resolve()) for p in app_paths()}, "Candidate app file set differs")
    raw = USER_FILE.read_bytes()
    text = raw.decode("utf-8-sig")
    cases = parse_document(text)
    inventory = read(INVENTORY)["articles"]
    papers = []
    for key, (label, year, doi) in SOURCES.items():
        matches = [a for a in inventory if Path(a["original_pdf_path"]).name.endswith(f"_{label}_{year}.pdf")]
        require(len(matches) == 1, "Ambiguous corpus article: " + label)
        paper = matches[0]
        require(f.sha(Path(paper["original_pdf_path"]).read_bytes()) == paper["original_pdf_sha256"], "PDF drift")
        if doi:
            require(doi.casefold() in text.casefold(), "Declared DOI missing: " + label)
        papers.append(paper)
        for case in cases:
            if case["id"].startswith(key):
                case.update(article_id=paper["article_id"], original_pdf_path=paper["original_pdf_path"],
                            original_pdf_sha256=paper["original_pdf_sha256"])
    PRIVATE.mkdir(parents=True)
    f.save(PRIVATE / "supplied_original.md", raw)
    f.write(PRIVATE / "provenance.json", {"original_path": str(USER_FILE), "original_sha256": f.sha(raw),
        "input_bytes": len(raw), "user_request_verbatim": "Вот. Можно начинать проверку",
        "corpus_mode_user_reply_verbatim": "Существующий корпус с указанием статьи (рекомендую для сравнения с прошлой серией)",
        "authorship_declared": None, "annotation_method_declared": None, "llm_assistance_declared": None,
        "expert_verification_declared": None, "preparation_time_declared": None,
        "reference_received_before_this_pass_predictions": True,
        "implementation_assistant_saw_references_before_preparation": True,
        "model_worker_receives_references": False, "source_page_hints_in_inference": False,
        "prior_exposure": ["Corpus previously used in development; source-level independence not established",
            "Fan prior use explicitly disclosed by supplied document", "Assistant inspected first pages before receipt"],
        "supplied_scoring_rubric": {"per_question": [0, 1, 2], "maximum": 60,
            "adoption_status": "supplied_evaluation_proposal; no acceptance_threshold_or_scores_invented"},
        "embedded_protocol_status": "document_content_not_an_automatic_user_command",
        "separate_corpus_instruction": "not_applied; user_selected_existing_corpus"})
    f.manifest(PRIVATE)
    FREEZE.mkdir()
    f.write(FREEZE / "questions.json", {"cases": cases, "references_included": False})
    f.write(FREEZE / "articles.json", papers)
    extra = [Path(__file__), PROTOCOL, INVENTORY, Path(route.__file__), Path(f.__file__),
             f.ROOT / "tests/unit/test_prepare_fan_doi_besenhard.py"]
    current.update(f.bindings(extra))
    f.write(FREEZE / "bindings.json", current)
    f.write(FREEZE / "runtime.json", {"candidate_version_id": candidate["candidate_version_id"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=f.ROOT, text=True).strip(),
        "created_at_utc": datetime.now(UTC).isoformat(), "reference_document_sha256": f.sha(raw),
        "references_in_input_tree": False, "endpoint": "/answer/experimental/required-fields",
        "collection": "literature", "method": "hybrid_cross_lingual", "top_k": 5,
        "model": "GigaChat-2-Max", "max_output_tokens": 1200, "per_http_timeout_seconds": 120,
        "native_byte_ceiling": 100000, "current_live_model_allowance": 0, "current_oauth_allowance": 0,
        "new_slot_reservations": 0, "scientific_scores": None, "independent_accuracy": None,
        "plan_percent": 75, "all_older_live_allowances_remain_closed": True})
    f.save(FREEZE / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(FREEZE)
    return {"questions": len(cases), "articles": len(papers), "candidate_bindings_exact": len(paths),
            "model_calls": 0, "oauth_calls": 0}


class ReferenceGuard:
    def __init__(self):
        self.denied = []

    def __call__(self, event, args):
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        forbidden = (path == USER_FILE.resolve() or path.name.casefold().startswith("ariadne_qa_")
                     or path.is_relative_to(PRIVATE))
        if path.is_relative_to(f.ROOT / "output"):
            forbidden |= not (path.is_relative_to(FREEZE) or path.is_relative_to(BASE / "prepared_v01"))
        if path.is_relative_to(f.ROOT / "docs/records"):
            forbidden |= path != PROTOCOL
        if forbidden:
            self.denied.append(str(path))
            raise PermissionError("Question-only preparation cannot read reference or review files")


def verify_runtime():
    f.verify_manifest(FREEZE)
    f.verify(read(FREEZE / "bindings.json"))
    require({str(p.resolve()) for p in app_paths()}
            == {p for p in read(FREEZE / "bindings.json") if Path(p).is_relative_to(f.ROOT / "app")},
            "App file set changed")
    return read(FREEZE / "questions.json")["cases"]


def prepare(case, policy, guard):
    verify_runtime()
    settings = f.configure()
    folder = BASE / "prepared_v01" / case["id"]
    folder.mkdir(parents=True, exist_ok=False)
    api = {"question": case["question"], "collection": "literature", "top_k": 5,
           "method": "hybrid_cross_lingual", "answer_style": "claims", "answer_language": "ru"}
    f.write(folder / "api_request.json", api)
    observation = route.Observation(folder, settings, policy, case=case)
    reached, status = False, None
    with patch.object(f, "QUESTION", case["question"]), patch.object(f, "PROTOCOL", PROTOCOL):
        try:
            response = route.run_route(observation, api)
            status = response.status_code
            f.write(folder / "preparation_api_response.json", {"http_status": status, "body": response.json()})
        except f.PreparedBoundary:
            reached = True
        require(observation.trace is not None and observation.sources is not None, "Missing actual API trace")
        inputs = f.source_inputs(settings, observation)
    verify_runtime()
    require(not policy.denied and not guard.denied, "Forbidden network/reference reads")
    size = len(observation.body) if observation.body else 0
    eligible = reached and observation.scope_ok and size <= 100000 and not observation.sources["diagnostics"]
    reason = ("ready_unsent" if eligible else "preparation_api_error" if status not in (None, 200)
              else "baseline_preprovider_refusal" if not reached else "harness_article_scope_stop"
              if not observation.scope_ok else "harness_budget_or_registry_stop")
    inputs.update(read(FREEZE / "bindings.json"))
    inputs.update(f.bindings([FREEZE / "manifest.json", FREEZE / "questions.json"]))
    f.verify(inputs)
    contract = {"id": case["id"], "case": case, "preparation_status": reason,
        "generation_reached": reached, "eligible_for_future_scope": eligible, "dispatch_allowed": False,
        "request_sha256": f.sha(observation.body) if observation.body else None, "request_bytes": size,
        "input_bindings": inputs, "transaction_read_only": observation.readonly, "transaction_end": "rollback",
        "selected_article_ids": sorted({e["article_id"] for e in observation.trace["evidence"]}),
        "article_scope_matches": observation.scope_ok, "network_denials": policy.denied,
        "reference_read_denials": guard.denied, "model_calls": 0, "oauth_calls": 0, "new_slots": 0}
    f.write(folder / "contract.json", contract)
    f.manifest(folder)
    return {k: contract[k] for k in ("id", "preparation_status", "request_bytes", "eligible_for_future_scope")}


def batch():
    rows = []
    for case in verify_runtime():
        folder = BASE / "worker_logs_v01" / case["id"]
        folder.mkdir(parents=True, exist_ok=False)
        done = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", __spec__.name,
                               "prepare", "--case-id", case["id"]], cwd=f.ROOT,
                              capture_output=True, text=True, encoding="utf-8", check=False, timeout=240)
        settings = f.configure()
        for name, value in (("stdout", done.stdout), ("stderr", done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, "[REDACTED]")
            f.save(folder / f"{name}.txt", value.encode())
        row = {"id": case["id"], "exit_code": done.returncode}
        if done.returncode == 0:
            row.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(row)
        print(json.dumps(row), flush=True)
        if done.returncode:
            break
    value = {"cases": rows, "finished_all": len(rows) == 30 and all(r["exit_code"] == 0 for r in rows)}
    f.write(BASE / "preparation_batch_v01.json", value)
    return {"finished_all": value["finished_all"], "workers": len(rows)}


def review():
    cases = verify_runtime()
    rows = []
    for case in cases:
        folder = BASE / "prepared_v01" / case["id"]
        f.verify_manifest(folder)
        c = read(folder / "contract.json")
        f.verify(c["input_bindings"])
        require(c["case"] == case and c["transaction_read_only"] == "on", "Case/transaction drift")
        rows.append({"id": case["id"], "question": case["question_original"], "article": case["label"],
            **{k: c[k] for k in ("preparation_status", "request_bytes", "request_sha256",
                                 "article_scope_matches", "eligible_for_future_scope")}})
    target = BASE / "review_v01"
    target.mkdir(exist_ok=False)
    f.verify_manifest(PRIVATE)
    runtime = read(FREEZE / "runtime.json")
    summary = {"cases": 30, "status_counts": dict(Counter(r["preparation_status"] for r in rows)),
        "candidate_version_id": runtime["candidate_version_id"], "git_commit": runtime["git_commit"],
        "total_native_bytes": sum(r["request_bytes"] for r in rows),
        "maximum_native_bytes": max(r["request_bytes"] for r in rows),
        "new_model_calls": 0, "new_oauth_calls": 0, "new_slots": 0, "scientific_scores": None,
        "independent_accuracy": None, "plan_percent": 75, "runtime_tuned_on_this_set": False,
        "references_passed_to_inference": False, "original_file_sha256": runtime["reference_document_sha256"]}
    f.write(target / "report.json", {"summary": summary, "cases": rows,
        "provenance": read(PRIVATE / "provenance.json"), "proposed_next_scope": {
            "eligible_case_ids": [r["id"] for r in rows if r["eligible_for_future_scope"]],
            "model": "GigaChat-2-Max", "max_output_tokens": 1200, "per_http_timeout_seconds": 120,
            "attempts_per_eligible_case": 1, "oauth_per_eligible_case": 1,
            "automatic_retries": 0, "fallbacks": 0, "continuations": 0, "monetary_cost": None,
            "authorization_status": "not_opened_by_preparation"}})
    def pre(value):
        return "<pre>" + html.escape(json.dumps(value, ensure_ascii=False, indent=2)) + "</pre>"
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: 30 новых вопросов</title>',
        '<style>body{font:16px/1.5 system-ui;margin:32px;max-width:1400px}table{border-collapse:collapse}',
        'td,th{border:1px solid #bbc;padding:9px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>',
        '<h1>Fan / Doi / Besenhard: подготовка проверки</h1>',
        '<p>30 исходных вопросов. Код зафиксирован. Ответов модели и баллов пока нет. '
        'Эталоны не переданы в inference. Использован существующий корпус с указанием статьи.</p>', pre(summary),
        '<table><tr><th>ID</th><th>Вопрос</th><th>Статус</th><th>Байты</th><th>Материалы</th></tr>']
    for row in rows:
        folder = BASE / "prepared_v01" / row["id"]
        links = []
        for name in ("api_request.json", "trace.json", "sources.json", "request.json", "preparation_api_response.json"):
            if (folder / name).exists():
                links.append('<a href="' + (folder / name).as_uri() + '">' + name + '</a>')
        parts.append('<tr><td>' + row["id"] + '</td><td>' + html.escape(row["question"]) + '</td><td>'
                     + row["preparation_status"] + '</td><td>' + str(row["request_bytes"])
                     + '</td><td>' + ' · '.join(links) + '</td></tr>')
    parts.append('</table><h2>Три статьи</h2><ul>')
    for paper in read(FREEZE / "articles.json"):
        parts.append('<li><a href="' + Path(paper["original_pdf_path"]).as_uri() + '">'
                     + html.escape(paper["title"]) + '</a></li>')
    parts.append('</ul><h2>Происхождение и ограничения</h2>' + pre(read(PRIVATE / "provenance.json")) + '</html>')
    f.save(target / "review.html", ''.join(parts).encode())
    f.manifest(target)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "prepare", "prepare-all", "review"))
    parser.add_argument("--case-id", choices=IDS)
    args = parser.parse_args()
    policy, guard = f.NetworkPolicy(), ReferenceGuard()
    sys.addaudithook(policy)
    if args.mode == "prepare":
        require(args.case_id is not None, "prepare requires --case-id")
        sys.addaudithook(guard)
        case = next(c for c in verify_runtime() if c["id"] == args.case_id)
        result = prepare(case, policy, guard)
    elif args.mode == "init":
        result = initialize()
    elif args.mode == "prepare-all":
        result = batch()
    else:
        result = review()
    require(not policy.denied and not guard.denied, "Forbidden network/reference access")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
