"""Export/reload diagnostic packets and independently inspect journal/source hashes."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

import fitz

from app.generation.answer_evidence_packet import build_packet, load_packet, save_packet, serialize_packet
from app.generation.answer_requirements import build_requirements
from app.generation.evidence_packet_routes import render_packet
from scripts import gigachat_answer_smoke as files
from scripts.answer_evidence_packet_20261109 import BASE, PROTOCOL
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE
from scripts.review_answer_requirements_20261109 import local_links
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail


def independent_digest(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return files.sha(raw)


def check_chain(packet: dict) -> int:
    previous = None
    for i, event in enumerate(packet["journal"]["events"], 1):
        data = {k: v for k, v in event.items() if k != "event_hash"}
        if (event["sequence"] != i or event["previous_hash"] != previous or independent_digest(data) != event["event_hash"]
                or event["actor_kind"] != "deterministic_system" or event["action_executed"] is not False):
            raise ValueError("Independent journal sequence/hash/actor check failed")
        previous = event["event_hash"]
    if previous != packet["journal"]["root_hash"]:
        raise ValueError("Independent journal root check failed")
    core = {k: packet[k] for k in ("version", "content", "journal")}
    if independent_digest(core) != packet["packet_id"]:
        raise ValueError("Independent packet digest differs")
    return len(packet["journal"]["events"])


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    (output / "packets").mkdir()
    for path in (BASE / "freeze_v01", comparison):
        files.verify_manifest(path)
    scope = read(junit.with_suffix(".scope.json"))
    files.verify(scope["test_bindings"])
    files.verify(scope["app_bindings"])
    suites = list(ET.parse(junit).getroot().iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "errors", "failures", "skipped")}
    if scope["exit_code"] or scope["external_network_denials"] or counts["errors"] or counts["failures"]:
        raise ValueError("Packet test scope failed")
    initial = read(BASE / "freeze_v01/bindings.json")
    drift = [{"path": name, "before": digest, "after": files.sha(Path(name).read_bytes())}
             for name, digest in initial.items() if Path(name).is_relative_to(files.ROOT / "app")
             and files.sha(Path(name).read_bytes()) != digest]
    if {Path(d["path"]).relative_to(files.ROOT).as_posix() for d in drift} != {
            "app/main.py", "app/generation/preparation_routes.py"}:
        raise ValueError("Unexpected old app drift")
    new = {str(p.resolve()) for p in (files.ROOT / "app").rglob("*.py")} - set(initial)
    if new != {str((files.ROOT / p).resolve()) for p in
               ("app/generation/answer_evidence_packet.py", "app/generation/evidence_packet_routes.py")}:
        raise ValueError("Unexpected new app modules")
    controls = read(files.ROOT / "output/answer_requirements_20261109/controls_v01.json")
    packets, outcomes, total_events = [], [], 0
    for i, case in enumerate(controls):
        p = copy.deepcopy(case["parent"])
        parent = {"version": "answer_requirements_preparation_v0.1", "preparation": p,
                  "requirements": build_requirements(p), "generation_performed": False,
                  "external_request_constructed": False, "network_ready": False}
        before = copy.deepcopy(parent)
        packet = build_packet(parent)
        path = output / f"packets/{i:03}.json"
        save_packet(path, packet, parent)
        loaded = load_packet(path, parent, expected_packet_id=packet["packet_id"])
        if loaded != packet or serialize_packet(build_packet(parent)) != path.read_bytes() or parent != before:
            raise ValueError("Packet export/replay or unchanged parent differs")
        digest_before = files.sha(path.read_bytes())
        try:
            save_packet(path, packet, parent)
        except FileExistsError:
            pass
        else:
            raise ValueError("Existing packet was overwritten")
        if files.sha(path.read_bytes()) != digest_before:
            raise ValueError("Rejected overwrite changed snapshot")
        total_events += check_chain(packet)
        packets.append(packet)
        content = packet["content"]
        outcomes.append({"id": case["id"], "origin": case["origin"], "packet_id": packet["packet_id"],
            "file": str(path), "bytes": len(path.read_bytes()), "parent_unchanged": True,
            "sources": len(content["sources"]), "anchors": len(content["anchors"]), "facts": len(content["facts"]),
            "transformations": len(content["transformations"]), "journal_events": len(packet["journal"]["events"]),
            "page_registry_entries": len(content["pages"]), "baseline_blockers": content["stop"]["baseline_blocking_reasons"]})
    files.write(output / "packet_outcomes.json", outcomes)
    articles, corpus = read(CORPUS_BASE / "Q01/articles.json"), read(CORPUS_BASE / "Q01/corpus.json")
    pdfs = []
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        pdfs.append(path)
    real = packets[0]
    fresh = {}
    for source in real["content"]["sources"]:
        registered = corpus[source["chunk_id"]]
        if source["raw_text"] != registered["full_text"] or source["source_type"] != registered["source_type"]:
            raise ValueError("Packet selected raw source differs from frozen corpus")
        with fitz.open(articles[source["article_id"]]["original_pdf_path"]) as pdf:
            for n in range(source["page_start"], source["page_end"] + 1):
                fresh[(source["article_id"], n)] = pdf[n - 1].get_text()
                pdf[n - 1].get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(str(output / f"page_{n:02}.png"))
    matches, by_source = [], {s["id"]: s for s in real["content"]["sources"]}
    for item in real["content"]["anchors"]:
        anchor, source = item["anchor"], by_source[item["source_ref"]]
        found = [n for (a, n), text in fresh.items() if a == anchor["article_id"]
                 and anchor["page_start"] <= n <= anchor["page_end"] and anchor["text"] in text]
        if (source["raw_text"][anchor["start"]:anchor["end"]] != anchor["text"]
                or files.sha(source["raw_text"].encode()) != anchor["raw_chunk_sha256"] or not found):
            raise ValueError("Packet raw anchor absent from fresh declared PDF page")
        matches.append({"anchor_id": item["id"], "anchor": anchor, "fresh_PDF_pages": found,
                        "packet_page_binding_retained": item["page_binding"]})
    ui, links = [], []
    for i, (packet, case) in enumerate(zip(packets, controls, strict=True)):
        fragment = render_packet(packet)
        files.save(output / f"runtime_UI_{i:03}.html", fragment.encode())
        local, mapped_links = local_links(fragment, articles)
        links.append({"id": case["id"], "links": mapped_links})
        ui.append('<div data-packet-case="' + escape(case["id"], quote=True) + '"><h2>' + escape(case["id"])
            + " — synthetic preparation</h2>" + local + "</div>")
    document = ("<!doctype html><html lang='ru'><meta charset='utf-8'><title>ARIADNE — пакет и журнал</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:1150px;margin:25px auto;padding:0 20px;color:#183044}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}"
        "td,th{padding:8px;border:1px solid #abc}details{margin:8px 0}summary{cursor:pointer}</style><body>"
        "<h1>Пакет доказательств и журнал наблюдений</h1><p>Подготовки здесь SYNTHETIC; первый случай содержит "
        "неизменные реальные raw тексты Lin2020. Новых ответов модели нет. PDF page registry в этих минимальных "
        "подготовках отсутствует; свежая проверка PDF выполнена отдельно и не переписала пакеты.</p>"
        + "".join(ui) + "</body></html>")
    if document.count("data-packet-case=") != len(controls) or document.count("data-packet-event=") != total_events:
        raise ValueError("Packet/journal UI inventory differs")
    files.save(output / "packet_UI.html", document.encode())
    files.write(output / "UI_links.json", links)
    summary = {"version": real["version"], "tests": counts, "external_network_denials": scope["external_network_denials"],
        "exported_packets": len(packets), "independently_checked_journal_events": total_events,
        "canonical_roundtrip_and_rejected_overwrite": len(packets), "real_raw_packet": outcomes[0],
        "code_binding_count": len(real["content"]["versions"]["code_bindings"]),
        "final_frozen_comparison": read(comparison / "service/summary.json"), "runtime_drift": drift, "new_modules": sorted(new),
        "unique_raw_anchors_checked": len(matches), "anchor_observations": real["content"]["inspection"]["anchor_observations"],
        "corpus_PDF_hashes": len(pdfs), "fresh_pages": [{"article_id": a, "page": n, "sha256": files.sha(text.encode())}
            for (a, n), text in fresh.items()], "real_model_calls": 0, "real_oauth_exchanges": 0,
        "new_slots": 0, "fresh_DB_preparation": False, "independent_scientific_accuracy": None,
        "browser_layout": "not_verified_prior_file_URL_policy_block",
        "limitations": ["System observation journal is not a retrieval execution history or human review",
            "Integrity/replay depends on trusted current parent and fixed declared code bindings, not authenticity",
            "Missing page registry remains unproven; package builder does not read embedded PDF paths",
            "One finite family and exposed/synthetic sources, no scientific quality/refusal gain measured"]}
    previous = read(files.ROOT / "output/answer_requirements_20261109/review_v01/report.json")
    report = {"summary": summary, "cases": copy.deepcopy(previous["cases"]), "articles": articles,
        "regressions": summary["final_frozen_comparison"]["regressions"], "packets": outcomes, "source_matches": matches}
    html = render(report).replace("Сохранение запрошенного контекста в runtime", "Пакет доказательств и диагностический журнал")
    extra = ("<h2>Пакеты и воспроизведение</h2>" + detail("27 отдельных canonical JSON snapshots", outcomes)
        + "<p>Журнал фиксирует диагностические наблюдения системы; исходные blockers не меняются. "
          "Проверка свежих PDF ниже — внешняя проверка экспорта, не новое поле научного допуска в пакете.</p>"
        + "<iframe src='packet_UI.html' title='Diagnostic packet UI' style='width:100%;height:1100px;border:1px solid #abc'></iframe>"
        + detail("Exact raw/PDF bindings", matches))
    for n in (1, 3, 7):
        extra += (f"<details><summary>Свежий PDF-рендер {n}</summary>"
                  f"<img src='page_{n:02}.png' style='max-width:100%' alt='PDF {n}'></details>")
    html = html.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(html, article_count=len(articles), case_count=5)
    qa.update(packet_cases=len(packets), journal_events=total_events, original_parent_unchanged=True)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL,
        files.ROOT / "tests/unit/test_answer_evidence_packet.py", files.ROOT / "scripts/answer_evidence_packet_20261109.py",
        files.ROOT / "scripts/test_answer_evidence_packet_20261109.py", junit, junit.with_suffix(".scope.json"), *pdfs]
    report["bindings"] = files.bindings(paths)
    files.verify(report["bindings"])
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.save(output / "review.html", html.encode())
    return {k: v for k, v in summary.items() if k not in {"final_frozen_comparison", "runtime_drift", "new_modules"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.output, args.comparison, args.junit)
    files.write(args.output / "network.json", {"external_denials": policy.denied})
    if policy.denied:
        raise ValueError("External network attempted")
    files.manifest(args.output)
    print(json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
