"""Export canonical review capsules and readable UI over declared diagnostic assertions."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

from app.generation.answer_evidence_packet import build_packet, serialize_packet
from app.generation.answer_requirements import build_requirements
from app.generation.claim_review import VERSION, build_review, render_catalog, render_review, validate_review
from scripts import gigachat_answer_smoke as files
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.claim_review_ui_baseline_20261110 import BASE, PROTOCOL
from scripts.review_answer_evidence_packet_20261109 import independent_digest
from scripts.review_answer_requirements_20261109 import local_links
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail
from scripts.review_claim_checks_20261110 import assertions, independent_report_check


def run(output: Path, comparison: Path, junit: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    (output / "capsules").mkdir()
    prior_folder = files.ROOT / "output/claim_checks_20261110/review_v01"
    for folder in (BASE / "freeze_v01", comparison, prior_folder, BASE / "browser_probe_v02"):
        files.verify_manifest(folder)
    scope = read(junit.with_suffix(".scope.json"))
    files.verify(scope["test_bindings"])
    files.verify(scope["app_bindings"])
    counts = {k: sum(int(s.get(k, 0)) for s in ET.parse(junit).getroot().iter("testsuite"))
              for k in ("tests", "failures", "errors", "skipped")}
    if scope["exit_code"] or scope["external_network_denials"] or counts["failures"] or counts["errors"]:
        raise ValueError("Affected UI test scope failed")
    before = read(BASE / "freeze_v01/bindings.json")
    old_app = {k: v for k, v in before.items() if Path(k).is_relative_to(files.ROOT / "app")}
    drift = {Path(k).relative_to(files.ROOT).as_posix(): {"before": v, "after": files.sha(Path(k).read_bytes())}
             for k, v in old_app.items() if files.sha(Path(k).read_bytes()) != v}
    if set(drift) != {"app/main.py", "app/generation/preparation_routes.py"}:
        raise ValueError("Unexpected old app drift outside router/navigation")
    new = {str(p.resolve()) for p in files.ROOT.joinpath("app").rglob("*.py")} - set(old_app)
    if new != {str((files.ROOT / p).resolve()) for p in
               ("app/generation/claim_review.py", "app/generation/claim_review_routes.py")}:
        raise ValueError("Unexpected new app files")
    prior = read(prior_folder / "report.json")
    articles = prior["articles"]
    pdfs = [Path(a["original_pdf_path"]) for a in articles.values()]
    for article, path in zip(articles.values(), pdfs, strict=True):
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF hash changed")
    controls = read(files.ROOT / "output/answer_requirements_20261109/controls_v01.json")
    outcomes, fragments, link_inventory, renderer_comparisons = [], [], [], []
    events, claim_count = 0, 0
    for i, case in enumerate(controls):
        preparation = copy.deepcopy(case["parent"])
        parent = {"version": "answer_requirements_preparation_v0.1", "preparation": preparation,
            "requirements": build_requirements(preparation), "generation_performed": False,
            "external_request_constructed": False, "network_ready": False}
        packet = build_packet(parent)
        claims = assertions(packet)
        capsule = build_review(packet, claims, expected_packet_id=packet["packet_id"])
        validate_review(capsule, packet, claims, expected_packet_id=packet["packet_id"], expected_review_id=capsule["review_id"])
        if independent_digest({k: v for k, v in capsule.items() if k != "review_id"}) != capsule["review_id"]:
            raise ValueError("Independent review capsule identity check failed")
        events += independent_report_check(capsule["report"], packet)
        claim_count += len(claims)
        path = output / "capsules" / f"review_{i:03}.json"
        files.save(path, serialize_packet(capsule))
        restored = read(path)
        validate_review(restored, packet, claims, expected_packet_id=packet["packet_id"], expected_review_id=capsule["review_id"])
        if serialize_packet(restored) != path.read_bytes():
            raise ValueError("Canonical review export roundtrip differs")
        catalog = render_catalog(packet)
        fragment = render_review(capsule, packet, expected_review_id=capsule["review_id"])
        if render_review(restored, packet, expected_review_id=capsule["review_id"]) != fragment:
            raise ValueError("Canonical capsule roundtrip changed rendered UI")
        if render_catalog(read(output / "capsules" / f"review_{i:03}.json")["packet"]) != catalog:
            raise ValueError("Canonical packet roundtrip changed rendered catalog")
        previous_path = BASE / "review_v01/capsules" / f"review_{i:03}.json"
        if output.name != "review_v01" and previous_path.exists():
            previous = read(previous_path)
            if serialize_packet(previous["report"]) != serialize_packet(capsule["report"]):
                raise ValueError("Renderer-only fix changed the diagnostic report")
            renderer_comparisons.append({"id": case["id"], "packet_id_unchanged": previous["packet"]["packet_id"] == packet["packet_id"],
                "report_bytes_unchanged": True, "before_review_id": previous["review_id"], "after_review_id": capsule["review_id"]})
        files.save(output / f"catalog_{i:03}.html", catalog.encode())
        files.save(output / f"runtime_UI_{i:03}.html", fragment.encode())
        local, links = local_links(fragment, articles)
        if fragment.count("data-claim-card") != len(claims):
            raise ValueError("Rendered claim card inventory differs")
        fragments.append('<div data-review-case><h3>' + escape(case["id"]) + " · " + escape(case["origin"]) + "</h3>"
            + "<p>Явные assertions — constructed development controls, не ответы модели или независимые эталоны.</p>" + local + "</div>")
        link_inventory.append({"id": case["id"], "links": links})
        outcomes.append({"id": case["id"], "origin": case["origin"], "claims": len(claims), "review_id": capsule["review_id"],
                         "packet_id": packet["packet_id"], "report_id": capsule["report"]["report_id"]})
        if i == 0:
            real_packet = packet
        print(json.dumps({"control": i + 1, "cards": len(claims)}), flush=True)
    source_folder = files.ROOT / "output/bounded_context_action_20261110/review_v01"
    files.verify_manifest(source_folder)
    anchors = read(source_folder / "report.json")["source_matches"]
    for item in anchors:
        data = item["anchor"]
        source = next(s for s in real_packet["content"]["sources"] if s["chunk_id"] == data["chunk_id"])
        if (source["raw_text"][data["start"]:data["end"]] != data["text"]
                or files.sha(source["raw_text"].encode()) != data["raw_chunk_sha256"]):
            raise ValueError("Prior raw/PDF binding differs from current UI source")
    browser = read(BASE / "browser_probe_v02/result.json")
    if browser["external_network_denials"] or not browser["synthetic_preparation"]:
        raise ValueError("Browser preview escaped declared synthetic scope")
    browser_observation = {"surface": "new_HTTP_UI_not_archived_file_URL", "synthetic_preparation": True,
        "observed": ["GET form", "prepare catalog", "explicit wrong-cell check", "four separate statuses",
            "preserved page-registry blocker", "field mismatch", "assertion and exact quote side by side",
            "full-width question after CSS correction", "registered source-range link"],
        "viewport": "desktop only; responsive/mobile not visually verified", "PDF_links_clicked": False,
        "archived_file_URL_review_layout": "not_retested_prior_policy_block",
        "evidence": "CUA accessibility and screenshot observations in this chat; helper requests in browser_probe_v02",
        "renderer_visual_scope": "Before the final deterministic-render-only fix; source preserved in pre_render_roundtrip_fix_v01",
        "subsequent_change": "Fixed field order and sorted technical JSON; visible workflow not re-opened in browser afterward",
        "server_stopped": True, "preview_summary": browser}
    summary = {"version": VERSION, "tests": counts, "external_network_denials": scope["external_network_denials"],
        "canonical_capsules": len(outcomes), "claim_cards": claim_count, "catalogs": len(outcomes),
        "independently_checked_events": events, "old_app_drift": drift, "new_modules": sorted(new),
        "renderer_roundtrip_fix_comparisons": renderer_comparisons,
        "final_service_comparison": read(comparison / "summary.json"), "original_PDF_hashes": len(pdfs),
        "prior_raw_PDF_bindings_rechecked": len(anchors), "fresh_PDF_extraction": False,
        "browser_observation": browser_observation, "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0,
        "fresh_DB_preparation": False, "independent_scientific_accuracy": None,
        "limitations": ["Explicit structured assertion inputs; no free-answer prose extraction",
            "No scientific acceptance/human decisions or stored revisions",
            "No real DB preparation or production PDF navigation in browser",
            "One desktop synthetic mismatch visually inspected; other controls static/API tests",
            "Current trusted packet/code required; old snapshots preserved without migration"]}
    report = {"summary": summary, "cases": copy.deepcopy(prior["cases"]), "articles": articles,
        "regressions": read(comparison / "summary.json")["regressions"], "controls": outcomes}
    document = render(report).replace("Сохранение запрошенного контекста в runtime", "Просмотр утверждений рядом с evidence")
    document = document.replace("<p>Офлайн-сравнение реального service на замороженных", "<p>Архивные пять секций контекста. "
        "Новый UI расположен перед TAC. Офлайн-сравнение service на замороженных")
    extra = ("<h2>Явный интерфейс утверждений и источников</h2><p>Это сохранённые runtime fragments нового renderer. "
        "Записи assertions constructed; научная достоверность не оценена, исходный admission сохранён. "
        "HTTP UI проверен отдельно на synthetic preparation; этот архивный HTML в браузере не открывался.</p>"
        + detail("Фактическая browser-проверка и ограничения", browser_observation) + "".join(fragments))
    document = document.replace("<h2>TAC:", extra + "<h2>TAC:")
    qa = check_html(document, article_count=len(articles), case_count=5)
    if document.count("data-review-case") != len(outcomes) or document.count("data-claim-card") != claim_count:
        raise ValueError("Static review case/card inventory differs")
    qa.update(review_cases=len(outcomes), claim_cards=claim_count, HTTP_desktop_mismatch_visually_checked=True,
              archived_HTML_browser_layout_verified=False)
    paths = [*files.ROOT.joinpath("app").rglob("*.py"), Path(__file__), PROTOCOL, junit, junit.with_suffix(".scope.json"),
        files.ROOT / "output/answer_requirements_20261109/controls_v01.json", BASE / "browser_probe_v02/manifest.json",
        prior_folder / "manifest.json", source_folder / "manifest.json", *pdfs,
        *[files.ROOT / p for p in ("scripts/claim_review_ui_baseline_20261110.py", "scripts/test_claim_review_ui_20261110.py",
            "scripts/preview_claim_review_ui_20261110.py", "tests/unit/test_claim_review_ui.py")]]
    report["bindings"] = files.bindings(paths)
    files.verify(report["bindings"])
    files.write(output / "report.json", report)
    files.write(output / "qa.json", qa)
    files.write(output / "links.json", link_inventory)
    files.save(output / "review.html", document.encode())
    return {k: v for k, v in summary.items() if k not in {"final_service_comparison", "browser_observation"}}


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
