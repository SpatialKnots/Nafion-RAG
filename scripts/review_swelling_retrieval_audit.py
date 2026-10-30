"""Verify/replay a frozen retrieval-loss capture and write a local HTML review, without DB/model calls."""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.retrieval_loss_audit import VERSION, retention_path  # noqa: E402

PATH = (
    "_rerank_cross_lingual_results:1:input", "_legacy_rerank_cross_lingual_results:1:output",
    "_diversify_cross_lingual_results:1:output", "feature_rerank_cross_lingual_results:1:input",
    "feature_rerank_cross_lingual_results:1:output", "_rerank_cross_lingual_results:1:output",
    "_diversify_cross_lingual_results:2:output", "_ensure_cross_language_presence:1:output",
    "retrieval_top_k", "generation_evidence",
)


def replay(capture: dict[str, Any], settings: Any) -> dict[str, Any]:
    """Run real fusion/ranking/evidence code with frozen search channel outputs only."""
    from sqlalchemy.engine import Engine

    from app.generation import service
    from app.retrieval import search
    from app.retrieval.cross_lingual import build_query_bundle
    from scripts.run_swelling_retrieval_audit import CaptureComplete, NoGeneration

    stages = {s["name"]: s for s in capture["stages"]}
    request = capture["request"]
    question = request["question"]
    bundle = build_query_bundle(question)
    checked: list[str] = []

    def response(name: str, query: str) -> Any:
        stage = stages[name]
        return search.SearchResponse(query=query, results=[search.SearchResult(**r) for r in stage["results"]],
                                     metadata=stage["metadata"])

    def check(name: str, rows: Any) -> None:
        if [asdict(r) for r in rows] != stages[name]["results"]:
            raise ValueError("Replay differs at " + name)
        checked.append(name)

    with patch.object(Engine, "connect", side_effect=AssertionError("DB forbidden in offline replay")) as db_guard:
        with patch.object(search, "exact_search", return_value=response("exact_search:1:output", question)), patch.object(
                search, "semantic_search", return_value=response("semantic_search:1:output", question)):
            hybrid = search.hybrid_search(object(), question, request["collection"],
                search._cross_lingual_variant_top_k(bundle, top_k=request["top_k"], settings=settings), settings=settings)
        check("hybrid_search:1:output", hybrid.results)
        fused = [search.SearchResult(**r) for r in stages["_rerank_cross_lingual_results:1:input"]["results"]]
        legacy = search._legacy_rerank_cross_lingual_results(fused, bundle)
        check("_legacy_rerank_cross_lingual_results:1:output", legacy)
        diverse = search._diversify_cross_lingual_results(legacy, preferred_per_article=2)
        check("_diversify_cross_lingual_results:1:output", diverse)
        window_size = capture["trace"]["retrieval"]["metadata"]["reranking"]["window_size"]
        check("feature_rerank_cross_lingual_results:1:input", diverse[:window_size])
        feature = search.feature_rerank_cross_lingual_results(diverse[:window_size], original_query=question,
            query_language=bundle.language, query_variants=[(v.source, v.text) for v in bundle.variants])
        check("feature_rerank_cross_lingual_results:1:output", feature.results)
        reranked = search._rerank_cross_lingual_results(fused, bundle, window_size=window_size)
        check("_rerank_cross_lingual_results:1:output", reranked.results)
        diverse = search._diversify_cross_lingual_results(reranked.results, preferred_per_article=2)
        check("_diversify_cross_lingual_results:2:output", diverse)
        language, _ = search._ensure_cross_language_presence(diverse, query_language=bundle.language, top_k=request["top_k"])
        check("_ensure_cross_language_presence:1:output", language)
        check("retrieval_top_k", language[:request["top_k"]])

        exact_calls = []

        def exact(_session: Any, query: str, *args: Any, **kwargs: Any) -> Any:
            exact_calls.append(query)
            index = next(i for i, variant in enumerate(bundle.variants) if variant.text == query and i > 0)
            return response(f"exact_search:{index + 1}:output", query)

        traced: dict[str, Any] = {}

        def observer(retrieval: Any, evidence: Any, metadata: Any) -> None:
            traced.update(retrieval=asdict(retrieval), evidence=[asdict(e) for e in evidence], metadata=metadata)

        with patch.object(search, "hybrid_search", return_value=hybrid), patch.object(search, "exact_search", exact):
            result = search.hybrid_cross_lingual_search(object(), question, request["collection"], request["top_k"], settings=settings)
        if asdict(result) != capture["trace"]["retrieval"]:
            raise ValueError("Cross-lingual channel fusion/full retrieval replay differs")
        if exact_calls != [v.text for v in bundle.variants[1:]]:
            raise ValueError("Replay channel inventory differs")
        with patch.object(service, "search_chunks", return_value=result), patch.object(
                service, "build_answer_provider", side_effect=AssertionError("Provider forbidden")):
            try:
                service.answer_question(object(), settings, question, collection=request["collection"], top_k=request["top_k"],
                    method=request["method"], answer_style=request["answer_style"], answer_language=request["answer_language"],
                    provider=NoGeneration(), trace_observer=observer)
            except CaptureComplete:
                pass
        if traced != capture["trace"]:
            raise ValueError("Full answer evidence/adequacy trace replay differs")
        if db_guard.call_count:
            raise ValueError("Database connection was attempted during replay")
    return {"checked_boundaries": checked, "full_trace_identical": True, "db_connections": 0,
            "model_calls": 0, "oauth_calls": 0, "local_embedding_inference": 0}


def review(captured: Path, output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    settings = files.configure()
    files.verify_manifest(captured)
    raw = (captured / "capture.json").read_bytes()
    capture = json.loads(raw)
    if capture["version"] != VERSION or not capture["historical_final_trace_identical"]:
        raise ValueError("Expected version and identical historical final trace are required")
    files.verify(capture["bindings"])
    outcome = replay(capture, settings)
    stages = {s["name"]: s for s in capture["stages"]}
    target = capture["target"]
    from app.retrieval import reranking
    from app.retrieval.cross_lingual import build_query_bundle
    from app.retrieval.search import SearchResult

    bundle = build_query_bundle(capture["question"])
    variants = [(v.source, v.text) for v in bundle.variants]
    feature_stage = stages["feature_rerank_cross_lingual_results:1:output"]
    metadata = feature_stage["metadata"]
    comparison_enabled = reranking._has_swelling_comparison_intent(bundle.original, variants)
    target_ids = {c["chunk_id"] for c in capture["database_target_inventory"]}
    features = []
    for rank, row in enumerate(feature_stage["results"], 1):
        if rank <= 2 or row["chunk_id"] in target_ids:
            calculated = reranking._features_for_result(SearchResult(**row), query_language=bundle.language,
                protected_tokens=metadata["protected_tokens"], query_terms=metadata["query_terms"],
                query_phrases=metadata["query_phrases"],
                variant_terms=[(source, reranking._query_terms_for_rerank(t)) for source, t in variants],
                swelling_comparison_intent=comparison_enabled,
                conductivity_plasticizer_intent=reranking._has_conductivity_plasticizer_intent(bundle.original, variants),
                query_intents=set(metadata["query_intents"]))
            if rank <= 2:
                saved = next(r for r in metadata["top_features"] if r["chunk_id"] == row["chunk_id"])
                if any(saved[k] != v for k, v in asdict(calculated).items()):
                    raise ValueError("Recalculated ranking features differ")
            features.append({"chunk_id": row["chunk_id"], "page_start": row["page_start"], "page_end": row["page_end"],
                             "rank": rank, "target": row["chunk_id"] in target_ids, **asdict(calculated)})
    feature_diagnostics = {
        "comparison_intent_original_question_only": reranking._has_swelling_comparison_intent(bundle.original, []),
        "comparison_intent_with_glossary_variants": comparison_enabled, "features": features,
        "scope": "Source-visible ranking signals only; no scientific maximum/temperature/mixture validation or counterfactual fix.",
    }
    timeline = retention_path([stages[name] for name in PATH], article_id=target["article_id"],
                              page_number=target["page_number"], exact_text=target["exact_text"])
    losses = [row["name"] for row in timeline if row["transition"] == "lost"]
    if losses != ["retrieval_top_k"]:
        raise ValueError("Observed loss differs from the declared diagnosis")
    # Deliberately corrupted expected data must fail replay; never mutate original capture.
    corrupted = json.loads(raw)
    damaged = next(s for s in corrupted["stages"] if s["name"] == "_diversify_cross_lingual_results:2:output")
    damaged["results"] = list(reversed(damaged["results"]))
    try:
        replay(corrupted, settings)
    except ValueError as exc:
        if str(exc) != "Replay differs at _diversify_cross_lingual_results:2:output":
            raise
        outcome["corrupted_boundary_control"] = "rejected_at_expected_boundary"
    else:
        raise ValueError("Replay accepted corrupted expected boundary")
    bindings = {**capture["bindings"], **files.bindings([
        captured / "capture.json", captured / "manifest.json", Path(__file__),
        ROOT / "tests/unit/test_retrieval_loss_audit.py", ROOT / "docs/answer_quality_plan_2026-10-30.md",
    ])}
    report = {"version": VERSION, "bindings": bindings, "capture_sha256": files.sha(raw), "replay": outcome,
        "timeline": timeline, "target": target, "feature_diagnostics": feature_diagnostics,
        "diagnosis": "Target survives all candidate/reranking windows, ranks 17/18 after feature reranking, "
                     "60/61 after final article diversification; top-5 truncation removes it before answer evidence selection.",
        "historical_inference": "Historical internal stages unavailable; current unchanged implementation/input files "
                                "reproduces the complete historical final trace. This is a reproduction diagnosis.",
        "ranking_fix": "not_implemented", "scientific_acceptance": "not_established", "independent_accuracy": None,
        "network_denials": policy.denied, "article_count": len(capture["articles"])}
    output.mkdir(parents=True, exist_ok=False)
    files.write(output / "report.json", report)
    for name in ("scripts/retrieval_loss_audit.py", "scripts/run_swelling_retrieval_audit.py",
                 "scripts/review_swelling_retrieval_audit.py", "tests/unit/test_retrieval_loss_audit.py",
                 "docs/answer_quality_plan_2026-10-30.md"):
        destination = output / "source_snapshot" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        files.save(destination, (ROOT / name).read_bytes())

    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return "<details><summary>" + esc(label) + "</summary><pre>" + esc(content) + "</pre></details>"

    def cell(value: Any) -> str:
        if value is None:
            return "Неизвестно / не собрано на этом этапе"
        if isinstance(value, (list, dict)):
            return detail("Полное значение", value)
        return detail("Полный текст", value)

    target_pdf = Path(target["original_pdf_path"]).as_uri() + "#page=" + str(target["page_number"])
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: потеря evidence Li-Nafion</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}</style><h1>Локализация потери evidence</h1><p>' + esc(capture["question"])
        + '</p><p><strong>Страница с ≈1,8 найдена поиском, но исключена при отсечении top-5.</strong> '
        'Места после feature reranking: 17–18; после article diversification: 60–61. '
        'Полная итоговая трасса совпала со вчерашней. Runtime/ranking не изменены; новых model/OAuth calls — 0.</p>'
        '<p>Версия: ' + esc(VERSION) + '; input capture SHA256: ' + esc(files.sha(raw)) + '.</p>'
        '<p>Это воспроизведённый диагноз одного exposed случая. Вчерашние внутренние стадии не сохранялись. '
        'Независимая точность и общий максимум не установлены. 33 строки TAC — охват кандидатов, не 33 подтверждения.</p>'
        '<p><a href="' + esc(target_pdf) + '">Оригинальный PDF, с.75</a> · <a href="'
        + esc((captured / "capture.json").resolve().as_uri()) + '">Полная трасса и все тексты кандидатов</a></p>'
        + detail("Точный фрагмент контрпримера; источник выбран после прежнего ответа", target)
        + detail("Offline replay и отрицательный контроль", outcome)
        + detail("Признаки ранжирования: сравнение форм включилось после glossary expansion", feature_diagnostics)
        + '<h2>Путь через ранжирование и отбор</h2><table><thead><tr><th>Стадия</th><th>Число chunks</th>'
        '<th>Места точного фрагмента</th><th>Переход</th></tr></thead><tbody>')
    for row in timeline:
        body += ('<tr><td>' + esc(row["name"]) + '</td><td>' + str(row["count"]) + '</td><td>'
                 + esc([r["rank"] for r in row["exact_anchor_matches"]]) + '</td><td>' + esc(row["transition"]) + '</td></tr>')
    body += ('</tbody></table>' + detail("Каналы поиска отдельно; не линейная цепочка", capture["observations"])
        + detail("Два исходных chunks с точным фрагментом", capture["database_target_inventory"])
        + detail("Полные пять generation evidence", capture["trace"]["evidence"])
        + '<h2>TAC: все работы, встреченные на записанных стадиях</h2><p>Метаданные из БД; независимо не проверены. '
        'Abstract показывается целиком при наличии; Conclusions и Terms в этом этапе не собирались. '
        'Неизвестные поля не восстановлены догадками.</p><label>Поиск по таблице <input id="q" type="search"></label>'
        '<table id="tac"><thead><tr>'
        + ''.join('<th>' + c + '</th>' for c in ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms',
                                                'hyperlink to original file')) + '</tr></thead><tbody>')
    for article in capture["articles"]:
        body += ('<tr>' + ''.join('<td>' + cell(article[k]) + '</td>' for k in
            ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms')) + '<td><a href="'
            + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
            + detail("Происхождение и диагностика", article) + '</td></tr>')
    body += ('</tbody></table><script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});'
             '</script></html>')
    files.save(output / "review.html", body.encode("utf-8"))
    files.verify(bindings)
    files.write(output / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(output).as_posix(): files.sha(p.read_bytes())
        for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"}})
    return {"replay": outcome, "loss_boundary": losses, "articles": len(capture["articles"]), "review": str(output / "review.html")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captured", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    print(json.dumps(review(args.captured, args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
