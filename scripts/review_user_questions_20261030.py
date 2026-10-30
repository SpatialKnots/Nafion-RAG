"""Review three frozen user-question preparations; no DB/provider operations."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402
from scripts.user_questions_20261030 import CASES, PROTOCOL, VERSION, load_cases  # noqa: E402


def no_network(event: str, args: Any) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("All networking forbidden in frozen preparation review")


def history_inventory() -> tuple[list[dict[str, Any]], list[Path]]:
    import yaml
    paths = sorted((ROOT / "docs").glob("evaluation_questions*.yaml"))
    rows = []

    def walk(node: Any, path: Path) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("query"), str):
                rows.append({"path": str(path), "id": node.get("id"), "query": node["query"]})
            for child in node.values():
                walk(child, path)
        elif isinstance(node, list):
            for child in node:
                walk(child, path)

    for path in paths:
        walk(yaml.safe_load(path.read_text(encoding="utf-8")), path)
    return rows, paths


def review(root: Path, output: Path) -> dict[str, Any]:
    import fitz

    from app.evaluation.context_compaction import SourcePage, complete_pages_in_request

    if output.exists():
        raise FileExistsError(output)
    cases = load_cases()
    history, history_paths = history_inventory()
    bindings = files.bindings([Path(__file__), CASES, PROTOCOL, *history_paths,
                              ROOT / "scripts/run_user_questions_20261030_live.py",
                              ROOT / "tests/unit/test_user_questions_live_20261030.py",
                              ROOT / "docs/records/user_questions_2026-10-30_live_scope_v0.1.md",
                              ROOT / "output/user_questions_preflight_20261030_v01.xml",
                              ROOT / "output/user_questions_preflight_20261030_v02.xml"])
    rows, metadata = [], {}
    verified_pages: dict[tuple[str, int], str] = {}
    eligibility = []
    for case in cases:
        folder = root / case["id"] / "prepared"
        files.verify_manifest(folder)
        contract = json.loads((folder / "contract.json").read_bytes())
        if (contract["id"], contract["question"], contract["version"]) != (case["id"], case["question"], VERSION):
            raise ValueError("Frozen preparation question/version differs")
        if contract["maximum_model_attempts"] or contract["maximum_oauth_attempts"] or contract["new_slot_reservations"]:
            raise ValueError("Preparation must not authorize/reserve live calls")
        files.verify(contract["input_bindings"])
        for name, digest in contract["input_bindings"].items():
            if name in bindings and bindings[name] != digest:
                raise ValueError("Prepared input bindings conflict: " + name)
            bindings[name] = digest
        bindings.update(files.bindings([p for p in folder.iterdir() if p.is_file()]))
        trace = json.loads((folder / "trace.json").read_bytes())
        sources = json.loads((folder / "sources.json").read_bytes())
        articles = json.loads((folder / "articles.json").read_bytes())
        for article in articles:
            if article not in metadata.setdefault(article["article_id"], []):
                metadata[article["article_id"]].append(article)
        for page in sources["pages"].values():
            path = Path(page["original_pdf_path"])
            if files.sha(path.read_bytes()) != page["original_pdf_sha256"]:
                raise ValueError("Original PDF changed")
            key = str(path), page["page_number"]
            if key not in verified_pages:
                with fitz.open(path) as pdf:
                    text = pdf[page["page_number"] - 1].get_text("text")
                if text != page["page_text"]:
                    raise ValueError("Fresh PDF page text differs")
                verified_pages[key] = files.sha(text.encode())
            if verified_pages[key] != page["page_text_sha256"]:
                raise ValueError("Frozen source page hash differs")
        native = None
        full_pages = []
        if contract["generation_reached"]:
            raw = (folder / "request.json").read_bytes()
            if files.sha(raw) != contract["request_sha256"] or len(raw) != contract["request_bytes"]:
                raise ValueError("Native request differs from frozen digest/size")
            native = json.loads(raw)
            if native["model"] != "GigaChat-2-Max" or native["max_tokens"] != 1200:
                raise ValueError("Native request model/limit differs")
            pages = [SourcePage(p["article_id"], p["region_id"], p["page_number"], p["text_layer"], p["text_layer_id"],
                                p["page_text"], p["layer_pdf_path"], p["layer_pdf_sha256"]) for p in sources["pages"].values()]
            full_pages = complete_pages_in_request(native["messages"][1]["content"], pages)
            if contract["preparation_status"] == "ready_for_explicit_scope_authorization":
                eligibility.append(case["id"])
        gate = json.loads((folder / "gate_response.json").read_bytes()) if (folder / "gate_response.json").exists() else None
        exact_prior = [h for h in history if " ".join(h["query"].casefold().split()) == " ".join(case["question"].casefold().split())]
        rows.append({"case": case, "contract": contract, "trace": trace, "sources": sources, "gate_response": gate,
                     "native_request": native, "complete_source_pages_in_prompt": full_pages,
                     "exact_casefold_whitespace_history_matches": exact_prior,
                     "independence": "user_authored_wording_not_independent_reference_or_unseen_topic_claim",
                     "model_answer": None, "independent_scientific_score": None})
    # Capture exact selected source hints for the blocked case, without reclassifying the runtime gate.
    blocked_hints = []
    for row in rows:
        if row["contract"]["generation_reached"]:
            continue
        for e in row["trace"]["evidence"]:
            for match in list(re.finditer(r"LiOH|LiCl|LiNO3", e["text"]))[:4]:
                start, end = max(0, match.start() - 180), min(len(e["text"]), match.end() + 240)
                excerpt = e["text"][start:end]
                page_anchors = []
                for p in row["sources"]["pages"].values():
                    if p["article_id"] == e["article_id"] and e["page_start"] <= p["page_number"] <= e["page_end"]:
                        for hit in re.finditer(re.escape(excerpt), p["page_text"]):
                            page_anchors.append({"page_number": p["page_number"], "start": hit.start(), "end": hit.end(),
                                                 "text": hit.group(), "original_pdf_path": p["original_pdf_path"]})
                blocked_hints.append({"case_id": row["case"]["id"], "citation_id": e["citation_id"],
                    "article_id": e["article_id"], "chunk_id": e["chunk_id"], "page_start": e["page_start"],
                    "page_end": e["page_end"], "chunk_start": start, "chunk_end": end, "exact_chunk_text": excerpt,
                    "exact_page_anchors": page_anchors,
                    "interpretation": "assistant_preflight_lexical_hint_only_not_model_answer_or_independent_reference"})
    summary = {"questions": len(rows), "eligible_for_separate_live_authorization": eligibility,
        "blocked_before_generation": [r["case"]["id"] for r in rows if not r["contract"]["generation_reached"]],
        "request_bytes": {r["case"]["id"]: r["contract"]["request_bytes"] for r in rows},
        "selected_documents": len(metadata), "fresh_pdf_pages_verified": len(verified_pages),
        "prior_query_inventory_size": len(history), "new_model_calls": 0, "new_oauth_calls": 0,
        "new_slot_reservations": 0, "review_db_operations": 0,
        "independent_reference_answers": None, "scientific_acceptance": "not_evaluated"}
    report = {"version": VERSION, "bindings": bindings, "cases": rows, "articles": metadata,
              "summary": summary, "blocked_source_hints": blocked_hints,
              "scope": "Frozen current-system preparation, no answers generated; all prior live budgets remain closed"}
    files.verify(bindings)
    output.mkdir(parents=True, exist_ok=False)
    files.write(output / "report.json", report)
    render(report, output)
    for name in bindings:
        p = Path(name)
        if p.is_relative_to(ROOT) and p.suffix in {".py", ".md", ".json", ".yaml"} and p.relative_to(ROOT).parts[0] in {
                "app", "scripts", "tests", "docs"}:
            dst = output / "source_snapshot" / p.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            files.save(dst, p.read_bytes())
    files.verify(bindings)
    files.write(output / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(output).as_posix(): files.sha(p.read_bytes()) for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "manifest.json"}})
    return summary


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(raw) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — три вопроса пользователя</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '[hidden]{display:none!important}</style><h1>Три вопроса: подготовка без вызовов модели</h1><p>Version: '
        + esc(VERSION) + '; input bindings SHA256: ' + files.sha(files.encode(report["bindings"]))
        + '.</p><p>Вопросы сохранены дословно. Ответы модели не получены, независимых эталонов нет. '
        'Тематическое пересечение с прежними проверками отмечено; это не unseen gold. '
        'Все прежние бюджеты закрыты; текущие live authorization и slot reservations — 0.</p>')
    for row in report["cases"]:
        c, contract = row["case"], row["contract"]
        body += ('<section><h2>' + esc(c["question"]) + '</h2><p><strong>' + esc(contract["preparation_status"])
            + '</strong>; native request bytes: ' + str(contract["request_bytes"]) + '</p>'
            + detail("Исходный gate/status и диагностика покрытия", row["gate_response"] or row["trace"]["metadata"])
            + detail("Требования вопроса и известное пересечение тем; не эталонный ответ", c)
            + detail("Замороженный contract и ограничения", contract)
            + detail("Полные страницы в фактическом raw-chunk prompt", row["complete_source_pages_in_prompt"]))
        if row["native_request"] is not None:
            body += detail("Полный неотправленный native request", row["native_request"])
        for e in row["trace"]["evidence"]:
            source = next((p for p in row["sources"]["pages"].values() if p["article_id"] == e["article_id"]), None)
            url = Path(source["original_pdf_path"]).as_uri() + "#page=" + str(e["page_start"]) if source else None
            label = str(e["title"] or "Название неизвестно") + " — с." + str(e["page_start"]) + "–" + str(e["page_end"])
            body += '<article><p>' + ('<a href="' + esc(url) + '">' + esc(label) + '</a>' if url else esc(label)) + '</p>'
            body += detail("Полный выбранный source fragment " + e["citation_id"], e["text"]) + '</article>'
        body += '</section>'
    body += (detail("Точные source hints в заблокированном случае; не обход gate", report["blocked_source_hints"])
        + '<h2>TAC: все выбранные работы трёх вопросов</h2><p>Метаданные из read-only capture; независимо не подтверждены. '
        'Missing/не собранные Abstract, Conclusions и Terms сохранены явно.</p>'
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
                 + detail("Все версии метаданных и provenance", values) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итоги", report["summary"])
        + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
        'document.querySelectorAll("#tac tbody tr").forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(s)})});</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    print(json.dumps(review(args.root, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
