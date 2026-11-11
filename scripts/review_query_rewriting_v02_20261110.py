"""Closed-scope comparison across original, rewriting v0.1 and v0.2, with explicit native reuse."""

import html
import json
import os
from collections import Counter
from pathlib import Path

from scripts import gigachat_answer_smoke as f
from scripts import run_query_rewriting_v02_20261110 as run


def read(path):
    return json.loads(path.read_bytes())


def reuse_result(prepared, digest):
    slot = f.LEDGER / digest
    attempt = read(slot / "attempt.json")
    folder = Path(attempt["output"]).resolve()
    if not folder.is_relative_to((f.ROOT / "output").resolve()):
        raise ValueError("Prior native output outside declared workspace output tree")
    f.verify_manifest(folder)
    if (folder / "request.json").read_bytes() != (prepared / "request.json").read_bytes():
        raise ValueError("Reused result is not for identical native bytes")
    if f.sha((folder / "request.json").read_bytes()) != digest:
        raise ValueError("Reused digest mismatch")
    result = read(slot / "result.json")
    if result != read(folder / "result.json"):
        raise ValueError("Prior ledger and output differ")
    return result, folder


def main():
    base = run.BASE
    if read(base / "answers_closed_v01.json")["remaining_allowance"] or read(base / "rewrite_closed_v01.json")["remaining_allowance"]:
        raise ValueError("Both scopes must close before comparison")
    for name in ("input_freeze_v01", "plans_freeze_v01", "offline_replay_v01"):
        f.verify_manifest(base / name)
    f.verify(read(base / "input_freeze_v01/runtime.json")["input_bindings"])
    f.verify(read(base / "plans_freeze_v01/bindings.json"))
    old = f.ROOT / "output/satoh_fan_qa_run_20261110"
    for parent in (old / "review_v01", run.OLD / "review_v01"):
        f.verify_manifest(parent)
        f.verify(read(parent / "report.json")["bindings"])
    original = {c["id"]: c for c in read(old / "review_v01/report.json")["cases"]}
    v1 = {c["id"]: c for c in read(run.OLD / "review_v01/report.json")["cases"]}
    catalog = read(run.INTAKE)
    refs = {c["id"]: c for c in catalog["parsed"]["cases"]}
    titles = read(base / "input_freeze_v01/title_contexts.json")
    if f.sha(run.INTAKE.read_bytes()) != titles["title_catalog_sha256"]:
        raise ValueError("Original title catalog changed")
    for label, proof in titles["proofs"].items():
        page = next(p for p in catalog["sources"][label]["pages"] if p["pdf_page"] == 1)
        if page["text"][proof["start"]:proof["end"]] != proof["raw_title"]:
            raise ValueError("First-page title span changed")
    cases = read(base / "input_freeze_v01/questions.json")["cases"]
    if cases != read(old / "input_freeze_v01/questions.json")["cases"]:
        raise ValueError("Original questions changed")
    plans = {c["id"]: c for c in read(base / "plans_freeze_v01/plans.json")["cases"]}
    out = base / "review_v01"
    rows, cards, table, links = [], [], [], []
    bindings = f.bindings([Path(__file__), base / "answers_closed_v01.json", base / "rewrite_closed_v01.json",
        base / "answer_approval_v01.json", base / "plans_freeze_v01/manifest.json", base / "offline_replay_v01/manifest.json",
        run.INTAKE, old / "review_v01/manifest.json", run.OLD / "review_v01/manifest.json"])

    def link(path, label, page=None):
        if not path.is_file():
            raise ValueError("Missing report link: " + str(path))
        links.append(str(path))
        url = Path(os.path.relpath(path, out)).as_posix() + (f"#page={page}" if page else "")
        return '<a href="' + html.escape(url, quote=True) + '">' + html.escape(label) + '</a>'

    def detail(label, value):
        text = value if isinstance(value, str) else f.encode(value).decode()
        return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(text) + '</pre></details>'

    for case in cases:
        cid = case["id"]
        prepared, folder = base / "prepared_v01" / cid, base / "answers" / cid
        f.verify_manifest(prepared)
        result = read(folder / "result.json")
        effective, native_folder = result, None
        if result["status"] == "identical_native_reuse":
            effective, native_folder = reuse_result(prepared, result["request_sha256"])
        elif (folder / "live").exists():
            native_folder = folder / "live"
            f.verify_manifest(native_folder)
            if read(native_folder / "result.json") != result:
                raise ValueError("Case/live result mismatch")
            slot = f.LEDGER / read(prepared / "contract.json")["request_sha256"]
            if read(slot / "result.json") != result or read(slot / "query_rewriting_answer_closed_v01.json")["resend_authorized"]:
                raise ValueError("New slot result/closure mismatch")
            for name in ("trace.json", "sources.json", "articles.json", "request.json"):
                if (native_folder / name).exists() and (native_folder / name).read_bytes() != (prepared / name).read_bytes():
                    raise ValueError("Actual ASGI inputs differ from preparation")
        if native_folder:
            raw = (native_folder / "response.bin").read_bytes()
            if f.sha(raw) != effective["stored_response_sha256"]:
                raise ValueError("Native response changed")
            bindings.update(f.bindings([native_folder / "manifest.json"]))
        answer = effective.get("answer", {})
        trace = read(prepared / "trace.json") if (prepared / "trace.json").exists() else None
        evidence = trace["evidence"] if trace else []
        if any(e["article_id"] != case["article_id"] for e in evidence):
            raise ValueError("Selected evidence left target article")
        declared = set(refs[cid]["source_locations"]["pdf_pages"] + refs[cid]["source_locations"]["named_methods_pdf_pages"])
        selected = {p for e in evidence for p in range(e["page_start"], e["page_end"] + 1)}
        row = {"id": cid, "question": case["question_original"], "original_status": original[cid]["status"],
            "v01_status": v1[cid]["result"]["status"], "v01_answer": v1[cid]["answer"], "v02_status": result["status"],
            "effective_status": effective["status"], "result": result, "answer": answer, "plan": plans[cid],
            "effective_native_folder": str(native_folder) if native_folder else None,
            "selected_raw_evidence": evidence, "declared_reference_pages": sorted(declared),
            "v02_reference_pages_outside_ranges": sorted(declared - selected),
            "v01_reference_pages_outside_ranges": v1[cid]["new_declared_pages_outside_ranges"],
            "reference": refs[cid]["reference_answer_span"], "source_pointer": refs[cid]["source_pointer_span"],
            "independent_accuracy": None, "score": None, "scientific_validity": "not_evaluated"}
        rows.append(row)
        artifacts = [link(base / "rewrites" / cid / "result.json", "Переписывание"),
                     link(base / "rewrites" / cid / "plan.json", "План")]
        if trace:
            artifacts.append(link(prepared / "trace.json", "Новый trace"))
        if native_folder:
            artifacts.extend([link(native_folder / "api_response.json", "Исходный API-ответ"),
                              link(native_folder / "response.bin", "Исходный native")])
        source_links = [link(Path(case["original_pdf_path"]), f'{e["citation_id"]}: PDF{e["page_start"]}–{e["page_end"]}',
                             e["page_start"]) for e in evidence]
        table.append(f'<tr><td><a href="#{cid}">{cid}</a></td><td>' + html.escape(original[cid]["status"])
            + '</td><td>' + html.escape(row["v01_status"]) + '</td><td>' + html.escape(row["effective_status"])
            + '</td><td>' + ('старый exact input' if result["status"] == "identical_native_reuse" else 'новый результат') + '</td></tr>')
        cards.append(f'<section id="{cid}"><h2>{cid}</h2><p>' + html.escape(case["question_original"])
            + '</p>' + detail("Перевод/проверки/diagnostics", plans[cid])
            + '<h3>v0.2:ответ</h3><pre>' + html.escape(answer.get("answer") or answer.get("detail") or effective["status"])
            + '</pre>' + detail("v0.1:ответ", row["v01_answer"])
            + detail("Эталон пользователя — exposed development", refs[cid]["reference_answer_span"]["text"])
            + detail("PDF locations — только пересечение диапазонов",
                     {"declared": sorted(declared), "outside": row["v02_reference_pages_outside_ranges"]})
            + '<p>' + ' | '.join(source_links) + '</p>' + detail("Raw evidence", evidence)
            + detail("Полный результат/статус reuse", result) + '<p>' + ' | '.join(artifacts) + '</p></section>')
        bindings.update(f.bindings([prepared / "manifest.json", base / "rewrites" / cid / "manifest.json"]))
    rewrites = [read(base / "rewrites" / c["id"] / "result.json") for c in cases]
    offline = read(base / "offline_replay_v01/report.json")
    summary = {"version": run.qr.VERSION, "cases": 20, "original_answered": 4, "v01_answered": 11,
        "v02_effective_answered": sum(r["answer"].get("status") == "answered" for r in rows),
        "fresh_answered": sum(r["v02_status"] == "runtime_answered" for r in rows),
        "status_counts": dict(Counter(r["v02_status"] for r in rows)),
        "effective_status_counts": dict(Counter(r["effective_status"] for r in rows)),
        "rewrite_schema_valid": sum(r["status"] == "rewrite_valid" for r in rewrites),
        "meaning_accepted": sum(r["plan"]["accepted"] for r in rows),
        "offline_old_translations_usable": sum(c["plan"] is not None for c in offline["cases"]),
        "rewrite_model_attempts": sum(r["model_attempts"] for r in rewrites),
        "answer_model_attempts": sum(r["result"]["model_attempts"] for r in rows),
        "rewrite_oauth_attempts": sum(r["oauth_attempts"] for r in rewrites),
        "answer_oauth_attempts": sum(r["result"]["oauth_attempts"] for r in rows),
        "usage": {stage: {k: sum((r.get("usage") or {}).get(k, 0) for r in values)
                          for k in ("prompt_tokens", "completion_tokens", "total_tokens", "precached_prompt_tokens")}
                  for stage, values in (("rewrite", rewrites), ("answer", [r["result"] for r in rows]))},
        "cases_with_auxiliary_normalization_diagnostics": sum(
            bool(read(base / "rewrites" / r["id"] / "plan.json")["normalization_diagnostics"]) for r in rows),
        "v02_cases_with_reference_page_gaps": sum(bool(r["v02_reference_pages_outside_ranges"]) for r in rows),
        "new_model_samples_exclude_reuse": True, "cost": None, "score": None, "independent_accuracy": None,
        "all_allowances_closed": True, "default_product_changes": 0,
        "limitations": ["agent meaning review, exposed references, no independent evaluation",
            "v0.1 ranking/admission/answer policies retained; context/completeness not repaired",
            "fresh vs identical-input reuse explicitly separated; no new sample for reused response",
            "finite identifier/number/title guards do not prove semantic equivalence",
            "no fresh PDF extraction/visual/browser/full application tests/deployment"]}
    report = {"summary": summary, "cases": rows, "title_proofs": titles["proofs"], "bindings": bindings}
    f.verify(bindings)
    out.mkdir(exist_ok=False)
    f.write(out / "report.json", report)
    document = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE query rewriting v0.2</title>'
        '<style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:24px}pre{white-space:pre-wrap;'
        'overflow-wrap:anywhere;background:#eef2f4;padding:12px}table{border-collapse:collapse;width:100%}'
        'th,td{padding:8px;border:1px solid #999}section{margin-top:32px;border-top:2px solid #456}</style>'
        '<h1>Query rewriting v0.2:20 вопросов</h1><p>Development с agent meaning review. '
        'Выданный ответ/пересечение страниц не означают научную корректность. Exact-input reuse — старый model sample.</p>'
        + detail("Итоги и ограничения", summary) + detail("Verified title bindings", titles["proofs"])
        + '<table><tr><th>Вопрос</th><th>Исходный</th><th>v0.1</th><th>v0.2 effective</th><th>Происхождение</th></tr>'
        + ''.join(table) + '</table>' + ''.join(cards) + '</html>')
    f.save(out / "review.html", document.encode())
    f.write(out / "verification.json", {"cases": 20, "file_links_checked": len(links), "bindings_verified": len(bindings)})
    f.manifest(out)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
