"""Compare frozen-source window candidates without search, DB or generation."""

from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.retrieval_ablation import ARMS, candidate_bundle  # noqa: E402
from scripts.retrieval_ablation_labels import label_retention  # noqa: E402
from scripts.retrieval_loss_audit import anchor_presence  # noqa: E402
from scripts.retrieval_window_selection import QUALIFIERS, VERSION, assess_source, in_scope, rerank_window  # noqa: E402
from scripts.review_retrieval_ablation import evidence_identity, replay_arm, unpack  # noqa: E402
from scripts.run_swelling_retrieval_audit import CaptureComplete, NoGeneration  # noqa: E402

CAPTURE = ROOT / "output/retrieval_ablation_20261031/capture_v02"
PRIOR = ROOT / "output/kim_retrieval_audit_20261031/capture_v02/capture.json"
PROTOCOL = ROOT / "docs/records/retrieval_window_selection_protocol_v0.1.md"
CONTROLS = ROOT / "docs/records/retrieval_window_selection_controls_v0.1.json"


def run_candidate(value: dict[str, Any], corpus: dict[str, Any], settings: Any, qualifier: str) -> dict[str, Any]:
    from sqlalchemy.engine import Engine

    from app.generation import service
    from app.retrieval import cross_lingual, search

    restored = unpack(value, corpus)
    stages = {stage["name"]: stage for stage in restored["stages"]}
    original_rerank = search._rerank_cross_lingual_results
    request = value["request"]
    trace: dict[str, Any] = {}
    channel_calls: list[str] = []
    observations: dict[str, Any] = {}

    def response(name: str, query: str) -> Any:
        stage = stages[name]
        return search.SearchResponse(
            query=query, results=[search.SearchResult(**row) for row in stage["results"]], metadata=stage["metadata"]
        )

    bundle = (
        candidate_bundle(value["question"])
        if value["arm"] in {"expansion", "combined"}
        else cross_lingual.build_query_bundle(value["question"])
    )

    def exact(_session: Any, query: str, *args: Any, **kwargs: Any) -> Any:
        channel_calls.append(query)
        index = next(i for i, variant in enumerate(bundle.variants) if i > 0 and variant.text == query)
        return response(f"exact_search:{index + 1}:output", query)

    def rank(rows: Any, query_bundle: Any, *, window_size: int) -> Any:
        if window_size != value["limits"]["feature_window"]:
            raise ValueError("Feature window changed")
        if not in_scope(query_bundle.original):
            return original_rerank(rows, query_bundle, window_size=window_size)
        before = [asdict(row) for row in rows]
        expected = stages["_rerank_cross_lingual_results:1:input"]["results"]
        if before != expected:
            raise ValueError("Frozen candidate fusion input changed")
        candidate = rerank_window(rows, query_bundle, window_size=window_size, qualifier=qualifier)
        if [asdict(row) for row in rows] != before:
            raise ValueError("Candidate mutated raw retrieval rows")
        observations.update(candidate.metadata)
        observations["ranked_chunk_ids"] = [row.chunk_id for row in candidate.results]
        return candidate

    def observe(retrieval: Any, evidence: Any, metadata: Any) -> None:
        trace.update(retrieval=asdict(retrieval), evidence=[asdict(item) for item in evidence], metadata=metadata)

    with ExitStack() as stack:
        db = stack.enter_context(patch.object(Engine, "connect", side_effect=AssertionError("DB forbidden")))
        embedding = stack.enter_context(
            patch.object(search, "embed_query_with_fastembed", side_effect=AssertionError("Embedding forbidden"))
        )
        provider = stack.enter_context(patch.object(service, "build_answer_provider", side_effect=AssertionError("Provider forbidden")))
        stack.enter_context(patch.object(search, "hybrid_search", return_value=response("hybrid_search:1:output", value["question"])))
        stack.enter_context(patch.object(search, "exact_search", exact))
        stack.enter_context(patch.object(search, "_cross_lingual_variant_top_k", return_value=value["limits"]["variant_top_k"]))
        stack.enter_context(patch.object(search, "_cross_lingual_rerank_window_size", return_value=value["limits"]["feature_window"]))
        stack.enter_context(patch.object(search, "_rerank_cross_lingual_results", rank))
        if value["arm"] in {"expansion", "combined"}:
            stack.enter_context(patch.object(search, "build_query_bundle", candidate_bundle))
            stack.enter_context(patch.object(cross_lingual, "build_query_bundle", candidate_bundle))
        status = None
        try:
            result = service.answer_question(
                object(),
                settings,
                request["question"],
                collection=request["collection"],
                top_k=request["top_k"],
                method=request["method"],
                answer_style=request["answer_style"],
                answer_language=request["answer_language"],
                provider=NoGeneration(),
                trace_observer=observe,
            )
            status = result.status
        except CaptureComplete:
            status = "stopped_before_generation"
        if db.call_count or embedding.call_count or provider.call_count:
            raise ValueError("Forbidden operation attempted")
    if not trace or channel_calls != [variant.text for variant in bundle.variants[1:]]:
        raise ValueError("Missing trace or changed channel inventory")
    if len(trace["retrieval"]["results"]) > value["limits"]["final_top_k"]:
        raise ValueError("Final top-k increased")
    return {"trace": trace, "boundary_status": status, "observations": observations, "channel_replay_queries": channel_calls}


def windows_in(rows: list[dict[str, Any]], prior: dict[str, Any]) -> dict[str, Any]:
    return {
        window["label"]: anchor_presence(
            rows, article_id=prior["target_article_id"], page_number=window["pdf_page"], exact_text=window["exact_text"]
        )
        for window in prior["reference_windows"]
    }


def control_report() -> dict[str, Any]:
    dataset = json.loads(CONTROLS.read_bytes())
    records = []
    for control in dataset["controls"]:
        diagnosis = assess_source(control["text"])
        if diagnosis["body_coverage"] != control["body"] or diagnosis["local_relation"] != control["local"]:
            raise ValueError("Frozen control cue result differs: " + control["id"])
        records.append({**control, "diagnosis": diagnosis})
    return {
        "origin": dataset["origin"],
        "records": records,
        "qualifiers": {
            qualifier: {
                "qualified_positive_controls": [
                    row["id"] for row in records if row["diagnosis"][qualifier] and row["development_relation"]
                ],
                "false_qualifications": [row["id"] for row in records if row["diagnosis"][qualifier] and not row["development_relation"]],
                "false_refusals": [row["id"] for row in records if not row["diagnosis"][qualifier] and row["development_relation"]],
            }
            for qualifier in QUALIFIERS
        },
    }


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return "<details><summary>" + esc(label) + "</summary><pre>" + esc(raw) + "</pre></details>"

    body = (
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: отбор feature window</title>'
        "<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}"
        "[hidden]{display:none!important}</style><h1>Offline: отбор фрагментов до feature cutoff</h1><p>"
        + esc(VERSION)
        + ". Исходный snapshot: retrieval_ablation_20261031/capture_v02. "
        "Рабочий поиск не менялся; model/OAuth/DB/embedding calls и slots: 0. "
        "75% работ плана качества ответов; независимая научная оценка открыта.</p>"
        "<p>Два признака: совместное наличие пяти понятий в raw chunk и локальная фраза с dependency cue. "
        "Оба — ограниченные предложения отбора; научная достаточность и принадлежность условий не подтверждены.</p>"
        + detail("Итоги", report["summary"])
        + detail("Контрпримеры, включая ложные допуски и отказы", report["controls"])
        + "<h2>Восемь exposed source anchors в конечном evidence</h2><table><thead><tr>"
        "<th>Question</th><th>Frozen retrieval arm</th><th>Candidate</th><th>Before</th><th>After</th>"
        "<th>Gained</th><th>Lost</th></tr></thead><tbody>"
    )
    for row in report["comparisons"]:
        if row["reference_windows"] is None:
            continue
        anchors = row["reference_windows"]
        body += (
            "<tr><td>"
            + esc(row["case_id"])
            + "</td><td>"
            + esc(row["arm"])
            + "</td><td>"
            + esc(row["qualifier"])
            + "</td><td>"
            + str(len(anchors["before"]))
            + "/8</td><td>"
            + str(len(anchors["after"]))
            + "/8</td><td>"
            + esc(anchors["gained"])
            + "</td><td>"
            + esc(anchors["lost"])
            + "</td></tr>"
        )
    body += "</tbody></table><h2>Все случаи: изменения и неизменные ограничения</h2>"
    for row in report["comparisons"]:
        body += detail(row["case_id"] + " / " + row["arm"] + " / " + row["qualifier"], row)
    body += "<h2>Полные actual evidence и диагностика scoped cases; новых ответов модели нет</h2>"
    for record in report["scoped_records"]:
        body += detail(record["case_id"] + " / " + record["arm"] + " / " + record["qualifier"], record)
    body += "<h2>Проверенные source windows</h2>"
    for window in report["reference_windows"]:
        body += (
            '<p><a href="'
            + esc(Path(window["original_pdf_path"]).as_uri() + "#page=" + str(window["pdf_page"]))
            + '">'
            + esc(window["label"])
            + ", PDF с."
            + str(window["pdf_page"])
            + "</a></p>"
            + detail("Точный фрагмент; не вход кандидата", window)
        )
    body += (
        "<h2>TAC: все 33 работы исходного корпуса</h2><p>Сохранённые метаданные snapshot, "
        "не новая выгрузка БД. Неизвестные и несобранные поля явно отмечены.</p>"
        '<label>Поиск по TAC <input id="q" type="search"></label><table id="tac"><thead><tr>'
        + "".join(
            "<th>" + label + "</th>"
            for label in ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "hyperlink to original file")
        )
        + "</tr></thead><tbody>"
    )
    for article in report["articles"]:
        body += "<tr data-row>"
        for key in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"):
            body += "<td>" + ("Неизвестно / не собрано" if article[key] is None else detail("Полное значение", article[key])) + "</td>"
        body += (
            '<td><a href="'
            + esc(Path(article["original_pdf_path"]).as_uri())
            + '">Оригинальный PDF</a>'
            + detail("Происхождение и диагностика", article)
            + "</td></tr>"
        )
    body += (
        '</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
        'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});'
        "</script></html>"
    )
    files.save(output / "review.html", body.encode("utf-8"))


def run(output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    files.verify_manifest(CAPTURE)
    capture = json.loads((CAPTURE / "capture.json").read_bytes())
    files.verify(capture["bindings"])
    corpus = json.loads((CAPTURE / "corpus.json").read_bytes())
    articles = json.loads((CAPTURE / "articles.json").read_bytes())
    cases = json.loads((CAPTURE / "cases.json").read_bytes())["cases"]
    prior = json.loads(PRIOR.read_bytes())
    bound_paths = [
        Path(__file__),
        ROOT / "scripts/retrieval_window_selection.py",
        PROTOCOL,
        CONTROLS,
        ROOT / "docs/query_rewriting_2026-11-02.md",
        ROOT / "tests/unit/test_retrieval_window_selection.py",
        ROOT / "scripts/review_retrieval_ablation.py",
        ROOT / "scripts/review_swelling_retrieval_audit.py",
        ROOT / "scripts/retrieval_ablation_labels.py",
        ROOT / "scripts/retrieval_loss_audit.py",
        ROOT / "scripts/retrieval_ablation.py",
        ROOT / "scripts/gigachat_answer_smoke.py",
        PRIOR,
        *[CAPTURE / name for name in ("capture.json", "manifest.json", "cases.json", "corpus.json", "articles.json")],
    ]
    bindings = {**capture["bindings"], **files.bindings(bound_paths)}
    controls = control_report()
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    # Snapshot algorithm/protocol/controls before the first corpus measurement.
    for path in bound_paths:
        if path.is_relative_to(ROOT / "scripts") or path.is_relative_to(ROOT / "docs") or path.is_relative_to(ROOT / "tests"):
            destination = output / "source_snapshot" / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            files.save(destination, path.read_bytes())
    files.write(output / "frozen_inputs.json", {"version": VERSION, "bindings": bindings})
    comparisons, scoped_records, replays = [], [], []
    boundary_control = raw_control = False
    for index, case in enumerate(cases):
        for arm in ARMS:
            value = json.loads((CAPTURE / f"cases/{index:03d}_{arm}.json").read_bytes())
            proof = replay_arm(value, corpus, settings)
            replays.append({"case_id": case["id"], "arm": arm, **proof})
            if index == 0 and arm == "baseline":
                broken = copy.deepcopy(value)
                next(stage for stage in broken["stages"] if stage["name"] == "_diversify_cross_lingual_results:2:output")[
                    "results"
                ].reverse()
                try:
                    replay_arm(broken, corpus, settings)
                except ValueError as exc:
                    if str(exc) != "Replay differs at _diversify_cross_lingual_results:2:output":
                        raise
                    boundary_control = True
                else:
                    raise ValueError("Corrupt boundary accepted")
                damaged_corpus = copy.deepcopy(corpus)
                chunk_id = value["stages"][0]["results"][0]["chunk_id"]
                damaged_corpus[chunk_id]["full_text"] += " corrupt"
                try:
                    unpack(value, damaged_corpus)
                except ValueError as exc:
                    if str(exc) != "Packed raw source differs":
                        raise
                    raw_control = True
                else:
                    raise ValueError("Corrupt raw source accepted")
            before = value["trace"]
            before_labels = label_retention(case, before["retrieval"]["results"], articles)
            for qualifier in QUALIFIERS:
                candidate = run_candidate(value, corpus, settings, qualifier)
                # Actual second execution, not a comparison of a copy with itself.
                repeated = run_candidate(value, corpus, settings, qualifier)
                if candidate != repeated:
                    raise ValueError("Candidate execution is not reproducible")
                after = candidate["trace"]
                scoped = in_scope(case["query"])
                identical = after == before
                if not scoped and not identical:
                    raise ValueError("Out-of-scope full trace changed")
                labels = label_retention(case, after["retrieval"]["results"], articles)
                anchors = None
                if case.get("evaluate_reference_windows"):
                    old = [key for key, item in windows_in(before["evidence"], prior).items() if item["anchor_present"]]
                    new = [key for key, item in windows_in(after["evidence"], prior).items() if item["anchor_present"]]
                    observations = candidate["observations"]
                    stage_ids = {"selected_window": observations["selected_window_chunk_ids"], "ranked": observations["ranked_chunk_ids"]}
                    restored_stages = {stage["name"]: stage for stage in unpack(value, corpus)["stages"]}
                    rows = {row["chunk_id"]: row for row in restored_stages["_rerank_cross_lingual_results:1:input"]["results"]}
                    anchors = {
                        "before": old,
                        "after": new,
                        "gained": sorted(set(new) - set(old)),
                        "lost": sorted(set(old) - set(new)),
                        "candidate_stages": {
                            name: windows_in([rows[identity] for identity in ids], prior) for name, ids in stage_ids.items()
                        },
                    }
                changed = {
                    "case_id": case["id"],
                    "query": case["query"],
                    "origin": case["origin"],
                    "arm": arm,
                    "qualifier": qualifier,
                    "in_scope": scoped,
                    "full_trace_identical": identical,
                    "candidate_repeated_execution_identical": True,
                    "limits": value["limits"],
                    "evidence_identity_order_changed": evidence_identity(before) != evidence_identity(after),
                    "full_evidence_records_changed": before["evidence"] != after["evidence"],
                    "baseline_article_labels": before_labels,
                    "candidate_article_labels": labels,
                    "labelled_article_identities_lost": sorted(
                        set(before_labels["matching_article_ids"]) - set(labels["matching_article_ids"])
                    ),
                    "labelled_article_identities_gained": sorted(
                        set(labels["matching_article_ids"]) - set(before_labels["matching_article_ids"])
                    ),
                    "fixture_answerable": case.get("answerable"),
                    "before_boundary_status": value["boundary_status"],
                    "after_boundary_status": candidate["boundary_status"],
                    "before_adequacy": before["metadata"]["evidence_adequacy"],
                    "after_adequacy": after["metadata"]["evidence_adequacy"],
                    "reference_windows": anchors,
                }
                comparisons.append(changed)
                if scoped:
                    record = {"case_id": case["id"], "arm": arm, "qualifier": qualifier, **candidate}
                    scoped_records.append(record)
                    files.write(output / f"cases/{index:03d}_{arm}_{qualifier}.json", record)
        print(json.dumps({"completed_case": index + 1, "total_cases": len(cases)}), flush=True)
    # Fresh source verification uses original PDF text, not a historical rendering tool.
    import fitz

    for article in articles.values():
        if files.sha(Path(article["original_pdf_path"]).read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
    for window in prior["reference_windows"]:
        with fitz.open(window["original_pdf_path"]) as pdf:
            page = pdf[window["pdf_page"] - 1].get_text()
        if window["exact_text"] not in page:
            raise ValueError("Fresh PDF anchor differs: " + window["label"])
    files.verify(bindings)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    summary = {
        "version": VERSION,
        "case_count": len(cases),
        "frozen_arms": list(ARMS),
        "baseline_replays": len(replays),
        "candidate_comparisons": len(comparisons),
        "candidate_service_executions_including_repeats": 2 * len(comparisons),
        "scoped_comparisons": sum(row["in_scope"] for row in comparisons),
        "out_of_scope_exact_noops": sum(not row["in_scope"] and row["full_trace_identical"] for row in comparisons),
        "corrupted_boundary_rejected": boundary_control,
        "corrupted_raw_source_rejected": raw_control,
        "pdf_hashes_checked": len(articles),
        "fresh_reference_windows": len(prior["reference_windows"]),
        "binding_count": len(bindings),
        "runtime_changed": False,
        "db_calls": 0,
        "embedding_calls": 0,
        "model_calls": 0,
        "oauth_calls": 0,
        "slot_reservations": 0,
        "network_denials": policy.denied,
        "independent_accuracy": None,
        "scientific_acceptance": "not_established",
        "plan_completion_percent": 75,
        "qualifiers": {
            qualifier: {
                "evidence_changed_comparisons": sum(
                    row["evidence_identity_order_changed"] for row in comparisons if row["qualifier"] == qualifier
                ),
                "article_identity_losses": [
                    row["case_id"] + "/" + row["arm"]
                    for row in comparisons
                    if row["qualifier"] == qualifier and row["labelled_article_identities_lost"]
                ],
                "adequacy_boolean_changes": [
                    row["case_id"] + "/" + row["arm"]
                    for row in comparisons
                    if row["qualifier"] == qualifier and row["before_adequacy"]["adequate"] != row["after_adequacy"]["adequate"]
                ],
            }
            for qualifier in QUALIFIERS
        },
    }
    report = {
        "summary": summary,
        "bindings": bindings,
        "controls": controls,
        "comparisons": comparisons,
        "scoped_records": scoped_records,
        "baseline_replays": replays,
        "articles": list(articles.values()),
        "reference_windows": prior["reference_windows"],
    }
    files.write(output / "report.json", report)
    render(report, output)
    files.manifest(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(run(args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
