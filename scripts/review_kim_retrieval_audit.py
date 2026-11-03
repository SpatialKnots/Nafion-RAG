"""Offline replay, exact lexical diagnostics and source-preserving Kim review."""

from __future__ import annotations

import argparse
import copy
import html
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.retrieval_loss_audit import anchor_presence  # noqa: E402
from scripts.review_swelling_retrieval_audit import replay  # noqa: E402
from scripts.run_kim_retrieval_audit import BASE, VERSION, article_presence  # noqa: E402

ARCHIVED_INVENTORY = ROOT / "output/swelling_retrieval_audit_20261030/capture_v03/capture.json"


def raw_hits(raw: str, term: str) -> list[dict[str, Any]]:
    """Map the production lowercase/ligature view back to exact raw character spans."""
    from app.generation.evidence_adequacy import LIGATURES

    if not term.strip():
        raise ValueError("Nonblank term required")
    chars, offsets = [], []
    for index, char in enumerate(raw):
        normalized = char.lower().translate(LIGATURES)
        chars.append(normalized)
        offsets.extend([index] * len(normalized))
    view = "".join(chars)
    hits = []
    for match in re.finditer(re.escape(term), view):
        start, end = offsets[match.start()], offsets[match.end() - 1] + 1
        hits.append({"start": start, "end": end, "exact_text": raw[start:end],
                     "context": raw[max(0, start - 65):min(len(raw), end + 65)]})
    return hits


def gate_audit(capture: dict[str, Any]) -> dict[str, Any]:
    from app.generation.evidence_adequacy import assess_evidence_adequacy
    from app.generation.service import _cross_lingual_matched_concepts
    from app.retrieval.cross_lingual import glossary_terms_for_concepts

    evidence = [SimpleNamespace(text=row["text"]) for row in capture["trace"]["evidence"]]
    concept_terms = glossary_terms_for_concepts(_cross_lingual_matched_concepts(capture["trace"]["retrieval"]["metadata"]))
    result = asdict(assess_evidence_adequacy(capture["question"], evidence, concept_terms=concept_terms))
    expected = capture["trace"]["metadata"]["evidence_adequacy"]
    if {key: result[key] for key in expected} != expected:
        raise ValueError("Actual evidence adequacy metadata differs")
    controls = [
        ("thermal_property_only", "Вопрос о том, как меняется поведение дисперсии Nafion в зависимости от природы "
         "растворителя, здесь обсуждается только через температуру разложения мембран."),
        ("explicit_non_observation", "Морфология частиц дисперсии Nafion в зависимости от природы растворителя не исследована."),
        ("question_heading_only", capture["question"]),
    ]
    observed_controls = [{"id": name, "text": text, "origin": "assistant_constructed_development_control",
                          "result": asdict(assess_evidence_adequacy(capture["question"], [SimpleNamespace(text=text)],
                                                                  concept_terms=concept_terms))}
                         for name, text in controls]
    terms = [{"term": term, "matched": term in result["matched_terms"],
              "evidence_hits": [{"citation_id": row["citation_id"], "article_id": row["article_id"],
                                 "chunk_id": row["chunk_id"], "raw_hits": raw_hits(row["text"], term)}
                                for row in capture["trace"]["evidence"]]}
             for term in result["distinctive_terms"]]
    return {"recomputed_metadata_identical": True, "actual": result, "term_surfaces": terms,
        "admission_predicates": {
            "all_term_count_at_least_2_and_coverage_at_least_0_6": len(result["matched_terms"]) >= 2 and result["coverage"] >= .6,
            "top_term_count_at_least_2_and_coverage_at_least_0_5": len(result["top_matched_terms"]) >= 2 and result["top_coverage"] >= .5,
            "all_term_count_at_least_5_and_top_term_count_at_least_2": (
                len(result["matched_terms"]) >= 5 and len(result["top_matched_terms"]) >= 2),
        }, "constructed_controls": observed_controls,
        "scope": "Observed lexical admission, not scientific entailment or a proposed semantic validator"}


def lexical_inventory(capture: dict[str, Any]) -> list[dict[str, Any]]:
    from app.generation.evidence_adequacy import LIGATURES
    from app.retrieval.search import _query_terms

    terms = _query_terms(capture["question"])
    return [{"chunk_id": row["chunk_id"], "chunk_index": row["chunk_index"],
             "raw_query_term_matches": [term for term in terms if term.lower() in row["full_text"].lower()],
             "ligature_normalized_query_term_matches": [term for term in terms
                 if term.lower() in row["full_text"].lower().translate(LIGATURES)],
             "normalization_scope": "diagnostic_only; SQL ILIKE does not apply this translation"}
            for row in capture["database_target_inventory"]]


def review(captured: Path, expanded: Path, output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    for folder in (captured, expanded):
        files.verify_manifest(folder)
    capture = json.loads((captured / "capture.json").read_bytes())
    expansion = json.loads((expanded / "expanded.json").read_bytes())
    for value in (capture, expansion):
        files.verify(value["bindings"])
    if not capture["historical_final_trace_identical"]:
        raise ValueError("Historical final trace equality required")
    outcome = replay(capture, settings)
    corrupted = copy.deepcopy(capture)
    boundary = next(s for s in corrupted["stages"] if s["name"] == "_diversify_cross_lingual_results:2:output")
    boundary["results"].reverse()
    try:
        replay(corrupted, settings)
    except ValueError as exc:
        if str(exc) != "Replay differs at _diversify_cross_lingual_results:2:output":
            raise
        outcome["corrupted_boundary_control"] = "rejected_at_expected_boundary"
    else:
        raise ValueError("Corrupted boundary accepted")
    target = capture["target_article_id"]
    observations = [{"name": stage["name"], "parent": stage.get("parent"), "count": len(stage["results"]),
                     "target_article_rows": article_presence(stage["results"], target)} for stage in capture["stages"]]
    if observations != capture["observations"]:
        raise ValueError("Article presence observations differ")
    for channel, rows in expansion["expanded_channels"].items():
        previous = next(s for s in capture["stages"] if s["name"] == channel + "_search:1:output")
        if rows[:len(previous["results"])] != previous["results"]:
            raise ValueError("Expanded prefix differs")
        if article_presence(rows, target) != expansion["target_ranks"][channel]:
            raise ValueError("Expanded target ranks differ")
    import fitz

    verified = []
    anchors = []
    for window in capture["reference_windows"]:
        with fitz.open(window["original_pdf_path"]) as pdf:
            text = pdf[window["pdf_page"] - 1].get_text("text")
        if (files.sha(text.encode()) != window["page_text_sha256"]
                or text[window["start"]:window["end"]] != window["exact_text"]):
            raise ValueError("Fresh reference window differs")
        verified.append({"label": window["label"], "pdf_page": window["pdf_page"], "source": window["original_pdf_path"]})
        args = {"article_id": target, "page_number": window["pdf_page"], "exact_text": window["exact_text"]}
        anchors.append({"label": window["label"], "window": window,
            "database_chunks": anchor_presence(capture["database_target_inventory"], **args),
            "expanded_channels": {name: anchor_presence(rows, **args) for name, rows in expansion["expanded_channels"].items()},
            "captured_stages": [{"name": s["name"], **anchor_presence(s["results"], **args)} for s in capture["stages"]]})
    sources = json.loads((BASE / "preparation_v01/sources.json").read_bytes())
    for page in sources["pages"].values():
        with fitz.open(page["original_pdf_path"]) as pdf:
            text = pdf[page["page_number"] - 1].get_text("text")
        if text != page["page_text"] or files.sha(text.encode()) != page["page_text_sha256"]:
            raise ValueError("Fresh selected page differs")
    # Expanded channels cover the corpus. Use explicitly archived metadata for
    # works not loaded in this capture; never imply it was freshly read from DB.
    archive = json.loads(ARCHIVED_INVENTORY.read_bytes())
    archived_articles = {row["article_id"]: row for row in archive["articles"]}
    current_articles = {row["article_id"]: row for row in capture["articles"]}
    rows = [row for channel in expansion["expanded_channels"].values() for row in channel]
    ids = sorted({row["article_id"] for row in rows})
    articles = []
    for article_id in ids:
        row = dict(current_articles.get(article_id) or archived_articles[article_id])
        row["metadata_snapshot"] = ("current_readonly_capture" if article_id in current_articles
                                    else "archived_DB_inventory_2026-10-30; not a fresh metadata query")
        if files.sha(Path(row["original_pdf_path"]).read_bytes()) != row["original_pdf_sha256"]:
            raise ValueError("Original PDF differs")
        articles.append(row)
    stages = {stage["name"]: stage for stage in capture["stages"]}
    limits = [stages[name + "_search:1:output"]["requested_top_k"] for name in ("exact", "semantic")]
    if limits[0] != limits[1]:
        raise ValueError("Unequal channel limits require a separately described report")
    bindings = {**expansion["bindings"], **files.bindings([
        Path(__file__), ROOT / "scripts/retrieval_loss_audit.py", ROOT / "scripts/review_swelling_retrieval_audit.py",
        ROOT / "tests/unit/test_kim_retrieval_audit.py", ARCHIVED_INVENTORY,
        expanded / "expanded.json", expanded / "manifest.json", BASE / "preparation_v01/sources.json",
        *[Path(a["original_pdf_path"]) for a in articles],
    ])}
    gate = gate_audit(capture)
    summary = {"version": VERSION, "historical_final_trace_identical": True, "recorded_boundaries": len(observations),
        "production_exact_and_semantic_limits": limits[0],
        "production_hybrid_limit": stages["hybrid_search:1:output"]["requested_top_k"],
        "production_feature_window": capture["trace"]["retrieval"]["metadata"]["reranking"]["window_size"],
        "target_best_expanded_ranks": {name: min(r["rank"] for r in ranks) for name, ranks in expansion["target_ranks"].items()},
        "reference_windows_freshly_verified": len(verified), "selected_pages_freshly_verified": len(sources["pages"]),
        "tac_works": len(articles), "model_calls": 0, "oauth_calls": 0, "slot_reservations": 0,
        "scientific_acceptance": "not_established", "plan_completion_percent": 75}
    report = {"version": VERSION, "summary": summary, "bindings": bindings, "request": capture["request"],
        "artifact_paths": {"capture": str((captured / "capture.json").resolve()),
                           "expanded_channels": str((expanded / "expanded.json").resolve()),
                           "current_report": str((output / "report.json").resolve())},
        "replay": outcome, "observations": observations, "expanded_target_ranks": expansion["target_ranks"],
        "source_anchors": anchors, "fresh_reference_windows": verified, "gate_audit": gate,
        "target_lexical_inventory": lexical_inventory(capture), "articles": articles,
        "diagnosis": "Kim is absent at both original top-50 channel outputs, before hybrid top-10, feature window and top-5. "
                     "Expanded same-query channels have identical prefixes and expose the target below the original channel limits.",
        "causal_limits": "No alternative query/model/ranking was evaluated as a fix. English-model/Russian-query mismatch and "
                         "missing glossary coverage are observations, not a quantified attribution of semantic ranking error.",
        "historical_limits": "New internal boundaries are a reproduction, not recovered historical events.",
        "runtime_changes": False, "independent_accuracy": None, "network_denials": policy.denied}
    files.verify(bindings)
    output.mkdir(parents=True, exist_ok=False)
    files.write(output / "report.json", report)
    render(report, capture, output)
    for name in ("scripts/run_kim_retrieval_audit.py", "scripts/expand_kim_retrieval_audit.py",
                 "scripts/review_kim_retrieval_audit.py", "tests/unit/test_kim_retrieval_audit.py",
                 "docs/records/kim_retrieval_audit_protocol_v0.1.md"):
        path = output / "source_snapshot" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        files.save(path, (ROOT / name).read_bytes())
    files.verify(bindings)
    files.manifest(output)
    return summary


def render(report: dict[str, Any], capture: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(text) + '</pre></details>'

    summary = report["summary"]
    links = ' · '.join('<a href="' + esc(Path(path).as_uri()) + '">' + esc(label) + '</a>'
                       for label, path in report["artifact_paths"].items())
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: потеря Kim2015</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}</style><h1>Kim2015: потеря до позднего ранжирования</h1><p>'
        + esc(capture["question"]) + '</p><p>Kim отсутствует в обоих исходных top-50. В отдельной расширенной '
        'выдаче первая позиция exact — ' + str(summary["target_best_expanded_ranks"]["exact"])
        + ', semantic — ' + str(summary["target_best_expanded_ranks"]["semantic"]) + '. Полная итоговая трасса совпала '
        'с исходной. Это воспроизведение, не историческая запись внутренних стадий.</p><p>Запрос не активировал '
        'RU/EN glossary concepts; единственный вариант — исходный русский. Semantic model: BAAI/bge-small-en-v1.5. '
        'Причинный эффект смены модели/перевода не измерялся. Runtime, scoring, thresholds не менялись. '
        'Model/OAuth/новые slots: 0. План:75%, научная приёмка открыта.</p><p>Версия: ' + esc(VERSION)
        + '; input capture SHA256: ' + esc(files.sha(files.encode(capture))) + '.</p>'
        + '<p>' + links + '</p>'
        + detail('Итоги и пределы', summary) + detail('Replay и отрицательный контроль', report["replay"])
        + '<h2>Фактические границы; вложенные каналы не образуют одну цепочку</h2><table><thead><tr>'
        '<th>Граница</th><th>Parent</th><th>Chunks</th><th>Места Kim</th></tr></thead><tbody>')
    for row in report["observations"]:
        body += ('<tr><td>' + esc(row["name"]) + '</td><td>' + esc(row["parent"]) + '</td><td>'
                 + str(row["count"]) + '</td><td>' + esc([r["rank"] for r in row["target_article_rows"]]) + '</td></tr>')
    body += ('</tbody></table>' + detail('Все позиции Kim в отдельно расширенных каналах', report["expanded_target_ranks"])
        + '<h2>Лексический допуск</h2><p>Gate принял 7/9 terms без «морфология» и «частиц». Все три lexical '
        'admission predicates выполнены; required concepts и relation requirements для вопроса пусты. '
        'Ни это покрытие, ни существование citation IDs не проверяют запрошенную научную связь. '
        'Три constructed controls — примеры разработки, не независимый оценочный набор.</p>'
        + detail('Точный пересчёт, raw spans и constructed controls', report["gate_audit"])
        + '<h2>Исходный текст и лигатуры</h2><p>SQL ILIKE ищет в raw Chunk.text. В 20 из24 chunks Kim '
        'запрос не совпадает ни с одним query term; после диагностического раскрытия лигатур во всех24 '
        'появляется только Nafion. Это не исправление индекса/поиска и не доказательство достаточности текста.</p>'
        + detail('Полная диагностика24 chunks', report["target_lexical_inventory"])
        + '<h2>Восемь точных PDF окон; наличие статьи не равно наличию утверждения</h2>')
    for anchor in report["source_anchors"]:
        window = anchor["window"]
        body += ('<p><a href="' + esc(Path(window["original_pdf_path"]).as_uri() + '#page=' + str(window["pdf_page"]))
                 + '">' + esc(anchor["label"]) + ', PDF с.' + str(window["pdf_page"]) + '</a></p>'
                 + detail('Точный источник и наличие в chunks', anchor))
    body += (detail('Пять исходных generation evidence', capture["trace"]["evidence"])
        + '<h2>TAC: все работы исходных и отдельно расширенных каналов</h2><p>Здесь '
        + str(len(report["articles"])) + ' работ. Метаданные зарегистрированы в БД; для работ вне исходного capture '
        'явно указан архивный snapshot30 октября. Поля Conclusions/Terms не собирались; неизвестные значения сохранены. '
        'Все оригинальные PDF проверены по SHA256. Expanded выдача не передавалась модели.</p>'
        '<label>Поиск по TAC <input id="q" type="search"></label><table id="tac"><thead><tr>'
        + ''.join('<th>' + label + '</th>' for label in ('Title', 'Authors', 'Journal', 'Year', 'Abstract',
                                                       'Conclusions', 'Terms', 'hyperlink to original file'))
        + '</tr></thead><tbody>')
    for article in report["articles"]:
        body += '<tr data-row>'
        for field in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = article[field]
            body += '<td>' + ('Неизвестно / не собрано' if value is None else detail('Полное значение', value)) + '</td>'
        body += ('<td><a href="' + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
                 + detail('Происхождение метаданных', article) + '</td></tr>')
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});'
             '</script></html>')
    files.save(output / 'review.html', body.encode('utf-8'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captured', required=True, type=Path)
    parser.add_argument('--expanded', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(review(args.captured, args.expanded, args.output, policy), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
