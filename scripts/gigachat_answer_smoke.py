"""One explicitly authorized current /answer smoke; separate frozen artifacts."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERSION = "gigachat_answer_runtime_smoke_v0.1"
QUESTION = "Каким методом измеряли проводимость мембран и как выполняли уравновешивание образцов перед измерением?"
PROTOCOL = ROOT / "docs/records/gigachat_answer_smoke_protocol_v0.1.md"
LEDGER = ROOT / "data/experiments/gigachat_answer_runtime_attempts"


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def write(path: Path, value: Any) -> None:
    save(path, encode(value))


def bindings(paths: list[Path]) -> dict[str, str]:
    return {str(p.resolve()): sha(p.read_bytes()) for p in sorted(set(paths))}


def verify(expected: dict[str, str]) -> None:
    for name, digest in expected.items():
        if sha(Path(name).read_bytes()) != digest:
            raise ValueError("Frozen input changed: " + name)


def manifest(folder: Path) -> None:
    write(folder / "manifest.json", {"version": VERSION, "outputs": {
        p.relative_to(folder).as_posix(): sha(p.read_bytes())
        for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "manifest.json"}})


def verify_manifest(folder: Path) -> None:
    expected = json.loads((folder / "manifest.json").read_bytes())["outputs"]
    actual = {p.relative_to(folder).as_posix(): sha(p.read_bytes())
              for p in folder.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if expected != actual:
        raise ValueError("Frozen output manifest changed: " + str(folder))


def reserve(digest: str, value: dict[str, Any]) -> Path:
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Expected lowercase SHA256 request identity")
    LEDGER.mkdir(parents=True, exist_ok=True)
    slot = LEDGER / digest
    slot.mkdir(exist_ok=False)
    write(slot / "attempt.json", value)
    return slot


def recovery_inputs(parent: Path, digest: str) -> dict[str, str]:
    verify_manifest(parent)
    result = json.loads((parent / "result.json").read_bytes())
    attempt = json.loads((parent / "attempt.json").read_bytes())
    original_slot = LEDGER / digest
    if (result.get("model_attempts") != 0 or result.get("oauth_attempts") != 1
            or result.get("http_status") != 503 or result.get("answer", {}).get("detail") !=
            "GigaChat OAuth request failed (URLError)" or attempt.get("request_sha256") != digest
            or Path(attempt["output"]).resolve() != parent.resolve()
            or (parent / "response.bin").exists() or (parent / "request.json").exists()):
        raise ValueError("Continuation requires the unchanged OAuth failure before any model attempt")
    if ((original_slot / "result.json").read_bytes() != (parent / "result.json").read_bytes()
            or (original_slot / "attempt.json").read_bytes() != (parent / "attempt.json").read_bytes()):
        raise ValueError("Original attempt ledger differs from failed output")
    return bindings([parent / "manifest.json", parent / "result.json", parent / "attempt.json",
                     original_slot / "attempt.json", original_slot / "result.json"])


def reserve_continuation(parent: Path, digest: str, value: dict[str, Any]) -> Path:
    recovery_inputs(parent, digest)
    slot = LEDGER / digest / "infrastructure_recovery_v01"
    slot.mkdir(exist_ok=False)
    write(slot / "attempt.json", value)
    return slot


class PreparedBoundary(Exception):
    """Explicit stop before external requests; never a provider response."""


class NetworkPolicy:
    def __init__(self) -> None:
        self.external = False
        self.denied: list[str] = []

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event not in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            return
        address = args[1] if event in {"socket.connect", "socket.sendto"} else (args[0], args[1])
        host, port = address[:2] if isinstance(address, tuple) else (address, None)
        # Windows asyncio implements its internal socketpair over an ephemeral
        # loopback port. Permit loopback; database transactions remain read-only.
        local = host in {"localhost", "127.0.0.1", "::1"}
        remote = self.external and (
            (event == "socket.getaddrinfo" and host in {"api.giga.chat", "ngw.devices.sberbank.ru"})
            or (event == "socket.connect" and port in {443, 9443}))
        if not local and not remote:
            self.denied.append(event + ":" + str(host) + ":" + str(port))
            raise RuntimeError("Network outside the frozen smoke scope is forbidden")


def configure() -> Any:
    os.environ["FASTEMBED_CACHE_PATH"] = str(ROOT / "data/processed/model_cache")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from app.core.config import get_settings
    settings = get_settings()
    if (settings.rag_provider, settings.rag_model, settings.gigachat_scope,
            settings.rag_gigachat_max_tokens, settings.rag_timeout_seconds) != (
            "gigachat", "GigaChat-2-Max", "GIGACHAT_API_PERS", 1200, 120):
        raise ValueError("Current provider/model/scope/budget differs from the prospective protocol")
    return settings


class Observation:
    def __init__(self, folder: Path, settings: Any, policy: NetworkPolicy,
                 expected: Path | None = None) -> None:
        self.folder, self.settings, self.policy, self.expected = folder, settings, policy, expected
        self.trace: dict[str, Any] | None = None
        self.sources: dict[str, Any] | None = None
        self.articles: list[dict[str, Any]] = []
        self.body: bytes | None = None
        self.secrets = [settings.gigachat_credentials]
        self.result: dict[str, Any] = {"version": VERSION, "status": "unhandled_or_interrupted",
            "model_attempts": 0, "oauth_attempts": 0, "automatic_retries": 0, "fallbacks": 0,
            "scientific_acceptance": "not_evaluated", "independent_accuracy": None,
            "actual_cost": None, "header_request_id": None, "header_capture": "not_exposed_by_runtime_adapter"}

    def observe(self, session: Any, retrieval: Any, evidence: Any, metadata: Any) -> None:
        from app.db.models import Article
        from app.evaluation.query_packet_run import collect_sources
        from app.generation.preparation import _article_metadata
        from app.generation.query_qualifiers import assess_query_qualifiers
        self.trace = {"retrieval": asdict(retrieval), "evidence": [asdict(e) for e in evidence], "metadata": metadata}
        self.sources = collect_sources(session, self.settings, evidence)
        if self.sources["diagnostics"]:
            raise ValueError("Source registry has unresolved binding diagnostics")
        article_metadata, diagnostics = _article_metadata(session, evidence)
        self.result["qualifier_check"] = assess_query_qualifiers(
            QUESTION, evidence, baseline_allowed=metadata["evidence_adequacy"]["adequate"], article_metadata=article_metadata)
        self.result["metadata_diagnostics"] = diagnostics
        for article_id in sorted({e.article_id for e in evidence}):
            a = session.get(Article, UUID(article_id))
            regions = [r for r in self.sources["pages"].values() if r["article_id"] == article_id]
            self.articles.append({"article_id": article_id, "title": a.title, "authors": a.authors,
                "journal": a.journal, "year": a.year, "abstract": a.abstract,
                "conclusions": None, "terms": None,
                "uncollected_fields": ["conclusions", "terms"],
                "original_pdf_path": regions[0]["original_pdf_path"],
                "metadata_basis": "recorded DB metadata; not independently validated"})
        for name, value in (("trace.json", self.trace), ("sources.json", self.sources), ("articles.json", self.articles)):
            raw = encode(value)
            if self.expected is not None and raw != (self.expected / name).read_bytes():
                raise ValueError("Live retrieval/source/metadata differs from frozen " + name)
            save(self.folder / name, raw)

    def instrument(self, provider: Any) -> Any:
        original = provider._post

        def post(url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
            from app.generation.gigachat import AUTH_URL, CHAT_URL, _json
            if url != (AUTH_URL if oauth else CHAT_URL):
                raise ValueError("Unexpected endpoint")
            if self.expected is None:
                if oauth:
                    return b'{"access_token":"offline-preparation-placeholder"}'
                self.body = body
                save(self.folder / "request.json", body)
                raise PreparedBoundary()
            if not oauth:
                if body != (self.expected / "request.json").read_bytes():
                    raise ValueError("Live provider request differs from frozen native bytes")
                if self.result["model_attempts"]:
                    raise ValueError("A second model attempt is forbidden")
                self.body = body
                save(self.folder / "request.json", body)
                self.result["model_attempts"] = 1
            else:
                if self.result["oauth_attempts"]:
                    raise ValueError("A second OAuth attempt is forbidden")
                self.result["oauth_attempts"] = 1
            started = time.perf_counter()
            self.policy.external = True
            try:
                raw = original(url, body, authorization, oauth=oauth)
            finally:
                self.policy.external = False
                self.result["oauth_seconds" if oauth else "model_request_seconds"] = time.perf_counter() - started
            if oauth:
                token = _json(raw).get("access_token")
                if isinstance(token, str) and token:
                    self.secrets.append(token)
                return raw
            stored = raw
            for secret in self.secrets:
                if secret:
                    stored = stored.replace(secret.encode("utf-8"), b"[REDACTED]")
            save(self.folder / "response.bin", stored)
            self.result.update(observed_response_sha256=sha(raw), stored_response_sha256=sha(stored),
                               credential_redaction_applied=raw != stored)
            if stored != raw:
                raise ValueError("Credential redaction changed native response; acceptance blocked")
            return raw

        provider._post = post
        return provider


def run_route(observation: Observation, request: dict[str, Any]) -> Any:
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    import app.main as main
    from app.core.config import get_settings
    from app.db.session import SessionLocal, get_session
    from app.generation import service
    from app.main import app

    original_answer, original_factory = main.answer_question, service.build_answer_provider

    def session_override() -> Any:
        with SessionLocal() as session:
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            try:
                yield session
            finally:
                session.rollback()

    def traced(session: Any, *args: Any, **kwargs: Any) -> Any:
        kwargs["trace_observer"] = lambda r, e, m: observation.observe(session, r, e, m)
        return original_answer(session, *args, **kwargs)

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: observation.settings
    try:
        with patch.object(main, "answer_question", traced), patch.object(
                service, "build_answer_provider", lambda s: observation.instrument(original_factory(s))):
            with TestClient(app) as client:
                return client.post("/answer", json=request)
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_settings, None)


def source_inputs(settings: Any, observation: Observation) -> dict[str, str]:
    files = list((ROOT / "app").rglob("*.py")) + list((ROOT / "app").rglob("*.yaml"))
    files += [Path(__file__).resolve(), PROTOCOL, ROOT / "pyproject.toml", ROOT / "tests/unit/test_gigachat_answer_smoke.py"]
    files += [p for folder in (ROOT / "data/processed/model_cache", settings.data_root / "processed/vector_indexes")
              for p in folder.rglob("*") if p.is_file()]
    for page in (observation.sources or {}).get("pages", {}).values():
        files.extend([Path(page["original_pdf_path"]), Path(page["layer_pdf_path"])])
    return bindings(files)


def prepare(folder: Path, policy: NetworkPolicy, recovery_parent: Path | None = None) -> dict[str, Any]:
    settings = configure()
    folder.mkdir(parents=True, exist_ok=False)
    request = {"question": QUESTION, "collection": settings.default_collection,
               "method": settings.rag_retrieval_method, "top_k": settings.rag_top_k,
               "answer_style": "claims", "answer_language": "auto"}
    write(folder / "api_request.json", request)
    observation = Observation(folder, settings, policy)
    stopped = False
    try:
        response = run_route(observation, request)
        write(folder / "gate_response.json", {"http_status": response.status_code, "body": response.json()})
    except PreparedBoundary:
        stopped = True
    if observation.trace is None:
        raise ValueError("Actual /answer trace was not captured")
    from app.evaluation.context_compaction import SourcePage, complete_pages_in_request
    pages = [SourcePage(p["article_id"], p["region_id"], p["page_number"], p["text_layer"], p["text_layer_id"],
                        p["page_text"], p["layer_pdf_path"], p["layer_pdf_sha256"])
             for p in observation.sources["pages"].values()]
    user_text = json.loads(observation.body)["messages"][1]["content"] if observation.body else ""
    contract = {"version": VERSION, "prepared_at_utc": datetime.now(UTC).isoformat(),
        "authorization": "user_explicit_execute_current_answer_smoke_2026-10-29",
        "generation_reached": stopped, "request_sha256": sha(observation.body) if observation.body else None,
        "request_bytes": len(observation.body) if observation.body else 0,
        "input_bindings": source_inputs(settings, observation), "maximum_model_attempts": 1,
        "automatic_retries": 0, "fallbacks": 0, "scope": settings.gigachat_scope,
        "max_output_tokens": settings.rag_gigachat_max_tokens, "per_http_timeout_seconds": settings.rag_timeout_seconds,
        "actual_cost": None, "scientific_acceptance": "not_evaluated", "independent_accuracy": None,
        "complete_source_pages_in_runtime_prompt": complete_pages_in_request(user_text, pages),
        "qualifier_check": observation.result.get("qualifier_check"),
        "metadata_diagnostics": observation.result.get("metadata_diagnostics"),
        "context_scope": "Existing raw-chunk /answer, not compact-packet admission or scientific acceptance",
        "new_model_calls": 0, "network_denials": policy.denied}
    if stopped and contract["request_bytes"] > 100000:
        raise ValueError("Native request exceeds 100000-byte experiment ceiling; no clipping")
    if policy.denied:
        raise ValueError("Unexpected network activity during preparation")
    if recovery_parent is not None:
        contract["input_bindings"].update(recovery_inputs(recovery_parent, contract["request_sha256"]))
        contract["infrastructure_continuation_of"] = str(recovery_parent.resolve())
        contract["previous_model_attempts"] = 0
        contract["previous_oauth_attempts"] = 1
    write(folder / "contract.json", contract)
    manifest(folder)
    return {k: contract[k] for k in ("generation_reached", "request_sha256", "request_bytes", "new_model_calls")}


def send(prepared: Path, folder: Path, policy: NetworkPolicy) -> dict[str, Any]:
    settings = configure()
    verify_manifest(prepared)
    contract = json.loads((prepared / "contract.json").read_bytes())
    verify(contract["input_bindings"])
    if not contract["generation_reached"]:
        raise ValueError("Original adequacy gate blocked preparation; generation forbidden")
    if sha((prepared / "request.json").read_bytes()) != contract["request_sha256"]:
        raise ValueError("Frozen request SHA256 mismatch")
    request = json.loads((prepared / "api_request.json").read_bytes())
    attempt = {"version": VERSION, "request_sha256": contract["request_sha256"],
               "contract_sha256": sha((prepared / "contract.json").read_bytes()),
               "reserved_at_utc": datetime.now(UTC).isoformat(), "output": str(folder.resolve()),
               "maximum_model_attempts": 1, "authorization": contract["authorization"]}
    parent = contract.get("infrastructure_continuation_of")
    if parent is not None:
        attempt["infrastructure_continuation_of"] = parent
        slot = reserve_continuation(Path(parent), contract["request_sha256"], attempt)
    else:
        slot = reserve(contract["request_sha256"], attempt)
    folder.mkdir(parents=True, exist_ok=False)
    write(folder / "attempt.json", attempt)
    observation = Observation(folder, settings, policy, prepared)
    if parent is not None:
        observation.result.update(infrastructure_continuation_of=parent, previous_model_attempts=0, previous_oauth_attempts=1)
    started = time.perf_counter()
    from sqlalchemy.exc import SQLAlchemyError

    from app.generation.providers import GenerationOutputError, GenerationUnavailableError
    try:
        response = run_route(observation, request)
        write(folder / "api_response.json", {"http_status": response.status_code, "body": response.json()})
        if response.status_code != 200:
            status = "runtime_http_error"
        elif response.json().get("status") == "answered":
            status = "runtime_answered"
        else:
            status = "provider_abstained" if observation.result["model_attempts"] else "gate_rejected"
        observation.result.update(http_status=response.status_code, answer=response.json(),
                                  status=status)
        verify_manifest(prepared)
        verify(contract["input_bindings"])
        observation.result["postflight_input_hashes"] = "verified"
    except (GenerationOutputError, GenerationUnavailableError, SQLAlchemyError, ValueError, OSError) as exc:
        message = str(exc) if not isinstance(exc, SQLAlchemyError) else "Database operation failed; see exception type"
        for secret in observation.secrets:
            if secret:
                message = message.replace(secret, "[REDACTED]")
        observation.result.update(status="failed", error_type=type(exc).__name__, error=message)
    finally:
        raw_path = folder / "response.bin"
        if raw_path.exists():
            from app.generation.gigachat import _json
            try:
                native = _json(raw_path.read_bytes())
                observation.result.update(returned_model=native.get("model"), usage=native.get("usage"),
                                          native_response_id=native.get("id"))
            except (ValueError, UnicodeError, AttributeError) as exc:
                observation.result["native_metadata_parse_error"] = type(exc).__name__
        observation.result.update(elapsed_seconds=time.perf_counter() - started,
                                  network_denials=policy.denied, completed_at_utc=datetime.now(UTC).isoformat())
        write(folder / "result.json", observation.result)
        write(slot / "result.json", observation.result)
        manifest(folder)
    return observation.result


def review(prepared: Path, live: Path, output: Path) -> dict[str, Any]:
    verify_manifest(prepared)
    verify_manifest(live)
    result = json.loads((live / "result.json").read_bytes())
    contract = json.loads((prepared / "contract.json").read_bytes())
    articles = json.loads((prepared / "articles.json").read_bytes())
    output.mkdir(parents=True, exist_ok=False)

    def detail(label: str, value: Any) -> str:
        return "<details><summary>" + html.escape(label) + "</summary><pre>" + html.escape(
            value if isinstance(value, str) else encode(value).decode()) + "</pre></details>"

    def cell(value: Any) -> str:
        return "<td>" + ("Отсутствует / не собрано в этом smoke" if value is None else detail("Развернуть", value)) + "</td>"

    rows = []
    for article in articles:
        cells = "".join(cell(article.get(k)) for k in ("title", "authors", "journal", "year", "abstract", "conclusions", "terms"))
        link = Path(article["original_pdf_path"]).as_uri()
        rows.append('<tr data-row>' + cells + '<td><a href="' + html.escape(link, quote=True) + '">Original PDF</a></td></tr>')
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — GigaChat /answer smoke</title>'
            '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
            'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '[hidden]{display:none!important}</style><h1>GigaChat: текущий /answer</h1><p>'
            + html.escape(VERSION) + '</p><p>Один exposed development case. Независимой научной приёмки нет.</p>'
            + '<p>Input snapshot SHA256: ' + html.escape(contract["request_sha256"]) + '</p>'
            + detail("Вопрос", QUESTION) + detail("Результат и usage", result)
            + '<h2>TAC: все статьи выбранных доказательств</h2><p>Recorded metadata; Conclusions и Terms '
              'не собирались этим smoke. Отсутствующие значения не восстановлены.</p>'
            + '<label>Поиск <input id="q" type="search"></label><table><thead><tr>'
            + ''.join('<th>' + x + '</th>' for x in (
                "Title", "Authors", "Journal", "Year", "Abstract", "Conclusions", "Terms", "Original file"))
            + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
            + detail("Frozen contract и ограничения", contract))
    for label, path in (("Полный фактический запрос", prepared / "request.json"),
                        ("Исходный ответ GigaChat", live / "response.bin"),
                        ("Полная трасса: retrieval, evidence, диагностика", prepared / "trace.json"),
                        ("Исходные страницы, PDF, слои и хеши", prepared / "sources.json")):
        if path.exists():
            body += detail(label, path.read_text(encoding="utf-8"))
    body += ('<script>document.getElementById("q").addEventListener("input",e=>{for(const r of '
             'document.querySelectorAll("[data-row]"))r.hidden=!r.textContent.toLocaleLowerCase().includes('
             'e.target.value.toLocaleLowerCase())})</script></html>\n')
    save(output / "review.html", body.encode("utf-8"))
    write(output / "summary.json", {"version": VERSION, "status": result["status"], "articles": len(articles),
                                   "request_sha256": contract["request_sha256"], "new_model_calls": 0})
    manifest(output)
    return {"review": str((output / "review.html").resolve()), "status": result["status"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "send", "review"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--live", type=Path)
    parser.add_argument("--recover-before-model-from", type=Path)
    parser.add_argument("--authorize-one-gigachat-call", action="store_true")
    args = parser.parse_args()
    policy = NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == "prepare":
        value = prepare(args.output, policy, args.recover_before_model_from)
    elif args.mode == "send":
        if not args.authorize_one_gigachat_call or args.prepared is None:
            parser.error("send requires --prepared and --authorize-one-gigachat-call")
        value = send(args.prepared, args.output, policy)
        value = {k: value.get(k) for k in ("status", "model_attempts", "oauth_attempts", "usage", "error_type", "error")}
    else:
        if args.prepared is None or args.live is None:
            parser.error("review requires --prepared and --live")
        value = review(args.prepared, args.live, args.output)
    print(json.dumps(value, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
