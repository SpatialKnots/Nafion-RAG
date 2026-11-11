"""Consolidate exposed development evidence offline; never dispatch a real model request."""

from __future__ import annotations

import argparse
import html
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import replace
from pathlib import Path

import fitz

from scripts import bilingual_lexical_admission_20261110 as replay
from scripts import gigachat_answer_smoke as f
from scripts import quantitative_binding_20261111 as quant

BASE = f.ROOT / "output/answer_series_freeze_20261111"
FINAL = f.ROOT / "output/nambu_solubility_limit_20261111/comparison_v01"
QUESTIONS = f.ROOT / "output/kondo_nambu_peng_transfer_20261110/input_freeze_v01"
CAPTURE = f.ROOT / "output/refusal_groups_20261110/capture_v01"
POOLS = f.ROOT / "output/kondo_threshold_scope_20261111/capture_v01"
PROTOCOL = f.ROOT / "docs/records/answer_series_freeze_2026-11-11_v0.1.md"
IDS = [f"{label}_{n:02}" for label in ("Kondo", "Nambu", "Peng") for n in range(1, 11)]
STAGES = [
    ("quantitative_binding", "v05", "v01"), ("peng_glyph_binding", "v02", "v01"),
    ("peng_table_binding", "v01", "v01"), ("nambu_order_binding", "v02", "v01"),
    ("peng_best_ce", "v02", "v01"), ("kondo_descriptor", "v02", "v01"),
    ("nambu_identity", "v01", "v01"), ("kondo_potential_method", "v01", "v01"),
    ("nambu_cell_conditions", "v01", "v01"), ("peng_oxidation", "v01", "v02"),
    ("peng_surface", "v01", "v01"), ("kondo_solvation", "v01", "v01"),
    ("kondo_concentration_counterexample", "v01", "v01"), ("kondo_sei_sufficiency", "v03", "v01"),
    ("kondo_threshold_scope", "v02", "v01"), ("nambu_pure_concentration", "v01", "v01"),
    ("nambu_conductivity_explanation", "v02", "v01"), ("nambu_solubility_limit", "v01", "v01"),
]


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def app_paths():
    return [p for p in f.ROOT.joinpath("app").rglob("*") if p.is_file() and "__pycache__" not in p.parts]


def chain(output):
    from dataclasses import asdict

    from app.retrieval.search import SearchResult
    from app.retrieval.source_reference import rank_context

    output.mkdir(parents=True, exist_ok=False)
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    previous, stages, bindings, changes = {}, [], {}, []
    pools = {r["id"]: r["rows"] for r in read(POOLS / "cases.json")}
    expected_changes = {("peng_best_ce", "Peng_07"), ("kondo_potential_method", "Kondo_02"),
                        ("peng_surface", "Peng_10"), ("kondo_sei_sufficiency", "Kondo_09"),
                        ("kondo_threshold_scope", "Kondo_10")}
    for name, version, review_version in STAGES:
        base = f.ROOT / "output" / (name + "_20261111")
        comparison, reviewed = base / ("comparison_" + version), base / ("review_" + review_version)
        f.verify_manifest(comparison)
        f.verify_manifest(reviewed)
        result = read(comparison / "result.json")
        require([r["id"] for r in result["cases"]] == IDS, "Stage IDs/order changed")
        for row in result["cases"]:
            cid, path = row["id"], comparison / row["id"]
            before, after = read(path / "before.json"), read(path / "after.json")
            if previous:
                require(before == previous[cid], "Stage full-result continuity differs: " + name + "/" + cid)
            old_retrieval, new_retrieval = before["trace"]["retrieval"], after["trace"]["retrieval"]
            if new_retrieval != old_retrieval:
                require((name, cid) in expected_changes, "Undeclared stage retrieval transition: " + name + "/" + cid)
                api = read(path / "api_request.json")
                selected, metadata = rank_context(api["question"], [SearchResult(**r) for r in pools[cid]], top_k=api["top_k"])
                reconstructed = json.loads(json.dumps(old_retrieval))
                reconstructed["results"] = [asdict(r) for r in selected]
                reconstructed["metadata"]["explicit_source_reference"].update(metadata)
                require(new_retrieval == reconstructed and len(selected) == 5,
                        "Declared role retention cannot be reconstructed from original pool")
                changes.append({"stage": name, "id": cid, "original_pool_objects_exact": True,
                                "before_chunk_ids": [r["chunk_id"] for r in old_retrieval["results"]],
                                "after_chunk_ids": [r["chunk_id"] for r in new_retrieval["results"]]})
            if before["generation_reached"]:
                require(before == after, "Previously ready full result changed")
                require((path / "request_unsent.json").read_bytes() == (FINAL / cid / "request_unsent.json").read_bytes(),
                        "Previously ready native changed")
        previous = {r["id"]: read(comparison / r["id"] / "after.json") for r in result["cases"]}
        stages.append({"name": name, "comparison": str(comparison), "review": str(reviewed / "review.html"),
                       "before_ready": result["before_ready"], "after_ready": result["after_ready"]})
        bindings.update(f.bindings([comparison / "manifest.json", reviewed / "manifest.json"]))
    require({(r["stage"], r["id"]) for r in changes} == expected_changes, "Missing declared role-retention transition")
    f.write(output / "result.json", {"stages": stages, "stage_count": len(stages), "before_ready": 9, "after_ready": 30,
        "stage_full_results_checked": len(stages) * 30, "declared_retrieval_transitions": changes,
        "other_stage_retrieval_exact": True, "previous_ready_native_exact": True,
        "historical_current_source_bindings": "not all current: original historical app versions intentionally differ"})
    f.write(output / "bindings.json", bindings)
    f.manifest(output)


def audit(output):
    from app.generation import answer_facts, service
    from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError

    output.mkdir(parents=True, exist_ok=False)
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    current_bindings = f.bindings(app_paths())
    for folder in (FINAL, QUESTIONS, CAPTURE, POOLS):
        f.verify_manifest(folder)
    f.verify(read(FINAL / "bindings.json"))
    inputs = f.bindings([Path(__file__), PROTOCOL, *(p / "manifest.json" for p in (FINAL, QUESTIONS, CAPTURE, POOLS))])
    questions = read(QUESTIONS / "questions.json")["cases"]
    require([r["id"] for r in questions] == IDS, "Question set or order changed")
    chunks = read(CAPTURE / "chunks.json")
    for pool in read(POOLS / "cases.json"):
        for captured in pool["rows"]:
            source = {**captured, "text": captured["full_text"]}
            cid = source["chunk_id"]
            if cid in chunks:
                require(all(source[k] == chunks[cid][k] for k in
                            ("article_id", "chunk_id", "page_start", "page_end", "source_type", "text")),
                        "Original capture and complete pool disagree: " + cid)
            chunks[cid] = source
    articles = read(CAPTURE / "articles.json")
    pdfs = {}
    for article_id, article in articles.items():
        path = Path(article["pdf_path"])
        require(f.sha(path.read_bytes()) == article["pdf_sha256"], "Original PDF drift")
        with fitz.open(path) as doc:
            pdfs[article_id] = [page.get_text() for page in doc]
        inputs.update(f.bindings([path]))

    settings, rows = f.configure(), []
    for question in questions:
        cid, path = question["id"], FINAL / question["id"]
        f.verify_manifest(path)
        api, expected = read(path / "api_request.json"), read(path / "after.json")
        require(api["question"] == question["question"], "Original question changed: " + cid)
        current, native = replay.run_service(service, api, expected["trace"], settings)
        require(current == expected and native == (path / "request_unsent.json").read_bytes(),
                "Full preparation or native changed: " + cid)
        require(current["generation_reached"], "Preparation refused: " + cid)
        evidence = [Evidence(**e) for e in current["trace"]["evidence"]]
        records = answer_facts.selection_records(evidence)
        anchor_count, raw_evidence = 0, []
        for e in evidence:
            registered = chunks[e.chunk_id]
            require(all(getattr(e, k) == registered[k] for k in ("article_id", "chunk_id", "page_start", "page_end")),
                    "Registered source identity changed")
            raw = registered["text"]
            if e.source_type == "source_fact_derived":
                answer_facts.verify_raw_binding(e.text, raw, article_id=e.article_id, chunk_id=e.chunk_id,
                    citation_id=e.citation_id, page_start=e.page_start, page_end=e.page_end, source_type=registered["source_type"])
                raw_evidence.append(replace(e, text=raw, source_type=registered["source_type"]).__dict__)
            else:
                require(e.text == raw and e.source_type == registered["source_type"], "Raw selected evidence changed")
                raw_evidence.append(e.__dict__)
            # Check freshly extracted page text literally, preserving all glyphs.
            for number in range(e.page_start, e.page_end + 1):
                require(pdfs[e.article_id][number - 1].strip() in raw, "PDF page differs from raw chunk")
        for record in records.values():
            source = chunks[record["chunk_id"]]["text"]
            for fact in record["facts"]:
                require(fact["scientific_ownership_verified"] is False, "Scientific ownership asserted")
                values = (fact["sample"], fact["value"], fact["unit"], fact["method"], *fact["conditions"].values())
                for anchor in (fact["support"], *(v["source"] for v in values if v)):
                    require(source[anchor["start"]:anchor["end"]] == anchor["text"]
                            and f.sha(source.encode()) == anchor["raw_chunk_sha256"], "Fact raw anchor differs")
                    anchor_count += 1
        controls = None
        if records:
            selected = quant.synthetic(service, api, current["trace"]["retrieval"], "select", settings)
            abstained = quant.synthetic(service, api, current["trace"]["retrieval"], "abstain", settings)
            require(selected["status"] == "answered" and abstained["status"] == "insufficient_evidence",
                    "Synthetic select/abstain boundary changed")
            try:
                quant.synthetic(service, api, current["trace"]["retrieval"], "invalid", settings)
            except GenerationOutputError:
                pass
            else:
                raise ValueError("Synthetic prose admitted")
            try:
                answer_facts.resolve_selections([GeneratedClaim(key, ["E999"]) for key in records], evidence)
            except GenerationOutputError:
                pass
            else:
                raise ValueError("Wrong citation admitted")
            controls = {"execution": "SYNTHETIC, not real model answers", "selection": selected,
                        "abstention": abstained, "invalid_prose_rejected": True, "wrong_citation_rejected": True}
        row = {"id": cid, "question": api["question"], "article_id": question["article_id"],
            "ready_unsent": True, "full_result_exact": True, "native_exact": True,
            "native_bytes": len(native), "native_sha256": f.sha(native), "raw_anchors": anchor_count,
            "fact_records": records, "raw_evidence": raw_evidence, "synthetic_controls": controls,
            "scientific_accuracy": None, "independent_evaluation": False}
        rows.append(row)
        folder = output / cid
        folder.mkdir()
        f.write(folder / "result.json", row)
        f.write(folder / "preparation.json", current)
        f.save(folder / "request_unsent.json", native)
        print(cid + " exact", flush=True)

    operations = []
    for catalogue in sorted(f.ROOT.joinpath("app/resources").glob("reviewed*glyph*.json")):
        data = read(catalogue)
        article_id = next(a for a, value in articles.items() if value["pdf_sha256"] == data["pdf_sha256"])
        with fitz.open(articles[article_id]["pdf_path"]) as doc:
            for entry in data["entries"]:
                registered = chunks[entry["chunk_id"]]
                raw = registered["text"]
                require(entry["raw_sha256"] == f.sha(raw.encode()) and entry["article_id"] == article_id,
                        "Catalogue raw SHA/identity differs")
                require(all(entry[k] == registered[k] for k in ("article_id", "page_start", "page_end", "source_type")),
                        "Catalogue registered identity differs")
                for op in entry["operations"]:
                    page = doc[op["pdf_page"] - 1]
                    text = page.get_text()
                    require(text.strip() in raw and text[op["pdf_text_offset"]] == op["raw_character"]
                        and raw[op["raw_start"]:op["raw_end"]] == op["raw_character"]
                        and raw.index(text.strip()) + op["pdf_text_offset"] - (len(text) - len(text.lstrip())) == op["raw_start"]
                        and f.sha(doc.extract_font(op["font_xref"])[3]) == op["font_program_sha256"],
                        "Catalogue PDF offset/font binding differs")
                    found = [char for block in page.get_text("rawdict")["blocks"] for line in block.get("lines", [])
                        for span in line["spans"] for char in span["chars"] if span["font"] == op["font"]
                        and char["c"] == op["raw_character"] and list(char["bbox"]) == op["bbox"]]
                    require(len(found) == 1, "Catalogue glyph bbox ambiguous")
                    operations.append({"catalogue": catalogue.name, "chunk_id": entry["chunk_id"], **op})
    f.verify(current_bindings)
    f.verify(inputs)
    summary = {"cases": len(rows), "ready_unsent": len(rows), "exact_full_results": len(rows), "exact_native": len(rows),
        "source_fact_cases": sum(bool(r["fact_records"]) for r in rows), "raw_anchors": sum(r["raw_anchors"] for r in rows),
        "facts": sum(len(v["facts"]) for r in rows for v in r["fact_records"].values()),
        "catalogues": len({r["catalogue"] for r in operations}), "glyph_operations": len(operations),
        "original_PDFs": len(articles), "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0,
        "DB_queries": 0, "new_visual_PDF_review": False, "scientific_accuracy": None}
    f.write(output / "result.json", {"summary": summary, "cases": rows, "glyph_operations": operations, "articles": articles})
    f.write(output / "bindings.json", {**current_bindings, **inputs})
    f.manifest(output)
    print(json.dumps(summary), flush=True)


def wheel(output):
    output.mkdir(parents=True, exist_ok=False)
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    original = f.bindings(app_paths())
    source = output / "source"
    source.mkdir()
    for name in ("app", "scripts"):
        shutil.copytree(f.ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(f.ROOT / "pyproject.toml", source / "pyproject.toml")
    wheels = output / "wheels"
    command = [sys.executable, "-X", "utf8", "-B", "-m", "pip", "wheel", ".", "--no-deps",
               "--no-build-isolation", "--no-index", "--wheel-dir", str(wheels)]
    done = subprocess.run(command, cwd=source, capture_output=True)
    f.save(output / "build.stdout", done.stdout)
    f.save(output / "build.stderr", done.stderr)
    f.write(output / "build_result.json", {"command": command, "exit_code": done.returncode})
    require(done.returncode == 0, "Offline wheel build failed; inspect preserved stderr")
    candidates = list(wheels.glob("*.whl"))
    require(len(candidates) == 1, "Nonunique wheel")
    installed = output / "installed"
    with zipfile.ZipFile(candidates[0]) as archive:
        archive.extractall(installed)
        members = set(archive.namelist())
    checked = []
    for name, digest in original.items():
        relative = Path(name).relative_to(f.ROOT)
        require(relative.as_posix() in members, "Missing wheel member: " + str(relative))
        require(f.sha((installed / relative).read_bytes()) == digest, "Wheel member differs: " + str(relative))
        checked.append(relative.as_posix())
    env = {**os.environ, "PYTHONPATH": str(installed), "PYTHONDONTWRITEBYTECODE": "1",
           "GIGACHAT_CREDENTIALS": "offline-placeholder-no-transport"}
    driver = ("import runpy,sys; from pathlib import Path; sys.path.insert(0,sys.argv.pop(1)); "
              "from scripts import gigachat_answer_smoke as f; f.ROOT=Path(sys.argv.pop(1)); "
              "runpy.run_module('scripts.audit_answer_series_20261111',run_name='__main__')")
    command = [sys.executable, "-X", "utf8", "-B", "-c", driver, str(installed), str(f.ROOT), "replay",
               "--output", str(output / "replay_v01"), "--expected-app", str(installed / "app")]
    done = subprocess.run(command, cwd=output, env=env, capture_output=True)
    f.save(output / "replay.stdout", done.stdout)
    f.save(output / "replay.stderr", done.stderr)
    require(done.returncode == 0, "Installed wheel replay failed; inspect preserved stderr")
    f.verify(original)
    f.write(output / "result.json", {"wheel": str(candidates[0]), "sha256": f.sha(candidates[0].read_bytes()),
        "package_files_exact": len(checked), "members": checked,
        "installed_app_replay": read(output / "replay_v01/result.json")["summary"]})
    f.manifest(output)


def report(output):
    output.mkdir(parents=True, exist_ok=False)
    audited = BASE / "replay_v04"
    for path in (audited, BASE / "wheel_v03", BASE / "regression_v01", BASE / "chain_v02"):
        f.verify_manifest(path)
    data = read(audited / "result.json")
    suites = list(ET.parse(BASE / "full_suite_v02.xml").getroot().iter("testsuite"))
    counts = {k: sum(int(s.get(k, "0")) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    require(counts["failures"] == counts["errors"] == 0, "Full test suite not clean")
    quality = read(BASE / "quality_v02.json")
    require(all(quality[key]["exit_code"] == 0 for key in
                ("mypy_app", "ruff_application_tests_new_auditor", "full_pytest")),
            "Scoped quality checks not clean")
    require(quality["ruff_repository"]["diagnostics"] == read(BASE / "ruff_v01.json"),
            "Repository Ruff findings changed")
    history = read(BASE / "regression_v01/summary.json")
    require(history["actual_service_executions"] == 81 and all(r["full_service_identical"] for r in history["regressions"])
            and all(r["full_service_identical"] and r["native_identical"] for r in history["current_comparisons"]),
            "Historical regression differs")
    links = []

    def link(path, label, fragment=""):
        require(path.is_file(), "Missing review link: " + str(path))
        links.append(str(path))
        href = os.path.relpath(path, output).replace("\\", "/") + fragment
        return '<a href="' + html.escape(href, quote=True) + '">' + html.escape(label) + '</a>'

    rows = []
    for row in data["cases"]:
        detail = {k: row[k] for k in ("native_bytes", "native_sha256", "raw_anchors", "fact_records", "raw_evidence")}
        selection = row["synthetic_controls"]
        rendered = (selection["selection"]["answer"] if selection else
                    "Прежний путь: серверный ответ до реального выбора модели не установлен.")
        citations = [link(Path(data["articles"][e["article_id"]]["pdf_path"]),
                          f'{e["title"] or "Источник"}, PDF {e["page_start"]}–{e["page_end"]}',
                          f'#page={e["page_start"]}') for e in row["raw_evidence"]]
        cells = [row["id"], row["question"], "Готов, не отправлен", "Факты" if selection else "Прежний путь"]
        rows.append('<tr>' + ''.join('<td>' + html.escape(c) + '</td>' for c in cells)
            + '<td>' + ' · '.join(citations) + '<details><summary>Источник, условия и диагностика</summary><p>'
            + html.escape(rendered) + '</p><p>Серверный текст показан после SYNTHETIC F1; это не ответ модели.</p><pre>'
            + html.escape(json.dumps(detail, ensure_ascii=False, indent=2)) + '</pre></details></td></tr>')
    papers = []
    for a in data["articles"].values():
        cells = [str(a.get(k) or "Не собрано / отсутствует в snapshot") for k in
                 ("title", "authors", "journal", "year", "abstract", "conclusions", "terms")]
        papers.append('<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in cells)
                      + '<td>' + link(Path(a["pdf_path"]), "Исходный PDF") + '</td></tr>')
    summary = {**data["summary"], "pytest": counts, "historical_service_exact": 81, "historical_native_exact": 5,
               "quality": quality, "wheel": read(BASE / "wheel_v03/result.json"),
               "stage_chain": read(BASE / "chain_v02/result.json"), "plan_percent": 75}
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — сводный офлайн-аудит</title>'
        '<style>body{font:16px system-ui;margin:30px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #bdcbd0;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'details{max-width:75vw}input{padding:10px;width:65%;margin:15px 0}</style>'
        '<h1>ARIADNE: сводный офлайн-аудит, 11 ноября 2026</h1>'
        '<p>30/30 подготовленных входов; 21 случай с source-bound facts, 9 по прежнему пути. '
        'Все вопросы открыты разработке. Это проверка воспроизводимости и границ контрактов, '
        'не независимая научная оценка. Реальных model/OAuth/new slots: 0. План качества: 75%.</p>'
        '<p>Свежий поиск/DB, визуальная приёмка PDF, поведение реальной модели, браузер и deployment '
        'не проверялись. Историческая визуальная интерпретация glyph не заменена новой. '
        'Сохранены unknown fields, модальность и scientific_ownership_verified=false.</p><p>'
        '<p>За серию в пяти объявленных случаях изменился состав top-5 за счёт удержания ролей '
        'из исходного полного пула. Размер top-5 и исходные scores сохранены. Это не тождество '
        'выбранных фрагментов за весь день. Два прежних Ruff E501 в историческом диагностическом '
        'скрипте сохранены и показаны в итогах; application/tests/new auditor проходят Ruff.</p><p>'
        + ' · '.join([link(BASE / "full_suite_v02.xml", "Полный pytest"), link(audited / "result.json", "Raw audit JSON"),
                       link(BASE / "regression_v01/summary.json", "81 исторический сценарий"),
                       link(Path(summary["wheel"]["wheel"]), "Проверенное wheel")])
        + '</p><details><summary>Итог проверок</summary><pre>' + html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
        + '</pre></details><h2>Все 30 вопросов</h2><label>Поиск <input id="search" type="search"></label>'
        '<table id="cases"><thead><tr><th>ID</th><th>Вопрос</th><th>Статус</th><th>Путь</th><th>Источники и факты</th>'
        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table><h2>Все три статьи: TAC metadata snapshot</h2>'
        '<p>Недостающие поля не восстанавливались из названий файлов или предположений.</p><table><thead><tr>'
        + ''.join('<th>' + k + '</th>' for k in
                  ("Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file"))
        + '</tr></thead><tbody>' + ''.join(papers) + '</tbody></table><script>'
        'document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();'
        'document.querySelectorAll("#cases tbody tr").forEach(r=>r.hidden=!r.textContent.toLocaleLowerCase().includes(q));});'
        '</script></html>')
    f.save(output / "review.html", body.encode())
    f.write(output / "report.json", {**summary, "HTML_rows": len(rows), "article_rows": len(papers), "local_links": len(links)})
    f.write(output / "bindings.json", f.bindings([Path(__file__), PROTOCOL, BASE / "full_suite_v02.xml", BASE / "quality_v02.json",
        *(BASE / p / "manifest.json" for p in ("replay_v04", "wheel_v03", "regression_v01", "chain_v02"))]))
    f.manifest(output)


def freeze(output):
    output.mkdir(parents=True, exist_ok=False)
    paths = [*app_paths(), f.ROOT / "pyproject.toml", PROTOCOL, Path(__file__)]
    paths += [p for parent in ("scripts", "tests", "docs") for p in f.ROOT.joinpath(parent).rglob("*")
              if p.is_file() and "__pycache__" not in p.parts]
    bindings = f.bindings(paths)
    for name in bindings:
        source = Path(name)
        target = output / "source_snapshot" / source.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, source.read_bytes())
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    content = {"bindings": bindings, "packages": packages, "python": sys.version,
               "protocol_sha256": f.sha(PROTOCOL.read_bytes()), "real_model_calls": 0,
               "scientific_accuracy": None, "plan_percent": 75}
    f.write(output / "version.json", {**content, "freeze_id": f.sha(f.encode(content))})
    f.write(output / "bindings.json", bindings)
    f.verify(bindings)
    f.manifest(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("replay", "wheel", "report", "freeze", "chain"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-app", type=Path)
    args = parser.parse_args()
    if args.expected_app:
        import app
        require(Path(app.__file__).resolve().parent == args.expected_app.resolve(), "Wheel application import escaped installation")
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
    {"replay": audit, "wheel": wheel, "report": report, "freeze": freeze, "chain": chain}[args.mode](args.output.resolve())
    require(not policy.denied, "Unexpected external network attempt")


if __name__ == "__main__":
    main()
