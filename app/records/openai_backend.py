"""Explicit OpenAI Responses backend; immutable source text and local evidence checks."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.records.compact import CompactReply, build_compact_request, resolve_compact_reply
from app.records.extraction import FullRecordReply, build_record_request, resolve_reply, write_json
from app.records.readiness import assess_readiness
from app.records.runs import build_manifest
from app.records.schema import CandidateBundle, text_hash

ENDPOINT = "https://api.openai.com/v1/responses"
FULL_VERSION = "records_openai_full_v0.1"
COMPACT_VERSION = "records_openai_compact_v0.1"
VERSIONS = {FULL_VERSION, COMPACT_VERSION}
WireFormat = Literal["full", "compact"]
ReasoningEffort = Literal["low", "medium", "high", "xhigh", "max"]


def build_openai_request(
    bundle: CandidateBundle, task: str, model: str, max_output_tokens: int,
    wire_format: WireFormat, reasoning_effort: ReasoningEffort,
) -> dict[str, Any]:
    if wire_format not in {"full", "compact"} or reasoning_effort not in {"low", "medium", "high", "xhigh", "max"}:
        raise ValueError("Unsupported OpenAI wire format or reasoning effort")
    builder = build_compact_request if wire_format == "compact" else build_record_request
    base = builder(bundle, task, model, max_output_tokens, 42)
    schema = CompactReply.model_json_schema() if wire_format == "compact" else FullRecordReply.model_json_schema()
    # Reuse source/task/prompt bytes, without the local endpoint's seed/temperature parameters.
    return {"model": model, "input": base["messages"], "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": reasoning_effort}, "store": False, "stream": False,
            "truncation": "disabled", "service_tier": "default",
            "text": {"format": {"type": "json_schema", "name": "ariadne_record_" + wire_format,
                                 "strict": True, "schema": schema}}}


def responses_content(raw: bytes) -> str:
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("status") != "completed" or payload.get("error"):
        status = payload.get("status") if isinstance(payload, dict) else "invalid_root"
        raise ValueError(f"OpenAI response is not successfully completed: {status}")
    output = payload.get("output")
    if not isinstance(output, list):
        raise ValueError("OpenAI response output must be an array")
    texts: list[str] = []
    messages = 0
    for item in output:
        if not isinstance(item, dict):
            raise ValueError("OpenAI output item must be an object")
        if item.get("type") == "reasoning":
            continue
        if item.get("type") != "message" or item.get("role") != "assistant" or item.get("status") != "completed":
            raise ValueError("Unexpected OpenAI output item or incomplete message")
        messages += 1
        content = item.get("content")
        if not isinstance(content, list):
            raise ValueError("OpenAI message content must be an array")
        for block in content:
            if not isinstance(block, dict):
                raise ValueError("OpenAI content block must be an object")
            if block.get("type") == "refusal":
                raise ValueError("OpenAI model refusal; not an extraction abstention")
            if block.get("type") != "output_text" or not isinstance(block.get("text"), str):
                raise ValueError("Expected OpenAI output_text content")
            texts.append(block["text"])
    if messages != 1 or len(texts) != 1:
        raise ValueError("Expected one OpenAI message and one JSON text block; no concatenation is performed")
    return texts[0]


def openai_identity(request: dict[str, Any], wire_format: WireFormat) -> dict[str, Any]:
    return {"backend": "openai_responses", "endpoint": ENDPOINT, "model_alias": request["model"],
            "wire_format": wire_format, "reasoning_effort": request["reasoning"]["effort"],
            "max_output_tokens": request["max_output_tokens"], "store": False, "service_tier": "default"}


def resolve_openai_response(bundle: CandidateBundle, raw: bytes, wire_format: WireFormat) -> tuple[Any, CandidateBundle]:
    content = responses_content(raw)
    if wire_format == "compact":
        compact = CompactReply.model_validate_json(content)
        return compact, resolve_compact_reply(bundle, compact)
    if wire_format != "full":
        raise ValueError("Unsupported OpenAI wire format")
    reply = FullRecordReply.model_validate_json(content)
    return reply, resolve_reply(bundle, reply)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        raise HTTPError(req.full_url, code, "OpenAI redirects are forbidden", Message(), None)


def send_openai_request(payload: bytes, api_key: str, timeout_seconds: int) -> tuple[bytes, str | None]:
    if not api_key.strip() or timeout_seconds < 1:
        raise ValueError("OpenAI credential and positive timeout required")
    request = Request(ENDPOINT, data=payload, method="POST",
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key.strip()})
    # Fixed HTTPS destination; no user-controlled host, proxy forwarding, redirects or retries.
    with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout_seconds) as response:
        return bytes(response.read()), response.headers.get("x-request-id")


def run_openai_extraction(
    input_path: Path, output_dir: Path, *, task: str, model: str, api_key: str, source_root: Path,
    wire_format: WireFormat = "full", reasoning_effort: ReasoningEffort = "medium",
    max_output_tokens: int = 8192, timeout_seconds: int = 180,
) -> dict[str, Any]:
    if not api_key.strip() or timeout_seconds < 1:
        raise ValueError("OpenAI credential and positive timeout required")
    raw_input = input_path.read_bytes()
    bundle = CandidateBundle.model_validate_json(raw_input)
    request = build_openai_request(bundle, task, model, max_output_tokens, wire_format, reasoning_effort)
    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    identity = openai_identity(request, wire_format)
    identity_bytes = json.dumps(identity, ensure_ascii=False, indent=2).encode("utf-8")
    manifest = build_manifest(input_path, operation="context_export", source_root=source_root)
    artifact = manifest["artifact"]
    if not isinstance(artifact, dict) or artifact["sha256"] != hashlib.sha256(raw_input).hexdigest():
        raise ValueError("Input changed during OpenAI request preparation")
    manifest.update(extraction_version=COMPACT_VERSION if wire_format == "compact" else FULL_VERSION,
                    task=task, task_sha256=text_hash(task), input_sha256=hashlib.sha256(raw_input).hexdigest(),
                    request_sha256=hashlib.sha256(payload).hexdigest(), runtime_identity_sha256=hashlib.sha256(identity_bytes).hexdigest(),
                    timeout_seconds=timeout_seconds, scientific_admission="not_evaluated",
                    runtime_status="remote_provider_declaration; returned model/usage recorded separately")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "input.json").write_bytes(raw_input)
    (output_dir / "request.json").write_bytes(payload)
    (output_dir / "runtime_identity.json").write_bytes(identity_bytes)
    write_json(output_dir / "manifest.json", manifest)
    started = time.perf_counter()
    result: dict[str, Any] = {"backend": "openai_responses", "scientific_admission": "not_evaluated", "review_state": "needs_review"}
    stage = "transport"
    try:
        response, request_id = send_openai_request(payload, api_key, timeout_seconds)
        (output_dir / "response.json").write_bytes(response)
        result["request_id"] = request_id
        stage = "completion_contract"
        envelope = json.loads(response)
        if isinstance(envelope, dict):
            result.update(response_id=envelope.get("id"), returned_model=envelope.get("model"),
                          response_status=envelope.get("status"), usage=envelope.get("usage"), service_tier=envelope.get("service_tier"))
        content = responses_content(response)
        reply = CompactReply.model_validate_json(content) if wire_format == "compact" else FullRecordReply.model_validate_json(content)
        write_json(output_dir / "reply.json", reply.model_dump(mode="json"))
        stage = "evidence_integrity"
        resolved = (resolve_compact_reply(bundle, reply) if isinstance(reply, CompactReply) else resolve_reply(bundle, reply))
        write_json(output_dir / "candidates.json", resolved.model_dump(mode="json"))
        result.update(status="integrity_valid", records=len(resolved.records), abstention=not resolved.records,
                      readiness=[assess_readiness(record).to_dict() for record in resolved.records])
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        if isinstance(exc, HTTPError):
            # Authentication error bodies may echo a credential; retain explicitly redacted diagnostics.
            (output_dir / "http_error_body_redacted.bin").write_bytes(exc.read().replace(api_key.encode(), b"<redacted>"))
            result["http_status"] = exc.code
        result.update(status="failed", stage=stage, error_type=type(exc).__name__, error=str(exc))
    result.update(elapsed_seconds=round(time.perf_counter() - started, 3), completed_at=datetime.now(UTC).isoformat())
    result["artifacts"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output_dir.iterdir()) if p.is_file()}
    write_json(output_dir / "result.json", result)
    return result
