"""Explicit development tracing of the existing answer pipeline; no automatic scientific acceptance."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from pydantic import BaseModel, ConfigDict, StrictBool

from app.evaluation.context_compaction import SourcePage, require_no_complete_pages
from app.generation.providers import (
    SCIENTIFIC_ANSWER_SYSTEM_PROMPT,
    AnswerLanguage,
    AnswerStyle,
    Evidence,
    GeneratedClaim,
    GenerationOutputError,
    OpenAIAnswerProvider,
    ProviderResult,
)
from app.records.openai_backend import ENDPOINT, responses_content, send_openai_request
from app.retrieval.search import SearchResponse

VERSION = "answer_end_to_end_trace_v0.1"


class NativeClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    citation_ids: list[str]


class NativeAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answerable: StrictBool
    claims: list[NativeClaim]


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class PreparationComplete(Exception):
    """Intentional dry-preparation boundary, never a model abstention or success."""


class TraceResponsesProvider(OpenAIAnswerProvider):
    """Development-only Responses bridge; reuses production prompts, not global provider settings."""

    def __init__(self, *, model: str, api_key: str, max_output_tokens: int = 4096, timeout_seconds: int = 180,
                 output: Path | None = None, expected_request: bytes | None = None,
                 source_pages: list[SourcePage] | None = None) -> None:
        super().__init__(base_url="https://api.openai.com/v1", api_key=api_key, model=model,
                         timeout_seconds=timeout_seconds, max_tokens=max_output_tokens)
        self.output = output
        self.expected_request = expected_request
        self.source_pages = None if source_pages is None else list(source_pages)
        self.prepared_request: bytes | None = None
        self.result: dict[str, Any] = {"provider": "openai_responses", "endpoint": ENDPOINT, "model": model,
                                      "scientific_admission": "not_evaluated"}

    def request(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = "claims",
                answer_language: AnswerLanguage = "auto") -> dict[str, Any]:
        if not question.strip() or not evidence:
            raise ValueError("Trace generation requires a nonempty question and selected evidence")
        user_text = self._user_prompt(question, evidence, answer_style=answer_style, answer_language=answer_language)
        if self.source_pages is not None:
            require_no_complete_pages(user_text, self.source_pages)
        return {"model": self.model, "input": [
            {"role": "system", "content": SCIENTIFIC_ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_text}],
            "max_output_tokens": self.max_tokens, "reasoning": {"effort": "medium"}, "store": False,
            "stream": False, "truncation": "disabled", "service_tier": "default",
            "text": {"format": {"type": "json_schema", "name": "ariadne_answer_trace", "strict": True,
                                "schema": NativeAnswer.model_json_schema()}}}

    def generate(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = "claims",
                 answer_language: AnswerLanguage = "auto") -> ProviderResult:
        payload = encode(self.request(question, evidence, answer_style=answer_style, answer_language=answer_language))
        if len(payload) > 100_000:
            raise ValueError("Frozen trace request exceeds 100,000-byte budget; no clipping is performed")
        self.prepared_request = payload
        if self.output is None:
            raise PreparationComplete()
        if payload != self.expected_request:
            raise ValueError("Live question/evidence/request differs from frozen preflight; no API call made")
        self.output.mkdir(parents=True, exist_ok=False)
        (self.output / "request.json").write_bytes(payload)
        self.result["request_sha256"] = digest(payload)
        stage = "transport"
        started = time.perf_counter()
        try:
            raw, request_id = send_openai_request(payload, self.api_key, self.timeout_seconds)
            (self.output / "response.json").write_bytes(raw)
            envelope = json.loads(raw)
            self.result["request_id"] = request_id
            if isinstance(envelope, dict):
                self.result.update(response_id=envelope.get("id"), returned_model=envelope.get("model"),
                                   usage=envelope.get("usage"), response_status=envelope.get("status"))
            stage = "completion_contract"
            answer = NativeAnswer.model_validate_json(responses_content(raw))
            if any(not claim.text.strip() or not claim.citation_ids or any(not item.strip() for item in claim.citation_ids)
                   for claim in answer.claims) or (answer.answerable and not answer.claims):
                raise GenerationOutputError("Answerable claims require nonempty text and citation IDs")
            result = ProviderResult(answerable=answer.answerable,
                                    claims=[GeneratedClaim(text=claim.text.strip(), citation_ids=claim.citation_ids)
                                            for claim in answer.claims],
                                    provider="openai_responses", model=self.model)
            (self.output / "reply.json").write_bytes(encode(answer.model_dump()))
            self.result["status"] = "provider_valid"
            return result
        except (HTTPError, URLError, TimeoutError, ValueError, GenerationOutputError) as exc:
            if isinstance(exc, HTTPError):
                (self.output / "http_error_redacted.bin").write_bytes(exc.read().replace(self.api_key.encode(), b"<redacted>"))
            self.result.update(status="failed", stage=stage, error_type=type(exc).__name__,
                               error=str(exc).replace(self.api_key, "<redacted>"))
            raise
        finally:
            self.result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            (self.output / "provider_result.json").write_bytes(encode(self.result))


class TraceCollector:
    def __init__(self, expected: bytes | None = None) -> None:
        self.expected = expected
        self.trace: dict[str, Any] | None = None

    def __call__(self, retrieval: SearchResponse, evidence: list[Evidence], metadata: dict[str, object]) -> None:
        trace = {"version": VERSION, "retrieval": asdict(retrieval), "evidence": [asdict(item) for item in evidence], "metadata": metadata}
        if self.expected is not None and encode(trace) != self.expected:
            raise ValueError("Live retrieval/selection differs from frozen trace; no API call permitted")
        self.trace = trace
