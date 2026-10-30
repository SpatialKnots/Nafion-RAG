"""Offline ASGI replay and explicit post-hoc source review; never another model call."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.run_user_questions_20261030_live import ELIGIBLE, read_scope  # noqa: E402

POPPLER = Path(r"C:\Users\unive\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe")
ROWS = (
    ("ацетонитрил", "0.14", "0.12"), ("ацетон", "0.38", "0.27"), ("вода", "0.38", "0.35"),
    ("изопропанол", "0.83", "0.49"), ("диметилсульфоксид", "0.89", "1.12"),
    ("N,N-диметилформамид", "0.72", "1.15"), ("метанол", "1.14", "1.18"), ("этанол", "1.44", "1.33"),
    ("N-метил-2-пирролидон", "0.64", "1.37"),
)


def run(root: Path, prepared_review: Path, output: Path, policy: files.NetworkPolicy) -> dict[str, Any]:
    import fitz
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    from app.db.session import get_session
    from app.generation import service
    from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider, _json
    from app.generation.presentation import capture_sources
    from app.generation.providers import Evidence
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult
    from app.ui import _answer_payload_panel

    if output.exists():
        raise FileExistsError(output)
    frozen = read_scope(root, prepared_review)
    summary = json.loads((root / "live_summary.json").read_bytes())
    if [c["id"] for c in summary["cases"]] != list(ELIGIBLE):
        raise ValueError("Expected both authorized cases to have completed")
    bindings = {**frozen["bindings"], **files.bindings([
        Path(__file__), prepared_review / "report.json", root / "live_dispatch.json", root / "live_summary.json",
        root.parent / "authorization_20261030.json", POPPLER])}
    cases, source_registry, articles = [], {}, frozen["articles"]
    output.mkdir(parents=True, exist_ok=False)
    for row in frozen["cases"]:
        for p in row["sources"]["pages"].values():
            source_registry[(p["article_id"], p["page_number"])] = p

    for case_id in ELIGIBLE:
        prepared, live = root / case_id / "prepared", root / case_id / "live"
        files.verify_manifest(prepared)
        files.verify_manifest(live)
        result = json.loads((live / "result.json").read_bytes())
        api = json.loads((live / "api_response.json").read_bytes())
        trace = json.loads((live / "trace.json").read_bytes())
        if (result["model_attempts"], result["oauth_attempts"]) != (1, 1):
            raise ValueError("Observed call budget differs")
        if (live / "request.json").read_bytes() != (prepared / "request.json").read_bytes():
            raise ValueError("Actual native request differed from preparation")
        for name in ("trace.json", "sources.json", "articles.json"):
            if (live / name).read_bytes() != (prepared / name).read_bytes():
                raise ValueError("Actual prepared/live source trace differs")
        contract = json.loads((prepared / "contract.json").read_bytes())
        slot = files.LEDGER / contract["request_sha256"]
        for name in ("attempt.json", "result.json"):
            if (slot / name).read_bytes() != (live / name).read_bytes():
                raise ValueError("Global slot/result differs")
            bindings.update(files.bindings([slot / name]))
        bindings.update(files.bindings([p for p in live.iterdir() if p.is_file()]))
        raw = (live / "response.bin").read_bytes()
        native = _json(raw)
        if native["choices"][0]["finish_reason"] != "stop":
            raise ValueError("Unexpected native finish reason")
        retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                                   results=[SearchResult(**r) for r in trace["retrieval"]["results"]])
        called = []

        def post(self: Any, url: str, body: bytes, authorization: str, *, oauth: bool = False,
                 expected: bytes = (prepared / "request.json").read_bytes(), saved: bytes = raw,
                 calls: list[str] = called) -> bytes:
            if url != (AUTH_URL if oauth else CHAT_URL):
                raise ValueError("Unexpected offline boundary")
            calls.append("oauth_placeholder" if oauth else "saved_native_response")
            if oauth:
                return b'{"access_token":"offline-replay-placeholder"}'
            if body != expected:
                raise ValueError("Offline replay native request bytes differ")
            return saved

        def no_session():
            yield object()

        previous_overrides = dict(app.dependency_overrides)
        app.dependency_overrides[get_session] = no_session
        try:
            with patch.object(service, "search_chunks", return_value=retrieval), patch.object(
                    GigaChatAnswerProvider, "_post", post), patch.object(
                    Engine, "connect", side_effect=AssertionError("DB forbidden in offline replay")) as guard:
                with TestClient(app) as client:
                    response = client.post("/answer", json=json.loads((prepared / "api_request.json").read_bytes()))
                if guard.call_count:
                    raise ValueError("DB connection attempted")
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
        if response.status_code != api["http_status"] or response.json() != api["body"]:
            raise ValueError("Full offline ASGI status/body differs")
        if called != ["oauth_placeholder", "saved_native_response"]:
            raise ValueError("Unexpected replay boundary inventory")
        evidence = [Evidence(**e) for e in trace["evidence"]]
        panel = _answer_payload_panel(api["body"], retrieval.query, capture_sources(retrieval, evidence))
        cases.append({"id": case_id, "question": retrieval.query, "original_api": api, "original_native": native,
                      "original_result": result, "original_trace": trace, "panel_html": panel,
                      "offline_asgi_replay": "identical_http_status_and_complete_body", "replay_db_connections": 0,
                      "replay_real_model_oauth_calls": 0})

    q3 = root / "q3_lithiation_methods"
    if (q3 / "live").exists() or (q3 / "prepared/request.json").exists():
        raise ValueError("Blocked third case must not have a live run/request")
    gate = json.loads((q3 / "prepared/gate_response.json").read_bytes())
    if gate["http_status"] != 200 or gate["body"]["status"] != "insufficient_evidence":
        raise ValueError("Original third-case rejection differs")

    dissertation_id = "6f6fca14-92e8-446d-b1cd-ec08ca811962"
    sanginov_id = "aec95165-f993-4576-9dba-0ec4bb8ecee1"
    pdf_paths = {key: Path(values[0]["original_pdf_path"]) for key, values in articles.items()}
    inspected: dict[tuple[str, int], dict[str, Any]] = {}
    for article_id, numbers in ((dissertation_id, (28, 29, 51, 52, 55, 97)), (sanginov_id, (1, 2, 3, 9, 10, 11, 12))):
        path = pdf_paths[article_id]
        digest = files.sha(path.read_bytes())
        with fitz.open(path) as pdf:
            for number in numbers:
                text = pdf[number - 1].get_text("text")
                if (article_id, number) in source_registry and text != source_registry[(article_id, number)]["page_text"]:
                    raise ValueError("Fresh inspected page differs from captured source")
                membership = {r["case"]["id"]: any(p["article_id"] == article_id and p["page_number"] == number
                    for p in r["sources"]["pages"].values()) for r in frozen["cases"]}
                inspected[(article_id, number)] = {"article_id": article_id, "page_number": number,
                    "original_pdf_path": str(path), "original_pdf_sha256": digest, "text_layer": "original", "page_text": text,
                    "page_text_sha256": files.sha(text.encode()), "selected_prepared_page_by_question": membership,
                    "actual_model_input_page_by_question": {k: v and k in ELIGIBLE for k, v in membership.items()},
                    "review_origin": "assistant_posthoc_source_inspection_not_independent_reference"}
        bindings.update(files.bindings([path]))

    def window(label: str, article_id: str, number: int, pattern: str) -> dict[str, Any]:
        page = inspected[(article_id, number)]
        match = re.search(pattern, page["page_text"], re.S)
        if match is None:
            raise ValueError("Declared source-review anchor not found: " + label)
        return {"label": label, **{k: v for k, v in page.items() if k != "page_text"},
                "start": match.start(), "end": match.end(), "exact_text": match.group()}

    table_rows = []
    page = inspected[(dissertation_id, 97)]
    for solvent, h, li in ROWS:
        pattern = re.escape(solvent) + r"\s+(?P<h>\d+\.\d+)\s+[−-]?\d+(?:\.\d+)?\s+(?P<li>\d+\.\d+)\s+[−-]?\d+(?:\.\d+)?"
        match = re.search(pattern, page["page_text"], re.I)
        if match is None or (match["h"], match["li"]) != (h, li):
            raise ValueError("Post-hoc table transcription differs: " + solvent)
        a, b = Decimal(h), Decimal(li)
        table_rows.append({"solvent": solvent, "alpha_h": h, "alpha_li": li, "delta_alpha": str(b - a),
            "relative_change_percent": str(((b - a) / a * 100).quantize(Decimal("0.01"))),
            "li_greater": b > a, "source": {k: v for k, v in page.items() if k != "page_text"},
            "start": match.start(), "end": match.end(), "exact_text": match.group(),
            "origin": "assistant_posthoc_table_transcription_and_arithmetic_not_independent_gold"})
    if sum(r["li_greater"] for r in table_rows) != 4:
        raise ValueError("Unexpected table comparison count")
    windows = [
        window("alpha_mass_definition", dissertation_id, 55, r"Равновесное набухание[\s\S]*?масса сухой мембраны\."),
        window("ec_sl_mass_fraction_basis", sanginov_id, 1, r"The weight fraction of SL[\s\S]*?wt\. %\."),
        window("ec_sl_peak_conductivity", sanginov_id, 9, r"Fig\. 10 shows[\s\S]*?Although only slightly inferior"),
        window("ec_sl_combined_objective", sanginov_id, 10, r"to the membrane[\s\S]*?best among the studied samples\."),
        window("ec_sl_own_table_row_and_temperature_footnote", sanginov_id, 11,
               r"Li-Naﬁon-115\s+EC/SL b[\s\S]*?d at 20 °C\."),
        window("ec_sl_not_universal_maximum", sanginov_id, 12, r"One can see that Li-Naﬁon-115[\s\S]*?lithium-ion batteries\."),
        window("membrane_exchange_start", dissertation_id, 51, r"На втором этапе[\s\S]*?1\.0 М LiOH,"),
        window("membrane_exchange_continuation", dissertation_id, 52, r"приготовленном на смеси[\s\S]*?14 суток\."),
        window("dispersion_neutralization", dissertation_id, 52, r"2\.2\.1\.[\s\S]*?без выпадения осадка\."),
    ]
    views = output / "source_pdf_views"
    views.mkdir()
    for (article_id, number), page in inspected.items():
        prefix = views / (("dissertation" if article_id == dissertation_id else "sanginov") + "_p" + str(number))
        subprocess.run([str(POPPLER), "-f", str(number), "-l", str(number), "-singlefile", "-scale-to", "1800",
                        "-png", page["original_pdf_path"], str(prefix)], capture_output=True, check=True)
    assessment = {
        "origin": "assistant_posthoc_source_review_not_independent_scientific_evaluation",
        "q1": {"finding": "Cited Table 4.5 has Li>H in 4 of 9 rows and Li<H in 5; the model's majority generalization is not supported.",
               "rows": table_rows, "temperature": "not_stated_in_table_4_5_heading_no_temperature_assumed",
               "scope": "nine_rows_only_not_all_solvents_or_literature"},
        "q2": {"finding": "The unqualified best-mixture claim is not established; composition, conductivity and temperature are omitted.",
               "posthoc_scope": "Within the studied EC/SL series, p.9 reports a conductivity peak at SL mass fraction 0.20; "
                                "p.10 favors 0.40 for conductivity plus operating-temperature range. "
                                "Neither is a universal mixture optimum.",
               "temperature_caveat": "The own-work row in p.11 Table 2 has 1.1e-4 S/cm at 20 C by footnote d, "
                                     "not the nominal 25 C column header.",
               "new_pages_were_not_model_input": [9, 10, 11, 12]},
        "q3": {"finding": "Production gate rejected before the model despite a selected LiOH exchange description.",
               "posthoc_scope": "Dissertation pp.51-52 separately describes membrane ion exchange "
                                "and neutralization of a Nafion dispersion; "
                                "p.52 continuation was not selected in q3. No exhaustive method catalogue or model answer is claimed."},
        "raw_answers_modified": False, "independent_accuracy": None, "scientific_acceptance": "not_established"}
    total_usage = {key: sum(c["original_result"]["usage"][key] for c in cases)
                   for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    report = {"version": "user_questions_live_review_v0.1", "bindings": bindings, "cases": cases,
        "third_original_gate_response": gate, "third_trace": frozen["cases"][2]["trace"], "articles": articles,
        "source_windows": windows, "inspected_pages": list(inspected.values()), "assistant_source_review": assessment,
        "summary": {"actual_model_posts": 2, "actual_oauth_exchanges": 2, "automatic_retries": 0, "fallbacks": 0,
                    "http_outcomes": [c["original_api"]["http_status"] for c in cases], "native_finish_reasons": ["stop", "stop"],
                    "usage": total_usage, "offline_asgi_replays_identical": 2, "postflight_real_model_oauth_calls": 0,
                    "original_selected_works": len(articles), "source_pdf_pages_rendered": len(inspected),
                    "budgets": "both_new_slots_consumed_closed_no_retry", "independent_accuracy": None},
        "network_denials": policy.denied, "scientific_acceptance": "not_established"}
    files.verify(bindings)
    files.write(output / "report.json", report)
    render(report, output)
    files.save(output / "postflight_source.py", Path(__file__).read_bytes())
    return report["summary"]


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(raw) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — фактические ответы и сверка</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}.source-exact{white-space:pre-wrap;max-height:30rem;overflow:auto}'
        '.claim-source{border:1px solid #abc;padding:10px;margin:10px 0}img{max-width:100%}</style>'
        '<h1>Два реальных ответа и отдельная проверка источников</h1><p>Ровно 2 model POST и 2 OAuth exchange, '
        'без повторов. Оба HTTP 200 / answered. Третий вопрос остался HTTP 200 / insufficient_evidence до модели. '
        'Все новые slots исчерпаны и закрыты.</p><p>Версия: ' + esc(report["version"]) + '; bindings SHA256: '
        + files.sha(files.encode(report["bindings"])) + '. Независимой scientific accuracy/приёмки нет.</p>')
    for case in report["cases"]:
        body += ('<section><h2>Исходный ответ системы: ' + esc(case["question"]) + '</h2>' + case["panel_html"]
                 + detail("Полный неизменённый API result", case["original_api"])
                 + detail("Полный native response, результат и usage", {k: case[k] for k in ("original_native", "original_result")})
                 + '</section>')
    body += ('<h2>Третий вопрос: исходный отказ до модели</h2>' + detail("HTTP/status/body", report["third_original_gate_response"])
        + '<h2>Отдельная post-hoc проверка ассистента</h2><p>Это не текст модели и не independent gold. '
        'Первый ответ не поддержан большинством строк цитируемой таблицы: Li выше H в 4/9, ниже в 5/9. '
        'Второй ответ не обосновывает универсальный максимум и не сообщает состав/условия.</p>'
        '<h3>Набухание: H-Nafion → Li-Nafion в табл.4.5</h3><img src="swelling_comparison.png" alt="Парное сравнение девяти растворителей">'
        '<p>Δ и проценты рассчитаны ассистентом из табл.4.5; температура в её заголовке не указана. '
        'Определение α отдельно проверено на с.55. Это не модельный вывод.</p>'
        '<table><tr><th>Растворитель</th><th>αH</th><th>αLi</th><th>Δα</th><th>Изменение, %</th></tr>')
    for row in report["assistant_source_review"]["q1"]["rows"]:
        body += '<tr>' + ''.join('<td>' + esc(row[k]) + '</td>' for k in
            ("solvent", "alpha_h", "alpha_li", "delta_alpha", "relative_change_percent")) + '</tr>'
    body += ('</table><h3>EC/SL: разные критерии «лучше»</h3><p>В исследованной EC/SL серии максимум проводимости '
        'сообщён при ω(SL)=0.20 (80:20 по массе; пересчёт ассистента). '
        'ω(SL)=0.40 авторы предпочитают по сочетанию проводимости и рабочего температурного диапазона. '
        'Эти результаты не устанавливают лучшую смесь среди всей литературы. Страницы 9–12 проверены после ответа, '
        'модели переданы только зарегистрированные источники с.1–3 и диссертации с.28–29.</p>'
        '<h3>Литирование: source hints после исходного отказа</h3><p>Диссертация с.51–52 описывает обмен H→Li '
        'для готовых мембран и отдельно нейтрализацию водно-спиртовой дисперсии LiOH. '
        'Продолжение на с.52 не входило в отобранный контекст третьего вопроса; полного каталога методов нет.</p>'
        + detail("Полная отдельная оценка и ограничения", report["assistant_source_review"]))
    for window in report["source_windows"]:
        url = Path(window["original_pdf_path"]).as_uri() + "#page=" + str(window["page_number"])
        body += '<p><a href="' + esc(url) + '">PDF с.' + str(window["page_number"]) + '</a></p>' + detail(window["label"], window)
    body += ('<h2>TAC: все выбранные работы трёх вопросов</h2><p>Missing metadata и несобранные поля сохранены.</p>'
        '<label>Поиск <input type="search" id="q"></label><table id="tac"><thead><tr>'
        + ''.join('<th>' + h + '</th>' for h in ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms',
                                               'hyperlink to original file')) + '</tr></thead><tbody>')
    for values in report["articles"].values():
        article = values[0]
        body += '<tr>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = article.get(key)
            if value is None:
                content = 'Неизвестно / не собрано'
            elif key in {"abstract", "conclusions", "terms"}:
                content = detail("Полный текст", value)
            elif key == "authors" and isinstance(value, list) and all(isinstance(a, dict) and a.get("name") for a in value):
                content = esc('; '.join(a["name"] for a in value))
            else:
                content = esc(value if isinstance(value, (str, int)) else json.dumps(value, ensure_ascii=False))
            body += '<td>' + content + '</td>'
        body += ('<td><a href="' + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
                 + detail("Все архивные metadata/provenance", values) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итоги, usage и ограничения", report["summary"])
        + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
        'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prepared-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    files.configure()
    print(json.dumps(run(args.root, args.prepared_review, args.output, policy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
