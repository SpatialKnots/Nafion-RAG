"""Bounded v0.2 experiment, reusing immutable transport/preparation machinery."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import gigachat_answer_smoke as f
from scripts import prepare_query_rewriting_v02_20261110 as reader
from scripts import query_rewriting_v02 as qr
from scripts import run_query_rewriting_20261110 as engine

BASE = f.ROOT / "output/query_rewriting_v02_20261110"
OLD = engine.BASE
SCOPE = f.ROOT / "docs/records/query_rewriting_v02_2026-11-10.md"
TESTS = f.ROOT / "tests/unit/test_query_rewriting_v02.py"
USER = "Выполняй"
INTAKE = f.ROOT / "output/satoh_fan_qa_20261110/intake_v02/report.json"
TITLE_PATTERNS = {
    "Satoh": r"Physical and Electrolytic Properties of Trifluorinated Linear Ethers\s+and Their Application to Lithium Secondary Batteries",
    "Fan": r"Non-flammable electrolyte enables Li-metal\s+batteries with aggressive cathode chemistries",
}


def read(path):
    return json.loads(path.read_bytes())


def title_contexts(catalog):
    contexts, proofs = {}, {}
    for label, pattern in TITLE_PATTERNS.items():
        source = catalog["sources"][label]
        page = next(p for p in source["pages"] if p["pdf_page"] == 1)
        matches = list(re.finditer(pattern, page["text"]))
        if len(matches) != 1 or f.sha(page["text"].encode()) != page["page_text_sha256"]:
            raise ValueError("Verified first-page title missing/ambiguous/hash mismatch")
        article = source["article"]
        if f.sha(Path(article["original_pdf_path"]).read_bytes()) != article["original_pdf_sha256"]:
            raise ValueError("Original PDF hash differs")
        match = matches[0]
        title = re.sub(r"\s+", " ", match[0]).strip()
        contexts[label] = {"article_id": article["article_id"], "title": title,
                           "title_sha256": hashlib.sha256(title.encode()).hexdigest(),
                           "original_pdf_sha256": article["original_pdf_sha256"]}
        proofs[label] = {"page": 1, "page_text_sha256": page["page_text_sha256"], "start": match.start(),
                         "end": match.end(), "raw_title": match[0], "context": contexts[label]}
    return contexts, proofs


@contextmanager
def environment(contexts, questions):
    facade = SimpleNamespace(VERSION=qr.VERSION, __file__=qr.__file__, validate=qr.validate, activate=qr.activate,
        request=lambda case, model: qr.request(case, model, contexts[case["id"].split("_")[0]]),
        parse_response=lambda raw, question: qr.parse_response(raw, question, contexts[questions[question]]))
    with patch.object(engine, "BASE", BASE), patch.object(engine, "SCOPE", SCOPE), patch.object(engine, "TESTS", TESTS), \
            patch.object(engine, "USER", USER), patch.object(engine, "qr", facade), patch.object(reader, "qr", facade), \
            engine.constants():
        yield


def initialize(contexts, questions):
    settings = f.configure()
    if settings.rag_methods_identity_policy != "disabled":
        raise ValueError("Methods policy must stay disabled")
    rows = engine.baseline.make_cases(read(engine.baseline.PUBLIC))
    verified, proofs = title_contexts(read(INTAKE))
    contexts.update(verified)
    questions.update({c["question_original"]: c["id"].split("_")[0] for c in rows})
    BASE.mkdir(exist_ok=False)
    freeze = BASE / "input_freeze_v01"
    freeze.mkdir()
    paths = [*f.ROOT.joinpath("app").rglob("*.py"), *f.ROOT.joinpath("app").rglob("*.yaml"),
        Path(__file__), Path(qr.__file__), Path(engine.__file__), Path(engine.baseline.__file__), Path(f.__file__),
        Path(reader.__file__), f.ROOT / "scripts/query_rewriting_experiment.py", TESTS, SCOPE,
        f.ROOT / "docs/cross_lingual_glossary.yaml", f.ROOT / "pyproject.toml"]
    for label in contexts:
        paths.append(Path(read(INTAKE)["sources"][label]["article"]["original_pdf_path"]))
    bindings = f.bindings(paths)
    for source in paths:
        if source.suffix == ".pdf":
            continue
        target = freeze / "source_snapshot" / source.relative_to(f.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target, source.read_bytes())
    f.write(freeze / "title_contexts.json", {"contexts": contexts, "proofs": proofs,
        "title_catalog_path": str(INTAKE), "title_catalog_sha256": f.sha(INTAKE.read_bytes()),
        "meaning": "exact cached original-PDF page1 title span, not abstract/results/reference data"})
    for case in rows:
        folder = freeze / "rewrites" / case["id"]
        folder.mkdir(parents=True)
        f.save(folder / "request.json", qr.request(case, settings.rag_model, contexts[case["id"].split("_")[0]]))
        f.manifest(folder)
    f.write(freeze / "questions.json", {"version": qr.VERSION, "cases": rows, "references_included": False})
    f.write(freeze / "runtime.json", {"input_bindings": bindings, "raw_user_authorization": USER,
        "maximum_rewrite_attempts": 20, "maximum_answer_attempts": 20, "maximum_oauth_attempts": 40,
        "automatic_retries": 0, "fallbacks": 0, "continuations": 0,
        "model": settings.rag_model, "max_output_tokens": 1200, "timeout_seconds": 120})
    f.manifest(freeze)
    return {"cases": 20, "verified_titles": 2, "new_model_calls": 0}


def offline(contexts):
    rows = []
    for case in engine.cases():
        folder = OLD / "rewrites" / case["id"]
        f.verify_manifest(folder)
        try:
            plan = qr.parse_response((folder / "response.bin").read_bytes(), case["question_original"],
                                     contexts[case["id"].split("_")[0]], legacy=True)
        except ValueError as exc:
            row = {"id": case["id"], "status": "rejected", "reason": str(exc), "plan": None}
        else:
            row = {"id": case["id"], "status": "translation_usable_pending_meaning_review", "plan": plan}
        row.update(old_status=read(folder / "result.json")["status"],
                   original_response_sha256=f.sha((folder / "response.bin").read_bytes()))
        rows.append(row)
    folder = BASE / "offline_replay_v01"
    folder.mkdir(exist_ok=False)
    f.write(folder / "report.json", {"cases": rows, "new_model_calls": 0,
        "scope": "new parser on unchanged old responses; not a retroactive v0.1 score change"})
    f.manifest(folder)
    return {"cases": 20, "usable": sum(r["plan"] is not None for r in rows), "new_model_calls": 0}


def run_all(mode):
    settings, rows = f.configure(), []
    for case in engine.cases():
        done = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "scripts.run_query_rewriting_v02_20261110",
                               mode, "--case-id", case["id"]], cwd=f.ROOT, capture_output=True, encoding="utf8", check=False)
        folder = BASE / "worker_logs" / case["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for name, value in (("stdout", done.stdout), ("stderr", done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    value = value.replace(secret, "[REDACTED]")
            f.save(folder / f"{mode}_{name}.txt", value.encode())
        row = {"id": case["id"], "returncode": done.returncode}
        if not done.returncode:
            row.update(json.loads(done.stdout.strip().splitlines()[-1]))
        rows.append(row)
        print(json.dumps(row), flush=True)
        if done.returncode:
            break
    value = {"cases": rows, "finished_all": len(rows) == 20 and not rows[-1]["returncode"]}
    f.write(BASE / f"{mode}_batch_v01.json", value)
    if mode == "rewrite":
        engine.close_rewrites()
    if mode == "send":
        engine.close_answers()
    return {"stage": mode, "finished_all": value["finished_all"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "offline", "rewrite", "rewrite-all", "freeze-plans", "prepare",
                                         "prepare-all", "seal", "send", "send-all"))
    parser.add_argument("--case-id", choices=engine.IDS)
    args = parser.parse_args()
    contexts, questions = {}, {}
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode != "init":
        contexts.update(read(BASE / "input_freeze_v01/title_contexts.json")["contexts"])
        questions.update({c["question_original"]: c["id"].split("_")[0]
                          for c in read(BASE / "input_freeze_v01/questions.json")["cases"]})
    with environment(contexts, questions):
        guard = engine.baseline.GoldReadGuard()
        if args.mode not in {"init", "offline"}:
            sys.addaudithook(guard)
        if args.mode == "init":
            result = initialize(contexts, questions)
        elif args.mode == "offline":
            result = offline(contexts)
        elif args.mode.endswith("-all"):
            result = run_all(args.mode.removesuffix("-all"))
        elif args.mode == "freeze-plans":
            result = reader.freeze()
        elif args.mode == "seal":
            result = engine.seal()
        else:
            if args.case_id is None:
                raise ValueError("Case required")
            case = next(c for c in engine.cases() if c["id"] == args.case_id)
            result = engine.rewrite(case, policy) if args.mode == "rewrite" else (
                engine.prepare(case, policy, guard) if args.mode == "prepare" else engine.send(case, policy))
        if policy.denied or guard.denied:
            raise RuntimeError("Forbidden reference/network access")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
