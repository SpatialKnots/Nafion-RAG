"""Frozen-channel service checks and SYNTHETIC HTTP controls; never live generation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import fitz

from app.generation.answer_fidelity import prepare
from app.generation.providers import Evidence
from scripts import benchmark_retrieval_replay_20261105 as engine
from scripts import gigachat_answer_smoke as files
from scripts.ascii_quote_selection_checks_20261105 import evaluated_evidence
from scripts.benchmark_retrieval_capture_20261105 import read
from scripts.check_requested_context_runtime_20261105 import render
from scripts.reference_quote_runtime_checks_20261105 import CORPUS_BASE, INTAKE, OLD, inventory_scope
from scripts.review_benchmark_retrieval_repair_20261105 import check_html, detail, presence
from scripts.review_retrieval_ablation import unpack

ROOT = files.ROOT
BASE = ROOT / "output/answer_fidelity_20261105"
PREVIOUS = ROOT / "output/user_benchmark_retest_20261105"
PROTOCOL = ROOT / "docs/records/answer_fidelity_protocol_2026-11-05_v0.1.md"


def client(settings):
    from app.generation.gigachat import GigaChatAnswerProvider
    return GigaChatAnswerProvider(credentials="offline-placeholder", scope=settings.gigachat_scope,
                                 model=settings.rag_model, timeout_seconds=120, max_tokens=1200)


def native(case_id, trace, settings, output):
    body, calls = [], []
    provider = client(settings)

    def post(url, raw, authorization, *, oauth=False):
        calls.append("fake_oauth" if oauth else "unsent_native_boundary")
        if oauth:
            return b'{"access_token":"offline-placeholder"}'
        body.append(raw)
        raise files.PreparedBoundary()

    provider._post = post
    try:
        provider.generate(trace["retrieval"]["query"], [Evidence(**e) for e in trace["evidence"]])
    except files.PreparedBoundary:
        pass
    if len(body) != 1 or calls != ["fake_oauth", "unsent_native_boundary"]:
        raise ValueError("Native capture did not stop exactly once")
    files.save(output / f"{case_id}_native_unsent.json", body[0])
    return {"bytes": len(body[0]), "sha256": files.sha(body[0]), "simulated_boundaries": calls}


def synthetic_claims(question, evidence):
    contract = prepare(question, evidence)
    if contract is None or not contract.eligible:
        raise ValueError("Expected complete finite source contract")
    by_key = {r.key: r for r in contract.requirements}

    def claim(text, key):
        return {"text": text, "citation_ids": [by_key[key].anchors[0]["citation_id"]]}

    if contract.family == "model_layer_bulk_conductivity_conditions":
        comparison = by_key["absolute_conductivities"].anchors[0]["groups"]
        gas = by_key["gas_synthesis"].anchors[0]["groups"]
        medium = by_key["eis_medium"].anchors[0]["groups"]
        return [claim(f"При комнатной температуре проводимость слоя Li₂O около {comparison['layer']} S/cm, "
                      f"а объёмного Li₂O — около {comparison['bulk']} S/cm по данным предшествующей литературы.",
                      "absolute_conductivities"),
                claim(f"Синтез слоя: литиевую фольгу обрабатывали в O₂ от {gas['low']} до {gas['high']} °C "
                      f"в течение {gas['hours']} часов; этот диапазон относится к получению слоя.", "gas_synthesis"),
                claim(f"EIS проводили в симметричных Li‖Li ячейках с {medium['concentration']} M LiPF₆ "
                      f"в EC/DEC {medium['left']}:{medium['right']} по объёму.", "eis_medium")]
    hold = by_key["hold_observation"].anchors[0]["groups"]
    return [claim("При нагревании поглощение увеличивается; при охлаждении достигнутое поглощение сохраняется.", "cycle_retention"),
            claim(f"После {hold['days']} суток при {hold['temperature']} °C поглощение не изменилось.", "hold_observation"),
            claim("Возможны либо близость к равновесию, либо очень медленный синерезис.", "alternative_interpretations"),
            claim("Гистерезис поддерживает гипотезу необратимой перестройки; необратимость не доказана.",
                  "irreversibility_hypothesis"),
            claim("Интенсивность кристаллического рефлекса несколько снижается: это небольшое изменение интенсивности.",
                  "slight_crystalline_intensity"),
            claim("Кристаллические области остаются практически неизменными.", "preserved_crystalline_regions"),
            claim("Гало сухой мембраны уменьшается; появляется новое аморфное гало.", "old_and_new_amorphous_halos")]


def http_check(case_id, trace, settings, output, mode):
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

    from app.core.config import get_settings
    from app.db.session import get_session
    from app.generation import service
    from app.main import app
    from app.retrieval.search import SearchResponse, SearchResult

    original = PREVIOUS / case_id / "live"
    question = read(PREVIOUS / case_id / "authorized_inputs/api_request.json")["question"]
    evidence = [Evidence(**e) for e in trace["evidence"]]
    if mode == "synthetic_complete":
        content = {"answerable": True, "claims": synthetic_claims(question, evidence)}
    else:
        content = {"answerable": False, "claims": []}
    envelope = files.encode({"choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(content, ensure_ascii=False)}}]})
    calls = []

    class Proxy:
        def generate(self, q, selected, **kwargs):
            provider = client(settings)

            def post(url, body, authorization, *, oauth=False):
                calls.append("fake_oauth" if oauth else "fake_model_response")
                if oauth:
                    return b'{"access_token":"offline-placeholder"}'
                if body != (output / f"{case_id}_native_unsent.json").read_bytes():
                    raise ValueError("Synthetic HTTP/native bytes mismatch")
                return (original / "response.bin").read_bytes() if mode == "counterfactual_old_native" else envelope

            provider._post = post
            generated = provider._parse_response(read(original / "response.bin")) if mode == "bypass_provider_old_native" \
                else provider.generate(q, selected, **kwargs)
            return replace(generated, provider="SYNTHETIC_FIDELITY_CHECK", model=None)

    retrieval = SearchResponse(query=trace["retrieval"]["query"], metadata=trace["retrieval"]["metadata"],
                               results=[SearchResult(**r) for r in trace["retrieval"]["results"]])

    def no_session():
        yield object()

    overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = no_session
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch.object(service, "search_chunks", return_value=retrieval), \
                patch.object(service, "build_answer_provider", return_value=Proxy()), \
                patch.object(Engine, "connect", side_effect=AssertionError("Offline HTTP forbids DB")):
            with TestClient(app) as test:
                response = test.post("/answer", json=read(PREVIOUS / case_id / "authorized_inputs/api_request.json"))
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
    body = response.json()
    if mode in {"counterfactual_old_native", "bypass_provider_old_native"}:
        if response.status_code != 502 or not body["detail"].startswith("Answer fidelity requirements failed:"):
            raise ValueError("Old deficient native output was not rejected by fidelity checks")
    elif response.status_code != 200 or body["status"] != ("answered" if mode == "synthetic_complete" else "insufficient_evidence"):
        raise ValueError("Synthetic complete answer/abstention did not pass")
    files.write(output / f"{case_id}_{mode}_HTTP.json", {"http_status": response.status_code, "body": body})
    return {"case_id": case_id, "mode": mode, "kind": "OFFLINE_NOT_A_NEW_REAL_MODEL_RESULT",
            "http_status": response.status_code, "simulated_boundaries": calls,
            "real_model_calls": 0, "real_oauth_calls": 0, "db_calls": 0}


def run(output):
    from app.generation import service

    settings = files.configure()
    files.verify_manifest(BASE / "freeze_v01")
    output.mkdir(parents=True, exist_ok=False)
    paths = [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("app").rglob("*.yaml"), Path(__file__), PROTOCOL,
             ROOT / "tests/unit/test_answer_fidelity.py", ROOT / "tests/unit/test_requested_context_service.py",
             ROOT / "docs/records/answer_fidelity_amendment_2026-11-05_v0.2.md"]
    bindings = files.bindings(paths)
    for path in paths:
        target = output / "source_snapshot" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        files.save(target, path.read_bytes())
    corpus, articles = read(CORPUS_BASE / "Q01/corpus.json"), read(CORPUS_BASE / "Q01/articles.json")
    predictions, natives, http = {}, {}, []
    for number in range(1, 6):
        cid = f"Q{number:02}"
        source = read(CORPUS_BASE / cid / "boundaries.json")
        with inventory_scope(corpus, articles), patch.object(service, "prepare_answer_fidelity", return_value=None):
            baseline = engine.replay(source, settings, replacement=lambda r: r)
        if baseline["trace"] != read(PREVIOUS / cid / "live/trace.json"):
            raise ValueError("Pre-change full trace not reproduced")
        with inventory_scope(corpus, articles):
            repaired = engine.replay(source, settings, replacement=lambda r: r)
        if baseline["trace"]["evidence"] != repaired["trace"]["evidence"]:
            raise ValueError("Source selection changed")
        if cid not in {"Q02", "Q04"} and baseline["trace"] != repaired["trace"]:
            raise ValueError("Out-of-scope full trace changed")
        for arm, value in (("baseline", baseline), ("repaired", repaired)):
            files.write(output / f"{cid}_{arm}.json", value)
        predictions[cid] = {"question": source["api"]["question"], "baseline": baseline, "repaired": repaired}
        natives[cid] = native(cid, repaired["trace"], settings, output)
        if cid not in {"Q02", "Q04"} and (output / f"{cid}_native_unsent.json").read_bytes() != (
                PREVIOUS / cid / "authorized_inputs/request.json").read_bytes():
            raise ValueError("Out-of-scope native bytes changed")
    for cid in ("Q02", "Q04"):
        http += [http_check(cid, predictions[cid]["repaired"]["trace"], settings, output, mode)
                 for mode in ("synthetic_complete", "counterfactual_old_native", "bypass_provider_old_native", "abstention")]
    old_corpus, dataset = read(OLD / "corpus.json"), read(OLD / "cases.json")
    regressions = []
    for index, case in enumerate(dataset["cases"]):
        source = unpack(read(OLD / f"cases/{index:03}_baseline.json"), old_corpus)
        with patch.object(service, "prepare_answer_fidelity", return_value=None):
            before = engine.replay(source, settings)
        after = engine.replay(source, settings, replacement=lambda r: r)
        api = source.get("api", source.get("request"))
        scoped = prepare(api["question"], [Evidence(**e) for e in after["trace"]["evidence"]]) is not None
        identical = before["trace"] == after["trace"]
        if not scoped and not identical:
            raise ValueError("Out-of-scope old full trace changed")
        regressions.append({"id": case["id"], "scoped": scoped, "full_trace_identical": identical})
        if index % 20 == 0:
            print(json.dumps({"old_cases_checked": index + 1}), flush=True)
    files.verify_manifest(INTAKE)
    reference, cases = read(INTAKE / "report.json"), []
    for ref in reference["cases"]:
        cid = ref["id"]
        target = next(a for a in articles.values() if Path(a["original_pdf_path"]).resolve()
                      == Path(ref["source_pdf_path_verbatim"]).resolve())
        pages = [p["pdf_page"] for p in reference["source_pages"] if p["case_id"] == cid]
        case = {"id": cid, "question": ref["question"]}
        for arm in ("baseline", "repaired"):
            value = predictions[cid][arm]
            evidence = evaluated_evidence(value["trace"], corpus)
            case[arm] = {"presence": presence(evidence, target["article_id"], pages, ref["quotes"]), "evidence": evidence,
                         "adequacy": value["trace"]["metadata"]["evidence_adequacy"], "boundary": value["boundary"],
                         "fidelity": value["trace"]["metadata"].get("answer_fidelity")}
        cases.append(case)
    for article in articles.values():
        path = Path(article["original_pdf_path"])
        if files.sha(path.read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF changed")
        bindings.update(files.bindings([path]))
    for cid in ("Q02", "Q04"):
        original = PREVIOUS / cid / "live"
        files.verify_manifest(original)
        bindings.update(files.bindings(list(original.iterdir())))
    fresh_pages, spans = 0, 0
    for page in reference["source_pages"]:
        ref = next(c for c in reference["cases"] if c["id"] == page["case_id"])
        with fitz.open(ref["source_pdf_path_verbatim"]) as pdf:
            raw = pdf[page["pdf_page"] - 1].get_text()
        if files.sha(raw.encode()) != page["sha256"]:
            raise ValueError("Reference page differs")
        fresh_pages += 1
        for span in [q["span"] for q in ref["quotes"] if q["span"] and q["pdf_page"] == page["pdf_page"]] + [
                n["raw_span"] for n in reference["source_notes"] if n["case_id"] == ref["id"] and n["pdf_page"] == page["pdf_page"]]:
            if raw[span["start"]:span["end"]] != span["text"]:
                raise ValueError("Reference span differs")
            spans += 1
    summary = {"version": "answer_fidelity_offline_v0.2", "exact_previous_baselines": 81,
               "frozen_channel_service_runs": 162, "offline_http_checks": http, "native_unsent": natives,
               "old_scoped_cases": sum(r["scoped"] for r in regressions),
               "old_full_trace_changes": sum(not r["full_trace_identical"] for r in regressions),
               "fresh_reference_pages": fresh_pages, "fresh_raw_spans": spans,
               "real_model_calls": 0, "real_oauth_calls": 0, "new_slots": 0, "scientific_accuracy": None,
               "limitations": ["Finite English source patterns and RU/EN answer wording, possible false refusals",
                               "Literal coverage and selected adverse guards are not general semantic entailment",
                               "Synthetic positives are not real model results; actual provider behavior untested",
                               "Source excerpts/old outputs/gold unchanged; no full suite/browser/concurrency check"]}
    report = {"summary": summary, "bindings": bindings, "articles": articles, "cases": cases, "regressions": regressions}
    html = render(report).replace("Сохранение запрошенного контекста в runtime", "Полнота условий и оговорок: офлайн-проверка")
    examples = "<h2>Синтетические ответы — не новые ответы модели</h2>"
    for cid in ("Q02", "Q04"):
        examples += detail(cid + " — сохранённый реальный ответ до фикса", read(PREVIOUS / cid / "live/api_response.json"))
        for mode in ("synthetic_complete", "counterfactual_old_native", "bypass_provider_old_native", "abstention"):
            examples += detail(cid + " — " + mode, read(output / f"{cid}_{mode}_HTTP.json"))
    html = html.replace("<h2>TAC: все работы снимка</h2>", examples + "<h2>TAC: все работы снимка</h2>")
    files.verify(bindings)
    files.write(output / "report.json", report)
    files.save(output / "review.html", html.encode())
    files.write(output / "qa.json", check_html(html, article_count=len(articles), case_count=5))
    files.manifest(output)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    result = run(args.output)
    if policy.denied:
        raise ValueError("Unexpected offline network attempt")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
