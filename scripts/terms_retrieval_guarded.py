"""Guarded, source-bound ranking experiment over the immutable production top-ten."""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.evaluation.retrieval import _evaluate_extended_question, _EvidenceSnippet, load_extended_questions
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.retrieval.search import SearchResponse, SearchResult
from scripts.tac_experiment import digest, json_default, validate_profiles
from scripts.tac_term_classification import validate_classification
from scripts.tac_term_contexts import validate_contexts, verify_pdfs
from scripts.terms_retrieval_compare import fuse, rank_terms, require, result_from_saved, term_signals, work_ranks

VERSION = "terms_retrieval_guarded_replay_v0.2"
METHODS = {
    "production": "Прежний поиск",
    "membership_tac": "TAC RRF, только прежний top-10",
    "membership_terms": "Terms RRF, только прежний top-10",
    "membership_combined": "TAC + Terms RRF, только прежний top-10",
    "guarded_tac": "TAC с проверками контекста",
    "guarded_terms": "Terms: точные фразы + IDF + проверки",
    "guarded_combined": "TAC + Terms: точные фразы + IDF + проверки",
}
STOPWORDS = {"and", "in", "or", "the", "using", "vs", "with"}


def normalized(text: str) -> str:
    return " ".join(text.casefold().translate(str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff"})).split())


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w+-]+", normalized(text)) if len(t) >= 2 and t not in STOPWORDS}


def work_ids(snapshot: dict[str, Any]) -> dict[str, str]:
    return {a["article_id"]: "doi:" + a["doi"].strip().lower() if a["doi"] else
            "text:" + digest("\n".join(p["text"] for p in a["pages"]).encode()) for a in snapshot["articles"]}


def idf_weights(groups: dict[str, set[str]]) -> dict[str, float]:
    frequencies: dict[str, int] = defaultdict(int)
    for values in groups.values():
        for value in sorted(values):
            frequencies[value] += 1
    return {value: 1 + math.log((len(groups) + 1) / (frequencies[value] + 1)) for value in sorted(frequencies)}


def corpus_weights(snapshot: dict[str, Any], contexts: dict[str, Any], works: dict[str, str]) -> tuple[dict[str, float], dict[str, float]]:
    pages: dict[str, set[str]] = defaultdict(set)
    phrases: dict[str, set[str]] = defaultdict(set)
    for article in snapshot["articles"]:
        pages[works[article["article_id"]]].update(tokens("\n".join(p["text"] for p in article["pages"])))
    for article in contexts["articles"]:
        phrases[works[article["article_id"]]].update(normalized(t["term"]) for t in article["terms"])
    return idf_weights(pages), idf_weights(phrases)


def coverage(query: str, text: str, weights: dict[str, float], missing_weight: float) -> float:
    query_tokens = tokens(query)
    denominator = math.fsum(weights.get(t, missing_weight) for t in sorted(query_tokens))
    numerator = math.fsum(weights.get(t, missing_weight) for t in sorted(query_tokens & tokens(text)))
    return numerator / denominator if denominator else 0.0


def clause(context: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Return an exact source slice, not a scientific sentence or inferred relation."""
    text = context["source"]["quote"]
    offset = source["start"] - context["source"]["start"]
    end = offset + len(source["quote"])
    require(offset >= 0 and text[offset:end] == source["quote"], "Mention/context source mismatch")
    left = max((text.rfind(delimiter, 0, offset) for delimiter in ".!?;"), default=-1) + 1
    right = min((position for delimiter in ".!?;" if (position := text.find(delimiter, end)) >= 0), default=len(text))
    quote = text[left:right]
    return {"quote": quote, "quote_sha256": digest(quote.encode()),
            "start": context["source"]["start"] + left, "end": context["source"]["start"] + right,
            "context_id": context["context_id"], "source_region_id": context["source"]["region_id"],
            "page_number": source["page_number"], "text_layer": source["text_layer"],
            "original_pdf_path": source["original_pdf_path"], "layer_pdf_path": source["layer_pdf_path"],
            "scope": "exact_lexical_clause_slice_not_relation"}


def contextual_signals(production: list[SearchResult], contexts: dict[str, Any], classification: dict[str, Any],
                       variants: list[str], token_weights: dict[str, float], phrase_weights: dict[str, float],
                       nworks: int) -> tuple[dict[str, dict[str, Any]], set[str]]:
    articles = {a["article_id"]: a for a in contexts["articles"]}
    classified = {a["article_id"]: a for a in classification["articles"]}
    missing_weight = 1 + math.log(nworks + 1)
    signals = {}
    locked = set()
    for result in production:
        article = articles[result.article_id]
        rows = {c["context_id"]: c for c in article["contexts"]}
        if not any(c["kind"] in {"A", "C"} and c["boundary_status"] == "pass" for c in rows.values()):
            locked.add(result.chunk_id)
        text = result.full_text or ""
        tac_evidence = []
        for context in rows.values():
            source = context["source"]
            if (context["boundary_status"] == "pass" and source["text_layer"] == result.text_layer
                    and result.page_start <= source["page_number"] <= result.page_end and source["quote"] in text):
                score = max((coverage(v, source["quote"], token_weights, missing_weight) for v in variants), default=0.0)
                if score:
                    tac_evidence.append({"score": score, "context_id": context["context_id"],
                                         "kind": context["kind"], "source": source})
        eligible = {a["use_id"] for a in classified[result.article_id]["assignments"]
                    if a["axis"] == "type" and a["state"] == "proposed"}
        terms = {t["term_id"]: t for t in article["terms"]}
        mentions = {m["mention_id"]: m["source"] for m in article["mentions"]}
        term_evidence = []
        for use in article["uses"]:
            phrase = normalized(terms[use["term_id"]]["term"])
            source, context = mentions[use["mention_id"]], rows[use["context_id"]]
            if (use["use_id"] not in eligible or len(tokens(phrase)) < 2 or context["boundary_status"] != "pass"
                    or source["text_layer"] != result.text_layer
                    or not result.page_start <= source["page_number"] <= result.page_end):
                continue
            matched = [v for v in variants if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", normalized(v))]
            if not matched:
                continue
            fragment = clause(context, source)
            if fragment["quote"] not in text:
                continue
            weight = phrase_weights[phrase]
            score = weight * max(coverage(v, fragment["quote"], token_weights, missing_weight) for v in matched)
            term_evidence.append({"term_id": use["term_id"], "use_id": use["use_id"], "term": phrase,
                                  "phrase_idf": weight, "score": score, "clause": fragment,
                                  "mention_source": source, "matched_query_variants": matched})
        signals[result.chunk_id] = {"tac": max((e["score"] for e in tac_evidence), default=0.0),
                                   "terms": max((e["score"] for e in term_evidence), default=0.0),
                                   "tac_evidence": tac_evidence, "term_evidence": term_evidence}
    return signals, locked


def guarded_order(production: list[SearchResult], query: str, signals: dict[str, dict[str, Any]],
                  locked: set[str], axes: tuple[str, ...]) -> tuple[list[SearchResult], dict[str, Any]]:
    ordered = list(production)
    query_tokens = tokens(query)
    matched = {r.chunk_id: tokens(r.full_text or "") & query_tokens for r in production}
    swaps = []
    changed = True
    while changed:
        changed = False
        for index in range(1, len(ordered)):
            defender, challenger = ordered[index - 1], ordered[index]
            if defender.chunk_id in locked or challenger.chunk_id in locked:
                continue
            before, after = signals[defender.chunk_id], signals[challenger.chunk_id]
            if (matched[challenger.chunk_id].issuperset(matched[defender.chunk_id])
                    and all(after[a] >= before[a] for a in axes) and any(after[a] > before[a] for a in axes)):
                ordered[index - 1], ordered[index] = challenger, defender
                swaps.append({"promoted": challenger.chunk_id, "demoted": defender.chunk_id, "position": index})
                changed = True
    before = assess_evidence_adequacy(query, [_EvidenceSnippet(r.snippet) for r in production]).adequate
    after = assess_evidence_adequacy(query, [_EvidenceSnippet(r.snippet) for r in ordered]).adequate
    rollback = before != after
    if rollback:
        ordered = list(production)
    return ordered, {"swaps_proposed": swaps, "adequacy_rollback": rollback,
                     "locked_chunk_ids": sorted(locked), "active_axes": list(axes),
                     "fallback": "adequacy_changed" if rollback else "no_supported_swap" if not swaps else None}


def grouped_results(results: list[SearchResult], works: dict[str, str]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for result in results:
        work = works[result.article_id]
        group = groups.setdefault(work, {"work_id": work, "article_ids": [], "chunk_ids": []})
        if result.article_id not in group["article_ids"]:
            group["article_ids"].append(result.article_id)
        group["chunk_ids"].append(result.chunk_id)
    return list(groups.values())


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for name in METHODS:
        items = [q["methods"][name] for q in rows]
        positive = [r for r in items if r["answerable"]]
        stats = {"passed": sum(r["passed"] for r in items), "total": len(items),
                 "top1_hits": sum(r["top_1_passed"] for r in positive),
                 "negative_failures": sum(not r["passed"] for r in items if not r["answerable"]),
                 "trace_complete": all(r["evidence_trace_complete"] for r in items),
                 "membership_preserved": all(q["membership_equal"][name] for q in rows),
                 "rank_improved": [q["id"] for q in rows if q["answerable"] and
                                   q["methods"][name]["mrr"] > q["methods"]["production"]["mrr"]],
                 "rank_worsened": [q["id"] for q in rows if q["answerable"] and
                                   q["methods"][name]["mrr"] < q["methods"]["production"]["mrr"]]}
        for key, field in (("article_recall", "article_recall_at_k"), ("chunk_recall", "chunk_recall_at_k"),
                           ("mrr", "mrr"), ("ndcg", "ndcg_at_k")):
            values = [r[field] for r in positive if r[field] is not None]
            stats[key] = sum(values) / len(values) if values else None
        output[name] = stats
    base, candidate = output["production"], output["guarded_combined"]
    checks = {"membership_preserved": candidate["membership_preserved"],
              "recall_not_lower": candidate["article_recall"] >= base["article_recall"]
                                  and candidate["chunk_recall"] >= base["chunk_recall"],
              "negative_failures_not_higher": candidate["negative_failures"] <= base["negative_failures"],
              "trace_complete": candidate["trace_complete"],
              "ranking_gain": candidate["mrr"] > base["mrr"] or candidate["ndcg"] > base["ndcg"]}
    output["decision"] = {**checks, "development_gain": all(checks.values()), "production_enabled": False}
    return output


def render(report: dict[str, Any], snapshot: dict[str, Any], root: Path) -> str:
    def h(value: object) -> str:
        return html.escape(str(value), quote=True)

    articles = {a["article_id"]: a for a in snapshot["articles"]}
    chunks = {c["chunk_id"]: c for a in snapshot["articles"] for c in a["chunks"]}
    metrics = []
    for name, label in METHODS.items():
        row = report["summary"][name]
        metrics.append(f'<tr><td>{h(label)}</td><td>{row["passed"]}/{row["total"]}</td>'
                       f'<td>{row["top1_hits"]}/{report["positive_count"]}</td><td>{row["mrr"]:.4f}</td>'
                       f'<td>{row["ndcg"]:.4f}</td><td>{row["article_recall"]:.1%}</td>'
                       f'<td>{row["negative_failures"]}/{report["negative_count"]}</td></tr>')
    evidence = []
    for query in report["questions"]:
        methods = []
        for name, label in METHODS.items():
            result = query["methods"][name]
            references = []
            for rank, row in enumerate(result["results"], 1):
                article = articles[row["article_id"]]
                uri = (root / article["original_pdf_path"]).resolve().as_uri()
                references.append(f'<li>{rank}. <a href="{h(uri)}#page={row["page_start"]}">{h(row["title"])}</a>'
                                  f' · стр. {row["page_start"]}–{row["page_end"]}'
                                  f' <button class="source" data-chunk="{h(row["chunk_id"])}">Точный текст</button>'
                                  f'<p class="id">{h(row["article_id"])} · {h(row["chunk_id"])} · {h(row["text_layer"])}</p></li>')
            methods.append(f'<details><summary>{h(label)} · первая нужная: {result["rank_of_first_relevant"] or "—"}'
                           f' · {"прошёл" if result["passed"] else "не прошёл"}</summary><ol>{"".join(references)}</ol>'
                           f'<pre>{h(json.dumps(query["ordering_diagnostics"].get(name, {}), ensure_ascii=False, indent=2))}</pre>'
                           '</details>')
        groups = []
        for group in query["candidate_work_groups"]:
            groups.append(f'<li><b>{h(group["work_id"])}</b> · документов {len(group["article_ids"])} '
                          f'· фрагментов {len(group["chunk_ids"])}<p class="id">{h(", ".join(group["article_ids"]))}</p>'
                          + "".join(f'<button class="source" data-chunk="{h(cid)}">Текст: {h(cid[:12])}</button>'
                                    for cid in group["chunk_ids"]) + '</li>')
        search_text = query["id"] + " " + query["query"] + " " + " ".join(
            str(r["title"]) for r in query["methods"]["production"]["results"])
        evidence.append(f'<article class="question" data-search="{h(search_text.lower())}"><h3>{h(query["id"])}</h3>'
                        f'<p>{h(query["query"])}</p>{"".join(methods)}'
                        f'<details><summary>Кандидат: группировка по работам — {len(groups)} групп, все 10 фрагментов</summary>'
                        f'<ul>{"".join(groups)}</ul></details></article>')
    payload = json.dumps({key: row["text"] for key, row in chunks.items()}, ensure_ascii=False).replace("<", "\\u003c")
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return '''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ARIADNE — guarded TAC + Terms v0.2</title><style>
body{font:15px/1.5 system-ui,sans-serif;background:#f5f7fa;color:#193248;margin:24px}h1{margin-bottom:10px}
table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;border:1px solid #d9e1e8;text-align:left}
th{background:#243e55;color:white}details{margin:10px 0}summary,button{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;
background:#edf2f7;padding:12px;font-size:12px}.question{background:white;padding:16px;margin:16px 0;border:1px solid #d9e1e8}
.id{font-size:11px;overflow-wrap:anywhere}input,button{font:inherit;padding:7px;border:1px solid #b9c9d7;border-radius:5px}
.toolbar{position:sticky;top:0;padding:12px 0;background:#f5f7fa}a{color:#17649a}ol{padding-left:24px}.scroll{overflow:auto}
</style></head><body>''' + (
        '<h1>TAC + Terms v0.2: сохранение top-10 и специфичность</h1>'
        f'<p>{len(snapshot["articles"])} документа · {len(chunks)} chunks · {len(report["questions"])} известных вопросов</p>'
        '<p>Регрессионный frozen replay после неудачного v0.1. Независимая проверка и измерение пользовательского времени не выполнены.</p>'
        '<p>Все варианты сохраняют состав прежнего top-10. Guards используют точные контексты, IDF и fallback; production не изменён.</p>'
        f'<p class="id">Snapshot: {h(report["terms_snapshot_id"])} · {h(VERSION)}</p>'
        '<p><a href="report.json">Полный JSON</a> · <a href="protocol.md">Протокол до оценки</a> · '
        '<a href="ARIADNE_TAC_33_documents.html">Полная таблица TAC, 33 документа</a></p>'
        '<div class="scroll"><table id="metrics"><thead><tr><th>Вариант</th><th>Прошли</th><th>Top-1</th><th>MRR ↑</th>'
        '<th>nDCG ↑</th><th>Article recall</th><th>Ошибки на отрицательных</th></tr></thead><tbody>'
        + "".join(metrics) + '</tbody></table></div>'
        f'<p>Разработка: прирост по заранее заданным условиям — <b>{h(report["summary"]["decision"]["development_gain"])}</b>.</p>'
        '<p>Совпадение фразы и clause — лексические сигналы; научная связь не подтверждается. Unknown/conflict сохраняются.</p>'
        '<div class="toolbar"><input id="search" aria-label="Поиск вопросов" placeholder="Вопрос или статья"> '
        '<strong id="count"></strong></div>'
        + "".join(evidence) + f'<script id="texts" type="application/json">{payload}</script>'
        '<script>const texts=JSON.parse(document.getElementById("texts").textContent);'
        'const rows=[...document.querySelectorAll(".question")],search=document.getElementById("search");'
        'function filter(){let n=0;const q=search.value.trim().toLowerCase();for(const row of rows){'
        'row.hidden=!row.dataset.search.includes(q);if(!row.hidden)n++;}'
        'document.getElementById("count").textContent=`Показано ${n} из ${rows.length}`;}'
        'search.addEventListener("input",filter);document.addEventListener("click",event=>{'
        'const button=event.target.closest("button.source");'
        'if(!button)return;let pre=button.nextElementSibling;if(pre&&pre.classList.contains("quote")){pre.hidden=!pre.hidden;return;}'
        'pre=document.createElement("pre");pre.className="quote";pre.textContent=texts[button.dataset.chunk];button.after(pre);});filter();'
        '</script></body></html>')


def run(previous_path: Path, protocol_path: Path, store: Path, output: Path) -> dict[str, Any]:
    root = Path.cwd().resolve()
    require(not output.exists() and output.resolve().is_relative_to(root), "Fresh comparison output inside workspace required")
    previous_raw = previous_path.read_bytes()
    previous = json.loads(previous_raw)
    require(previous["schema"] == "terms_retrieval_frozen_replay_v0.1", "Unsupported preceding comparison")
    input_raw = {name: (root / path).read_bytes() for name, path in previous["input_paths"].items()}
    for name, raw in input_raw.items():
        require(digest(raw) == previous["input_sha256"][name], "Frozen input differs: " + name)
    for path, checksum in previous["code_sha256"].items():
        require(digest((root / path).read_bytes()) == checksum, "v0.1 dependency changed: " + path)
    values = {name: json.loads(raw) for name, raw in input_raw.items() if name not in {"questions", "protocol"}}
    snapshot, contexts, classification = values["snapshot"], values["contexts"], values["classification"]
    validate_profiles(snapshot, values["profiles"], previous["input_sha256"]["snapshot"])
    validate_contexts(snapshot, values["profiles"], values["inventory"], contexts, previous["input_sha256"]["inventory"])
    validate_classification(contexts, classification, previous["input_sha256"]["contexts"])
    pdf_hashes = verify_pdfs(snapshot, root)
    conn = sqlite3.connect((store / "terms_decisions.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        sid = conn.execute("SELECT value FROM meta WHERE key='current_snapshot'").fetchone()[0]
    finally:
        conn.close()
    require(sid == previous["terms_snapshot_id"], "Active Terms snapshot changed")
    frozen_raw = (store / "snapshots" / (sid + ".json")).read_bytes()
    require(digest(frozen_raw) == sid, "Terms snapshot checksum mismatch")
    frozen = json.loads(frozen_raw)
    for name in ("snapshot", "profiles", "inventory", "contexts", "classification"):
        require(frozen["input_sha256"][name] == previous["input_sha256"][name], "Terms snapshot input differs: " + name)
    works = work_ids(snapshot)
    token_weights, phrase_weights = corpus_weights(snapshot, contexts, works)
    chunks = {c["chunk_id"]: (a, c) for a in snapshot["articles"] for c in a["chunks"]}
    texts = {cid: row[1]["text"] for cid, row in chunks.items()}
    checksums = {a["article_id"]: a["original_pdf_sha256"] for a in snapshot["articles"]}
    questions = load_extended_questions(root / previous["input_paths"]["questions"])
    prior_rows = {q["id"]: q for q in previous["questions"]}
    require(set(prior_rows) == {q.id for q in questions}, "Question inventory differs")
    protocol_raw = protocol_path.read_bytes()
    code_hashes = {**previous["code_sha256"], str(Path(__file__).resolve().relative_to(root)): digest(Path(__file__).read_bytes())}
    manifest = {"schema": VERSION, "prior_report_sha256": digest(previous_raw), "protocol_sha256": digest(protocol_raw),
                "input_sha256": previous["input_sha256"], "code_sha256": code_hashes, "source_pdf_sha256": pdf_hashes,
                "terms_snapshot_id": sid, "settings": {"top_k": 10, "rrf_k": 60, "tuning": False},
                "work_ids": works, "idf_tokens": token_weights, "idf_phrases": phrase_weights}
    output.mkdir(parents=True)
    (output / "protocol.md").write_bytes(protocol_raw)
    (output / "adapter_source.py").write_bytes(Path(__file__).read_bytes())
    (output / "manifest_before_evaluation.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for question in questions:
        prior = prior_rows[question.id]
        require(prior["query"] == question.query and prior["answerable"] == question.answerable, "Question semantics differ")
        production = [result_from_saved(r, chunks) for r in prior["methods"]["production"]["results"]]
        variants = prior["query_variants"]
        tac_ranks = {r["article_id"]: rank for rank, r in enumerate(prior["tac_candidates"], 1)}
        naive_terms = rank_terms(production, term_signals(production, contexts, classification, typed=True), variants)
        term_ranks = {r["chunk_id"]: rank for rank, r in enumerate(naive_terms, 1)}
        signals, locked = contextual_signals(production, contexts, classification, variants, token_weights, phrase_weights,
                                            len(set(works.values())))
        orders = {"production": production, "membership_tac": fuse(production, tac_ranks, {}, top_k=10),
                  "membership_terms": fuse(production, {}, term_ranks, top_k=10),
                  "membership_combined": fuse(production, tac_ranks, term_ranks, top_k=10)}
        diagnostics = {}
        for name, axes in (("guarded_tac", ("tac",)), ("guarded_terms", ("terms",)),
                           ("guarded_combined", ("tac", "terms"))):
            orders[name], diagnostics[name] = guarded_order(production, question.query, signals, locked, axes)
        expected = {r.chunk_id for r in production}
        methods = {}
        for name, order in orders.items():
            require(len(order) == len(production) and {r.chunk_id for r in order} == expected, "Top-ten membership changed")
            response = SearchResponse(question.query, order, {"strategy": name, "membership_preserved": True})
            result = _evaluate_extended_question(question, response, checksums, texts, elapsed_ms=0, top_k=10)
            result["work_ranking_diagnostic"] = work_ranks(result, works)
            methods[name] = result
        metric_names = ("passed", "article_recall_at_k", "chunk_recall_at_k", "mrr", "ndcg_at_k", "evidence_trace_complete")
        drift = {k: {"v01": prior["methods"]["production"][k], "v02": methods["production"][k]}
                 for k in metric_names if prior["methods"]["production"][k] != methods["production"][k]}
        rows.append({"id": question.id, "query": question.query, "answerable": question.answerable, "methods": methods,
                     "signals": signals, "ordering_diagnostics": diagnostics, "membership_equal": dict.fromkeys(METHODS, True),
                     "candidate_work_groups": grouped_results(orders["guarded_combined"], works), "baseline_metric_drift": drift})
    require(digest(previous_path.read_bytes()) == manifest["prior_report_sha256"], "Previous report changed during replay")
    require(digest(protocol_path.read_bytes()) == manifest["protocol_sha256"], "Protocol changed during replay")
    for name, path in previous["input_paths"].items():
        require(digest((root / path).read_bytes()) == previous["input_sha256"][name], "Input changed during replay: " + name)
    for path, checksum in code_hashes.items():
        require(digest((root / path).read_bytes()) == checksum, "Code changed during replay: " + path)
    report = {**manifest, "summary": summary(rows), "questions": rows,
              "positive_count": sum(q.answerable for q in questions), "negative_count": sum(not q.answerable for q in questions),
              "independent_validation": False, "latency_measured": False,
              "scientific_relation_validation": False, "prior_v01_summary": previous["summary"]}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    (output / "comparison.html").write_text(render(report, snapshot, root), encoding="utf-8")
    (output / "ARIADNE_TAC_33_documents.html").write_text(frozen["table_html"], encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("previous-report", "protocol", "store", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.previous_report, args.protocol, args.store, args.output)


if __name__ == "__main__":
    main()
