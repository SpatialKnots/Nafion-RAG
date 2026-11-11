"""Freeze and replay actual saved answers; no provider/OAuth/DB/retrieval execution."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from app.generation import answer_support as support
from app.generation.providers import Evidence, GeneratedClaim, ProviderResult, _clean_generation_evidence_text
from scripts import gigachat_answer_smoke as files

ROOT = files.ROOT
BASE = ROOT / "output/answer_support_v02_20261110"
PROTOCOL = ROOT / "docs/records/answer_support_audit_2026-11-10_v0.2.md"
PARENTS = {
    "original": ROOT / "output/satoh_fan_qa_run_20261110/review_v01",
    "rewriting_v01": ROOT / "output/query_rewriting_20261110/review_v01",
    "rewriting_v02": ROOT / "output/query_rewriting_v02_20261110/review_v01",
}
PDFS = {"Satoh": ROOT / "data/pdf/6689166e7e160336_Satoh_2013.pdf",
        "Fan": ROOT / "data/pdf/59bfbd00f345b750_Fan_2018.pdf"}


def read(path):
    return json.loads(path.read_bytes())


def project():
    """Whitelist only questions, actual claims/evidence and provenance, never reference answers."""
    records, paths = [], []
    for dataset, parent in PARENTS.items():
        files.verify_manifest(parent)
        report = read(parent / "report.json")
        files.verify(report["bindings"])
        paths.extend([parent / "manifest.json", parent / "report.json"])
        for row in report["cases"]:
            cid = row["id"]
            if dataset == "original":
                status, body, evidence = row["status"], row["answer"], row["evidence"]
                native = parent.parent / cid / "live"
                reused = False
            elif dataset == "rewriting_v01":
                status, body, evidence = row["result"]["status"], row["answer"], row["selected_raw_evidence"]
                native = parent.parent / "answers" / cid / "live"
                reused = row["result"]["status"] == "identical_native_reuse"
            else:
                status, body, evidence = row["effective_status"], row["answer"], row["selected_raw_evidence"]
                native = Path(row["effective_native_folder"]) if row["effective_native_folder"] else None
                reused = row["v02_status"] == "identical_native_reuse"
            api_hash = files.sha(files.encode(body))
            request_sha, native_folder = None, None
            if status == "runtime_answered":
                if native is None or not native.resolve().is_relative_to((ROOT / "output").resolve()):
                    raise ValueError("Actual native folder outside output tree")
                files.verify_manifest(native)
                request = (native / "request.json").read_bytes()
                prompt = json.loads(request)["messages"][1]["content"]
                for item in evidence:
                    if _clean_generation_evidence_text(item["text"]) not in prompt:
                        raise ValueError("Raw evidence is absent from the actual whitespace-cleaned prompt")
                actual_api = read(native / "api_response.json")["body"]
                if actual_api != body:
                    raise ValueError("Projected API body differs from saved actual response")
                request_sha, native_folder = files.sha(request), str(native)
                paths.extend([native / "manifest.json", native / "request.json", native / "api_response.json"])
            records.append({"dataset": dataset, "id": cid, "question": row["question"], "original_status": status,
                "original_api_body": body, "original_api_canonical_sha256": api_hash,
                "evidence": evidence, "actual_native_folder": native_folder, "request_sha256": request_sha,
                "reused_model_sample": reused, "original_pdf_path": str(PDFS[cid.split("_")[0]])})
    if len(records) != 60 or len({(r["dataset"], r["id"]) for r in records}) != 60:
        raise ValueError("Expected all three complete twenty-question datasets")
    return records, paths


def freeze():
    records, parent_paths = project()
    BASE.mkdir(exist_ok=False)
    folder = BASE / "freeze_v01"
    folder.mkdir()
    code = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"),
            Path(__file__), PROTOCOL, ROOT / "tests/unit/test_answer_support.py",
            ROOT / "tests/unit/test_answer_support_runtime.py", ROOT / "tests/unit/test_answer_support_boundaries.py",
            ROOT / "scripts/test_answer_support_20261110.py",
            ROOT / "docs/records/answer_support_audit_2026-11-10_v0.1.md", ROOT / "pyproject.toml"]
    for path in code:
        target = folder / "source_snapshot" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        files.save(target, path.read_bytes())
    bindings = files.bindings([*code, *parent_paths, *PDFS.values(),
                              ROOT / "output/answer_support_preflight_20261110/tests_v06.xml"])
    files.write(folder / "records.json", {"records": records, "reference_answers_included": False,
        "scope": "whitelisted saved model/API observations, not hidden gold"})
    files.write(folder / "bindings.json", bindings)
    files.verify(bindings)
    files.manifest(folder)
    return {"records": len(records), "answered_records": sum(r["original_status"] == "runtime_answered" for r in records),
            "new_model_calls": 0}


class ReplayProvider:
    def __init__(self, native):
        self.native, self.calls = native, 0

    def generate(self, *args, **kwargs):
        self.calls += 1
        return self.native


def run():
    freeze = BASE / "freeze_v01"
    files.verify_manifest(freeze)
    files.verify(read(freeze / "bindings.json"))
    records = read(freeze / "records.json")["records"]
    output = BASE / "review_v01"
    output.mkdir(exist_ok=False)
    rows, counts, witnesses = [], {}, []
    for record in records:
        row = {"dataset": record["dataset"], "id": record["id"], "original_status": record["original_status"],
               "question": record["question"], "request_sha256": record["request_sha256"],
               "reused_model_sample": record["reused_model_sample"], "audit": None,
               "projection": "original_nonanswer_preserved", "new_provider_calls": 0}
        if record["original_status"] == "runtime_answered":
            claims = [GeneratedClaim(**c) for c in record["original_api_body"]["claims"]]
            evidence = [Evidence(**e) for e in record["evidence"]]
            before = files.encode({"claims": [asdict(c) for c in claims], "evidence": [asdict(e) for e in evidence]})
            checked = support.audit(record["question"], claims, evidence)
            native = ProviderResult(True, claims, record["original_api_body"]["generation_provider"],
                                    record["original_api_body"]["generation_model"])
            provider, reports = ReplayProvider(native), []
            guarded = support.AuditedAnswerProvider(provider, reports.append).generate(record["question"], evidence)
            if provider.calls != 1 or len(reports) != 1:
                raise ValueError("Unexpected synthetic replay boundary count")
            replay_audit = {k: v for k, v in reports[0].items() if k != "wrapper_decision"}
            if replay_audit != checked or native.claims != claims:
                raise ValueError("Wrapper and standalone audit differ or native changed")
            if guarded.answerable != (not checked["decision"].startswith("withhold_")):
                raise ValueError("Wrapper did not enforce the declared decision")
            if files.encode({"claims": [asdict(c) for c in claims], "evidence": [asdict(e) for e in evidence]}) != before:
                raise ValueError("Original claims/source evidence modified")
            row.update(audit=checked, projection="retained_unverified" if guarded.answerable else checked["decision"],
                       guarded_result={"answerable": guarded.answerable, "claims": [asdict(c) for c in guarded.claims],
                                       "origin": "synthetic replay decision, not a new model/API response"})
            prompt = read(Path(record["actual_native_folder"]) / "request.json")["messages"][1]["content"]
            source_map = {e.citation_id: e for e in evidence}

            def visit(value, source_map=source_map, prompt=prompt, record=record):
                if isinstance(value, dict):
                    if {"raw_text_sha256", "start", "end", "text", "citation_id"} <= value.keys():
                        source = source_map[value["citation_id"]]
                        if (support.sha(source.text) != value["raw_text_sha256"]
                                or source.text[value["start"]:value["end"]] != value["text"]):
                            raise ValueError("Source witness raw hash/span mismatch")
                        text = _clean_generation_evidence_text(value["text"])
                        offset = prompt.find(text)
                        if offset < 0:
                            raise ValueError("Bound source witness absent from actual prompt")
                        witnesses.append({"dataset": record["dataset"], "id": record["id"], "raw_anchor": value,
                            "actual_prompt_start": offset, "actual_prompt_end": offset + len(text),
                            "actual_text": text, "transform": "existing whitespace collapse only"})
                    for child in value.values():
                        visit(child)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)
            visit(checked)
        rows.append(row)
    for dataset in PARENTS:
        selected = [r for r in rows if r["dataset"] == dataset]
        counts[dataset] = {"all_cases": len(selected),
            "original_answered": sum(r["original_status"] == "runtime_answered" for r in selected),
            "projection_counts": dict(Counter(r["projection"] for r in selected)),
            "finding_codes": dict(Counter(f["code"] for r in selected if r["audit"]
                for f in [*[f for c in r["audit"]["claims"] for f in c["findings"]], *r["audit"]["completeness_findings"]]))}
    summary = {"version": support.VERSION, "records": len(rows), "answered_records_audited": sum(r["audit"] is not None for r in rows),
        "unique_answered_native_requests": len({r["request_sha256"] for r in rows if r["audit"]}),
        "datasets": counts, "raw_to_actual_prompt_anchor_observations": len(witnesses),
        "distinct_raw_source_addresses": len({(w["raw_anchor"]["article_id"], w["raw_anchor"]["chunk_id"],
            w["raw_anchor"]["raw_text_sha256"], w["raw_anchor"]["start"], w["raw_anchor"]["end"]) for w in witnesses}),
        "new_model_calls": 0, "new_oauth_calls": 0, "new_DB_calls": 0, "new_retrieval_calls": 0,
        "default_runtime_changed": False, "original_outputs_modified": False,
        "independent_accuracy": None, "scientific_validity": "not_evaluated", "score": None}
    files.write(output / "report.json", {"summary": summary, "records": rows, "witnesses": witnesses,
        "input_manifest_sha256": files.sha((freeze / "manifest.json").read_bytes()),
        "bindings": files.bindings([freeze / "manifest.json", Path(__file__), ROOT / "app/generation/answer_support.py"])})
    by_key = {(r["dataset"], r["id"]): r for r in records}
    links = []

    def link(path, label, page=None):
        path = Path(path)
        if not path.is_file():
            raise ValueError("Missing report link")
        links.append(str(path))
        url = Path(os.path.relpath(path, output)).as_posix() + (f"#page={page}" if page else "")
        return '<a href="' + html.escape(url, quote=True) + '">' + html.escape(label) + '</a>'

    def detail(label, value):
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
            value if isinstance(value, str) else files.encode(value).decode()) + '</pre></details>'

    table, sections = [], []
    for row in rows:
        key = (row["dataset"], row["id"])
        original = by_key[key]
        rid = row["dataset"] + "_" + row["id"]
        table.append('<tr><td>' + html.escape(row["dataset"]) + f'</td><td><a href="#{rid}">{row["id"]}</a></td><td>'
                     + html.escape(row["original_status"]) + '</td><td>' + html.escape(row["projection"]) + '</td></tr>')
        artifacts = []
        if original["actual_native_folder"]:
            folder = Path(original["actual_native_folder"])
            artifacts = [link(folder / "api_response.json", "Исходный API"), link(folder / "request.json", "Исходный запрос модели")]
        source_links = [link(original["original_pdf_path"], f'{e["citation_id"]}:PDF{e["page_start"]}–{e["page_end"]}', e["page_start"])
                        for e in original["evidence"]]
        sections.append(f'<section id="{rid}"><h2>{rid}</h2><p>' + html.escape(original["question"])
            + '</p><p><b>Отдельная audit projection:</b> ' + html.escape(row["projection"]) + '</p>'
            + detail("Исходный service/API body — не изменён", original["original_api_body"])
            + detail("Научный аудит — finite/not general acceptance", row["audit"])
            + detail("Синтетическое решение wrapper, не новый ответ модели", row.get("guarded_result"))
            + '<p>' + ' | '.join(source_links + artifacts) + '</p></section>')
    document = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Finite answer support audit</title>'
        '<style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:24px}pre{white-space:pre-wrap;'
        'overflow-wrap:anywhere;background:#eef2f4;padding:12px}table{border-collapse:collapse;width:100%}'
        'td,th{padding:8px;border:1px solid #999}section{margin-top:30px;border-top:2px solid #456}</style>'
        '<h1>ARIADNE:статус, роль и ограниченная полнота</h1><p>Offline,0 новых model/OAuth/DB calls. '
        'Original model/API outputs неизменны. Not blocked не означает scientifically correct. '
        'Default app не включает wrapper; это явный opt-in и replay.</p>' + detail("Итоги", summary)
        + '<table><tr><th>Набор</th><th>Вопрос</th><th>Исходный результат</th><th>Audit projection</th></tr>'
        + ''.join(table) + '</table>' + ''.join(sections) + '</html>')
    files.save(output / "review.html", document.encode())
    files.write(output / "verification.json", {"records": len(rows), "existing_file_links": len(links),
        "original_claims_and_sources_unchanged": True, "wrapper_and_direct_audits_equal": True,
        "raw_anchor_observations_verified": len(witnesses), "browser_layout_verified": False})
    files.verify(read(freeze / "bindings.json"))
    files.manifest(output)
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "run"))
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    result = freeze() if args.mode == "freeze" else run()
    if policy.denied:
        raise RuntimeError("External network attempted during offline audit")
    if result is not None:
        print(json.dumps(result))
