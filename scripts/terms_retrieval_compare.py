"""Offline development comparison of saved retrieval with explicit TAC/Terms adapters."""
from __future__ import annotations

import argparse
import html
import json
import sqlite3
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from app.evaluation.retrieval import _evaluate_extended_question, load_extended_questions
from app.retrieval.cross_lingual import build_query_bundle
from app.retrieval.search import SearchResponse, SearchResult
from scripts.tac_experiment import digest, json_default, lexical_score, rank_tac, staged_replay, tac_response, validate_profiles
from scripts.tac_term_classification import validate_classification
from scripts.tac_term_contexts import validate_contexts, verify_pdfs

VERSION = "terms_retrieval_frozen_replay_v0.1"
METHODS = {
    "production": "Прежний hybrid_cross_lingual",
    "tac_soft": "TAC + полный текст, soft",
    "tac_typed_soft": "TAC + размеченные Terms + полный текст, soft",
    "tac_all_soft": "TAC + все Terms + полный текст, soft",
    "tac_only": "Только TAC, диагностика",
    "tac_rescue": "TAC shortlist + full-text rescue",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def common_pool(production: list[SearchResult], expanded: list[SearchResult]) -> list[SearchResult]:
    """Preserve the original baseline prefix, then add distinct expanded candidates."""
    require(len({r.chunk_id for r in production}) == len(production), "Duplicate production chunk")
    require(len({r.chunk_id for r in expanded}) == len(expanded), "Duplicate expanded chunk")
    seen = {r.chunk_id for r in production}
    return [*production, *(r for r in expanded if r.chunk_id not in seen)]


def term_signals(pool: list[SearchResult], contexts: dict[str, Any], classification: dict[str, Any],
                 *, typed: bool) -> dict[str, list[dict[str, Any]]]:
    """Require page/layer overlap and exact quote membership; infer no scientific attachment."""
    articles = {a["article_id"]: a for a in contexts["articles"]}
    classified = {a["article_id"]: a for a in classification["articles"]}
    output = {}
    for result in pool:
        article = articles[result.article_id]
        terms = {t["term_id"]: t for t in article["terms"]}
        mentions = {m["mention_id"]: m["source"] for m in article["mentions"]}
        eligible = {a["use_id"] for a in classified[result.article_id]["assignments"]
                    if a["axis"] == "type" and a["state"] == "proposed"}
        records = []
        for use in article["uses"]:
            source = mentions[use["mention_id"]]
            if typed and use["use_id"] not in eligible:
                continue
            if (result.page_start <= source["page_number"] <= result.page_end
                    and source["text_layer"] == result.text_layer
                    and source["quote"] in (result.full_text or "")):
                records.append({"term_id": use["term_id"], "term": terms[use["term_id"]]["term"],
                                "use_id": use["use_id"], "source": source})
        output[result.chunk_id] = records
    return output


def rank_terms(pool: list[SearchResult], signals: dict[str, list[dict[str, Any]]],
               variants: list[str]) -> list[dict[str, Any]]:
    ranked = []
    for order, result in enumerate(pool):
        labels = sorted({r["term"] for r in signals[result.chunk_id]})
        score = max((lexical_score(v, "\n".join(labels)) for v in variants), default=0.0)
        if score > 0:
            matched = [r for r in signals[result.chunk_id] if any(lexical_score(v, r["term"]) > 0 for v in variants)]
            ranked.append({"chunk_id": result.chunk_id, "score": score, "pool_order": order,
                           "matched_term_ids": sorted({r["term_id"] for r in matched}),
                           "matched_use_ids": sorted({r["use_id"] for r in matched})})
    ranked.sort(key=lambda r: (-r["score"], r["pool_order"]))
    return ranked


def fuse(pool: list[SearchResult], tac_ranks: dict[str, int], term_ranks: dict[str, int],
         *, top_k: int, rrf_k: int = 60) -> list[SearchResult]:
    """Equal-weight soft fusion, with full baseline candidates kept in the pool."""
    require(top_k > 0 and rrf_k > 0, "Invalid retrieval depth or RRF constant")
    scored = []
    for order, result in enumerate(pool):
        score = 1 / (rrf_k + order + 1)
        ranks = {"common_pool": order + 1}
        if result.article_id in tac_ranks:
            ranks["tac_article"] = tac_ranks[result.article_id]
            score += 1 / (rrf_k + ranks["tac_article"])
        if result.chunk_id in term_ranks:
            ranks["terms_chunk"] = term_ranks[result.chunk_id]
            score += 1 / (rrf_k + ranks["terms_chunk"])
        scored.append((score, order, replace(result, score=score,
                                            retrieval_method="experimental_tac_terms_rrf",
                                            method_scores={"fusion": score}, method_ranks=ranks)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:top_k]]


def result_from_saved(row: dict[str, Any], chunks: dict[str, tuple[dict[str, Any], dict[str, Any]]]) -> SearchResult:
    article, source = chunks[row["chunk_id"]]
    for key in ("page_start", "page_end", "source_type", "text_layer"):
        require(row[key] == source[key], "Saved result source differs: " + key)
    require(row["article_id"] == article["article_id"], "Saved result article differs")
    if "full_text" in row:
        require(row["full_text"] == source["text"], "Saved result text differs")
    payload = {key: value for key, value in row.items() if key in {f.name for f in fields(SearchResult)}}
    payload["full_text"] = source["text"]
    return SearchResult(**payload)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for method in METHODS:
        results = [q["methods"][method] for q in rows]
        answerable = [r for r in results if r["answerable"]]

        def mean(key: str, source: list[dict[str, Any]] = answerable) -> float | None:
            values = [r[key] for r in source if r[key] is not None]
            return sum(values) / len(values) if values else None

        output[method] = {
            "passed": sum(r["passed"] for r in results), "total": len(results),
            "answerable_count": len(answerable), "top1_hits": sum(r["top_1_passed"] for r in answerable),
            "article_recall": mean("article_recall_at_k"), "chunk_recall": mean("chunk_recall_at_k"),
            "mrr": mean("mrr"), "ndcg": mean("ndcg_at_k"),
            "judged_hit_fraction": mean("article_precision_at_k"),
            "negative_failures": sum(not r["passed"] for r in results if not r["answerable"]),
            "trace_complete": all(r["evidence_trace_complete"] for r in results),
            "regressions": [q["id"] for q in rows if q["methods"]["production"]["passed"]
                            and not q["methods"][method]["passed"]],
            "rank_improved": [q["id"] for q in rows if q["answerable"] and
                              (q["methods"][method]["mrr"] or 0) > (q["methods"]["production"]["mrr"] or 0)],
            "rank_worsened": [q["id"] for q in rows if q["answerable"] and
                              (q["methods"][method]["mrr"] or 0) < (q["methods"]["production"]["mrr"] or 0)],
        }
    base, candidate = output["production"], output["tac_typed_soft"]
    output["decision"] = {
        "recall_not_lower": candidate["article_recall"] >= base["article_recall"]
                            and candidate["chunk_recall"] >= base["chunk_recall"],
        "no_additional_negative_failures": candidate["negative_failures"] <= base["negative_failures"],
        "trace_complete": candidate["trace_complete"],
        "ranking_gain": candidate["mrr"] > base["mrr"] or candidate["ndcg"] > base["ndcg"],
    }
    output["decision"]["accepted_for_bounded_adapter"] = all(output["decision"].values())
    return output


def work_ranks(result: dict[str, Any], work_ids: dict[str, str]) -> dict[str, Any]:
    seen = set()
    relevance = []
    for row, judgment in zip(result["results"], result["result_relevances"], strict=True):
        work = work_ids[row["article_id"]]
        if work not in seen:
            seen.add(work)
            relevance.append(judgment)
    first = next((i for i, value in enumerate(relevance, 1) if value > 0), None)
    return {"unique_returned_works": len(seen), "first_judged_work_rank": first,
            "mrr": 1 / first if first else 0.0}


def render_html(report: dict[str, Any], snapshot: dict[str, Any], root: Path) -> str:
    def escape(value: object) -> str:
        return html.escape(str(value), quote=True)
    articles = {a["article_id"]: a for a in snapshot["articles"]}
    chunks = {c["chunk_id"]: c for a in snapshot["articles"] for c in a["chunks"]}
    summary_rows = []
    for key, title in METHODS.items():
        row = report["summary"][key]
        summary_rows.append(f'<tr><td>{escape(title)}</td><td>{row["passed"]}/{row["total"]}</td>'
                            f'<td>{row["top1_hits"]}/38</td><td>{row["article_recall"]:.1%}</td>'
                            f'<td>{row["chunk_recall"]:.1%}</td><td>{row["mrr"]:.4f}</td>'
                            f'<td>{row["ndcg"]:.4f}</td><td>{row["negative_failures"]}/8</td></tr>')
    question_rows = []
    for q in report["questions"]:
        cells = [f'<td><b>{escape(q["id"])}</b><p>{escape(q["query"])}</p>'
                 f'<p>Ожидается ответ: {escape(q["answerable"])} · pool: {q["common_pool_count"]}</p></td>']
        for key in METHODS:
            result = q["methods"][key]
            references = []
            for rank, (r, judgment) in enumerate(zip(result["results"], result["result_relevances"], strict=True), 1):
                article = articles[r["article_id"]]
                pdf = (root / article["original_pdf_path"]).resolve().as_uri()
                original_asset = digest(article["original_pdf_path"].encode())
                online = (f'http://127.0.0.1:8766/ui/terms-review/asset?snapshot={report["terms_snapshot_id"]}'
                          f'&asset={original_asset}#page={r["page_start"]}')
                text = chunks[r["chunk_id"]]["text"] if r["chunk_id"] in chunks else r["snippet"]
                references.append(
                    f'<details><summary>{rank}. {escape(r["title"])} · стр. '
                    f'{r["page_start"]}–{r["page_end"]} · judgment {judgment}</summary>'
                    f'<p><a href="{escape(online)}" target="_blank" rel="noopener">PDF в Atlas</a> · '
                    f'<a href="{escape(pdf)}#page={r["page_start"]}" target="_blank" rel="noopener">Локальный PDF</a></p>'
                    f'<p class="id">{escape(r["article_id"])} · {escape(r["chunk_id"])} · '
                    f'{escape(r["source_type"])} · {escape(r["text_layer"])}</p><pre>{escape(text)}</pre></details>')
            state = "Прошёл" if result["passed"] else "Не прошёл"
            rank = result["rank_of_first_relevant"] or "—"
            missing = json.dumps({"articles": result["missing_expected_articles"],
                                  "chunks": result["missing_expected_chunks"]}, ensure_ascii=False, default=json_default)
            cells.append(f'<td class="{"pass" if result["passed"] else "fail"}"><b>{state}</b> · первая нужная: {rank}'
                         f'<details><summary>Выдача ({result["result_count"]})</summary>{"".join(references)}</details>'
                         f'<details><summary>Диагностика</summary><pre>{escape(missing)}</pre>'
                         f'<pre>{escape(json.dumps(result["evidence_adequacy"], ensure_ascii=False, indent=2))}</pre>'
                         '</details></td>')
        question_rows.append('<tr class="question-row">' + "".join(cells) + '</tr>')
    decision = report["summary"]["decision"]
    return '''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARIADNE — сравнение TAC + Terms</title><style>
body{margin:24px;background:#f5f7fa;color:#183047;font:15px/1.5 system-ui,sans-serif}h1{margin-bottom:8px}
table{border-collapse:collapse;background:white;width:100%}th,td{padding:10px;border:1px solid #d8e1ea;vertical-align:top;text-align:left}
th{background:#254159;color:white}.scroll{overflow:auto}.comparisons{min-width:1900px}.comparisons td{min-width:240px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f1f4f8;padding:10px}.id{font-size:11px;overflow-wrap:anywhere}
details{margin:8px 0}summary{cursor:pointer}.pass{background:#f0f8f4}.fail{background:#fff0ee}
input{font:inherit;padding:10px;width:min(650px,90%)}
a{color:#17699b}.note{max-width:1100px}.toolbar{padding:16px 0;position:sticky;top:0;background:#f5f7fa}
</style></head><body>''' + (
        '<h1>TAC + Terms против прежнего поиска</h1>'
        '<p>33 документа · 619 chunks · 46 известных вопросов: 38 ответных, 8 отрицательных · top-10</p>'
        '<p class="note">Frozen replay, отдельный экспериментальный адаптер. Нет новых поисковых/model вызовов, '
        'измерения пользовательского времени или независимой научной оценки. Production не изменён.</p>'
        f'<p class="id">Terms snapshot: {escape(report["terms_snapshot_id"])}<br>'
        f'Corpus: {escape(report["input_sha256"]["snapshot"])}</p>'
        '<p><a href="ARIADNE_TAC_33_documents.html">Полная таблица TAC — все 33 документа</a> · '
        '<a href="report.json">Полные результаты JSON</a> · <a href="protocol.md">Протокол до оценки</a></p>'
        '<table><thead><tr><th>Метод</th><th>Прошли</th><th>Top-1</th><th>Article recall</th><th>Judged chunk recall</th>'
        '<th>MRR</th><th>nDCG</th><th>Ошибки на отрицательных</th></tr></thead><tbody>'
        + "".join(summary_rows) + '</tbody></table>'
        '<p class="note">Judgments неполные; lexical text_contains не подтверждает научную связь. '
        'Только TAC возвращает пять сводок статей, остальные варианты — десять полнотекстовых фрагментов. '
        'Unknown/conflict Terms не участвуют в typed-сигнале, но полный текст остаётся в общем pool.</p>'
        f'<p>Принятие ограниченного адаптера по заранее заданным условиям: <b>{escape(decision["accepted_for_bounded_adapter"])}</b>.</p>'
        f'<pre>{escape(json.dumps(decision, ensure_ascii=False, indent=2))}</pre>'
        '<div class="toolbar"><input id="search" type="search" aria-label="Поиск вопросов" placeholder="Поиск вопросов, статей, цитат"> '
        '<strong id="count"></strong></div><div class="scroll"><table class="comparisons"><thead><tr><th>Вопрос</th>'
        + "".join(f'<th>{escape(title)}</th>' for title in METHODS.values())
        + '</tr></thead><tbody>' + "".join(question_rows) + '</tbody></table></div>'
        '<script>const rows=[...document.querySelectorAll(".question-row")];const search=document.getElementById("search");'
        'const index=rows.map(row=>({row,text:row.textContent.toLowerCase()}));'
        'function filter(){let n=0;const q=search.value.trim().toLowerCase();for(const item of index){'
        'const show=!q||item.text.includes(q);item.row.hidden=!show;if(show)n++;}'
        'document.getElementById("count").textContent=`Показано ${n} из ${rows.length}`;}'
        'search.addEventListener("input",filter);filter();</script></body></html>')


def run(snapshot_path: Path, baseline_path: Path, questions_path: Path, run_root: Path,
        store: Path, protocol_path: Path, output: Path) -> dict[str, Any]:
    require(not output.exists(), "Comparison output already exists")
    root = Path.cwd().resolve()
    require(output.resolve().is_relative_to(root), "Comparison output outside workspace")
    inputs = {"snapshot": snapshot_path, "baseline": baseline_path, "questions": questions_path,
              "protocol": protocol_path, **{key: run_root / (key + ".json")
                                           for key in ("profiles", "inventory", "contexts", "classification")}}
    raw = {key: path.read_bytes() for key, path in inputs.items()}
    hashes = {key: digest(value) for key, value in raw.items()}
    values = {key: json.loads(value) for key, value in raw.items() if key not in {"questions", "protocol"}}
    snapshot, baseline = values["snapshot"], values["baseline"]
    require(baseline["snapshot_sha256"] == hashes["snapshot"] and baseline["questions_sha256"] == hashes["questions"],
            "Baseline corpus/questions differ")
    validate_profiles(snapshot, values["profiles"], hashes["snapshot"])
    validate_contexts(snapshot, values["profiles"], values["inventory"], values["contexts"], hashes["inventory"])
    validate_classification(values["contexts"], values["classification"], hashes["contexts"])
    pdf_hashes = verify_pdfs(snapshot, root)
    conn = sqlite3.connect((store / "terms_decisions.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        sid = conn.execute("SELECT value FROM meta WHERE key='current_snapshot'").fetchone()[0]
    finally:
        conn.close()
    frozen_raw = (store / "snapshots" / (sid + ".json")).read_bytes()
    require(digest(frozen_raw) == sid, "Active Terms snapshot checksum differs")
    frozen = json.loads(frozen_raw)
    for key in ("snapshot", "profiles", "inventory", "contexts", "classification"):
        require(frozen["input_sha256"][key] == hashes[key], "Active Terms input differs: " + key)
    questions = load_extended_questions(questions_path)
    previous = {q["id"]: q for q in baseline["questions"]}
    require(len(previous) == len(baseline["questions"]) and set(previous) == {q.id for q in questions},
            "Baseline question inventory differs")
    require(baseline["settings"]["top_k"] == 10 and baseline["settings"]["article_k"] == 5,
            "Baseline depths differ from frozen protocol")
    chunks = {c["chunk_id"]: (a, c) for a in snapshot["articles"] for c in a["chunks"]}
    chunk_texts = {key: row[1]["text"] for key, row in chunks.items()}
    checksums = {a["article_id"]: a["original_pdf_sha256"] for a in snapshot["articles"]}
    work_ids = {a["article_id"]: "doi:" + a["doi"].strip().lower() if a["doi"] else
                "text:" + digest("\n".join(p["text"] for p in a["pages"]).encode()) for a in snapshot["articles"]}
    code_paths = [Path(__file__), *root.glob("app/retrieval/*.py"), *root.glob("app/evaluation/*.py"),
                  *root.glob("app/generation/*.py"), *root.glob("app/terms/*.py"), *root.glob("app/terms/*.json"),
                  *root.glob("scripts/tac_*.py"), root / "docs/cross_lingual_glossary.yaml"]
    code_hashes = {str(p.resolve().relative_to(root)): digest(p.read_bytes()) for p in code_paths}
    output.mkdir(parents=True)
    (output / "protocol.md").write_bytes(raw["protocol"])
    (output / "adapter_source.py").write_bytes(Path(__file__).read_bytes())
    manifest = {"schema": VERSION, "input_paths": {k: str(p.resolve().relative_to(root)) for k, p in inputs.items()},
                "input_sha256": hashes, "code_sha256": code_hashes, "source_pdf_sha256": pdf_hashes,
                "terms_snapshot_id": sid, "settings": {"top_k": 10, "article_k": 5, "rrf_k": 60,
                                                         "weights": "equal", "tuning": False}}
    (output / "manifest_before_evaluation.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows = []
    for question in questions:
        prior = previous[question.id]
        require(prior["query"] == question.query and prior["answerable"] == question.answerable,
                "Question semantics differ")
        production = [result_from_saved(r, chunks) for r in prior["methods"]["production"]["results"]]
        expanded = [result_from_saved(r, chunks) for r in prior["full_pool"]]
        pool = common_pool(production, expanded)
        ranking = rank_tac(question.query, values["profiles"]["profiles"], 5)
        tac_ranks = {p["article_id"]: rank for rank, (_, p) in enumerate(ranking, 1)}
        variants = [v.text for v in build_query_bundle(question.query).variants]
        typed = rank_terms(pool, term_signals(pool, values["contexts"], values["classification"], typed=True), variants)
        all_terms = rank_terms(pool, term_signals(pool, values["contexts"], values["classification"], typed=False), variants)
        def channel(candidates: list[dict[str, Any]]) -> dict[str, int]:
            return {r["chunk_id"]: rank for rank, r in enumerate(candidates, 1)}
        responses = {
            "production": SearchResponse(question.query, production, prior["methods"]["production"]["retrieval_metadata"]),
            "tac_soft": SearchResponse(question.query, fuse(pool, tac_ranks, {}, top_k=10)),
            "tac_typed_soft": SearchResponse(question.query, fuse(pool, tac_ranks, channel(typed), top_k=10)),
            "tac_all_soft": SearchResponse(question.query, fuse(pool, tac_ranks, channel(all_terms), top_k=10)),
            "tac_only": tac_response(question.query, ranking),
            "tac_rescue": staged_replay(SearchResponse(question.query, pool), set(tac_ranks), top_k=10, rescue=True),
        }
        methods = {}
        for name, response in responses.items():
            texts = chunk_texts if name != "tac_only" else {r.chunk_id: r.full_text or r.snippet for r in response.results}
            result = _evaluate_extended_question(question, response, checksums, texts, elapsed_ms=0, top_k=10)
            result["work_ranking_diagnostic"] = work_ranks(result, work_ids)
            methods[name] = result
        historical = prior["methods"]["production"]
        metrics = ("passed", "article_recall_at_k", "chunk_recall_at_k", "mrr", "ndcg_at_k", "evidence_trace_complete")
        rows.append({"id": question.id, "query": question.query, "answerable": question.answerable,
                     "common_pool_count": len(pool), "common_pool_chunk_ids": [r.chunk_id for r in pool],
                     "baseline_preserved_in_common_pool": all(r.chunk_id in {p.chunk_id for p in pool} for r in production),
                     "query_variants": variants, "tac_candidates": [{"article_id": p["article_id"], "score": s} for s, p in ranking],
                     "typed_term_candidates": typed, "all_term_candidates": all_terms, "methods": methods,
                     "historical_baseline_metrics": {k: historical[k] for k in metrics},
                     "baseline_metric_drift": {k: {"historical": historical[k], "current": methods["production"][k]}
                                               for k in metrics if historical[k] != methods["production"][k]}})
    for key, path in inputs.items():
        require(digest(path.read_bytes()) == hashes[key], "Input changed during evaluation: " + key)
    for path, checksum in code_hashes.items():
        require(digest((root / path).read_bytes()) == checksum, "Code changed during evaluation: " + path)
    report = {**manifest, "summary": summarize(rows), "questions": rows,
              "work_ids": work_ids, "independent_validation": False,
              "limitations": ["Known development documents and questions; incomplete relevance judgments.",
                              "Offline ranking adapter, not production Terms retrieval or live latency.",
                              "Elapsed milliseconds are evaluator placeholders; user-time savings not measured.",
                              "Roles, origin and scientific relations are not evaluated by lexical chunk judgments.",
                              "No hypothesis tuning or new independent gold; TAC-only evidence uses different units."]}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    (output / "comparison.html").write_text(render_html(report, snapshot, root), encoding="utf-8")
    (output / "ARIADNE_TAC_33_documents.html").write_text(frozen["table_html"], encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "baseline", "questions", "run-root", "store", "protocol", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.snapshot, args.baseline, args.questions, args.run_root, args.store, args.protocol, args.output)


if __name__ == "__main__":
    main()
