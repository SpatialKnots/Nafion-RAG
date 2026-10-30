"""GigaChat answer provider. No networking during configuration or imports."""

from __future__ import annotations

import json
import ssl
from email.message import Message
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, ValidationError

from app.generation.presentation import PRESENTATION_INSTRUCTION
from app.generation.providers import (
    SCIENTIFIC_ANSWER_SYSTEM_PROMPT,
    AnswerLanguage,
    AnswerStyle,
    Evidence,
    GeneratedClaim,
    GenerationOutputError,
    GenerationUnavailableError,
    ProviderResult,
    _answer_language_instruction,
    _evidence_text_for_generation,
    _mini_review_user_prompt,
)

AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://api.giga.chat/v1/chat/completions"
SCOPES = {"GIGACHAT_API_PERS", "GIGACHAT_API_B2B", "GIGACHAT_API_CORP"}


class _Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str
    citation_ids: list[str]


class _Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answerable: bool
    claims: list[_Claim]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON number")


def _json(raw: bytes | str) -> Any:
    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        raise HTTPError(req.full_url, code, "GigaChat redirects are forbidden", Message(), None)


class GigaChatAnswerProvider:
    def __init__(self, *, credentials: str, scope: str, model: str, timeout_seconds: int, max_tokens: int,
                 ca_bundle_file: str = "") -> None:
        if not credentials.strip() or any(char.isspace() for char in credentials.strip()):
            raise GenerationUnavailableError("GIGACHAT_CREDENTIALS must contain the GigaChat authorization key")
        if scope not in SCOPES:
            raise GenerationUnavailableError("GIGACHAT_SCOPE must be GIGACHAT_API_PERS, GIGACHAT_API_B2B or GIGACHAT_API_CORP")
        if not model.strip().startswith("GigaChat"):
            raise GenerationUnavailableError("RAG_MODEL must name a GigaChat model, for example GigaChat-2-Max")
        if timeout_seconds <= 0 or max_tokens <= 0:
            raise ValueError("timeout_seconds and max_tokens must be positive")
        self.credentials = credentials.strip()
        self.scope = scope
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.ca_bundle_file = ca_bundle_file

    def _post(self, url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
        if url != (AUTH_URL if oauth else CHAT_URL):
            raise ValueError("Unregistered GigaChat endpoint")
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/x-www-form-urlencoded" if oauth else "application/json",
            "Accept": "application/json",
        }
        if oauth:
            headers["RqUID"] = str(uuid4())
        stage = "OAuth" if oauth else "generation"
        try:
            context = ssl.create_default_context()
            if self.ca_bundle_file:
                context.load_verify_locations(cafile=self.ca_bundle_file)
        except (OSError, ssl.SSLError) as exc:
            raise GenerationUnavailableError(
                f"GigaChat TLS trust configuration failed ({type(exc).__name__}); check GIGACHAT_CA_BUNDLE_FILE"
            ) from None
        # Neither a redirect nor an environment proxy may forward credentials.
        opener = build_opener(ProxyHandler({}), _NoRedirect(), HTTPSHandler(context=context))
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with opener.open(request, timeout=self.timeout_seconds) as response:
                return bytes(response.read())
        except HTTPError as exc:
            raise GenerationUnavailableError(f"GigaChat {stage} request failed with HTTP {exc.code}") from None
        except (OSError, TimeoutError, URLError, HTTPException) as exc:
            # Do not expose provider bodies, authorization values or token-bearing exceptions.
            raise GenerationUnavailableError(f"GigaChat {stage} request failed ({type(exc).__name__})") from None

    def _user_prompt(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = "claims",
                     answer_language: AnswerLanguage = "auto") -> str:
        answer_instruction = (
            'If evidence is insufficient, return exactly {"answerable": false, "claims": []}. '
            "When answerable=false, claims must be empty: do not put explanations or missing-information statements in claims. "
            "When answerable=true, claims must contain at least one supported scientific statement with citation_ids."
        )
        answerability_instruction = (
            "Before setting answerable=true, check that the supplied evidence directly answers the user's requested "
            "information for the specified sample, method, and conditions. A citation supporting a related fact is not sufficient. "
            "For an exact reported value or duration, do not substitute a completion criterion, an unspecified waiting time, "
            "or a qualitative description for that value. Do not borrow a value from another sample, work, or experimental stage; "
            "preparation, drying, and soaking times are not measurement dwell times unless the evidence explicitly links them. "
            "If only related context is available instead of the requested answer, return answerable=false with claims=[]. "
            "When the question asks for a method or criterion itself, a directly supported qualitative answer is allowed."
        )
        citation_instruction = (
            "Allowed citation_ids values (exact strings): "
            + json.dumps(list(dict.fromkeys(item.citation_id for item in evidence)), ensure_ascii=False)
            + ". Use these strings exactly in citation_ids. "
            "Square brackets delimiting evidence headings are not part of the IDs. "
            "Do not add brackets, whitespace, or other characters to an ID."
        )
        if answer_style == "mini_review":
            return (f"{answer_instruction}\n\n{answerability_instruction}\n\n{PRESENTATION_INSTRUCTION}\n\n{citation_instruction}\n\n"
                    + _mini_review_user_prompt(question, evidence, answer_language=answer_language))
        blocks = [
            f"[{item.citation_id}] title={item.title!r}; doi={item.doi!r}; "
            f"pages={item.page_start}-{item.page_end}; source_type={item.source_type}\n{_evidence_text_for_generation(item)}"
            for item in evidence
        ]
        return (f"{_answer_language_instruction(answer_language)}\n\n{answer_instruction}\n\n"
                f"{answerability_instruction}\n\n{PRESENTATION_INSTRUCTION}\n\n{citation_instruction}\n\n"
                f"Question:\n{question}\n\nEvidence:\n\n" + "\n\n".join(blocks))

    def generate(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = "claims",
                 answer_language: AnswerLanguage = "auto") -> ProviderResult:
        if not evidence:
            return ProviderResult(answerable=False, claims=[], provider="gigachat", model=self.model)
        reply_schema = _Answer.model_json_schema()
        reply_schema["$defs"]["_Claim"]["properties"]["citation_ids"]["items"]["enum"] = list(
            dict.fromkeys(item.citation_id for item in evidence))
        # Obtain a fresh token per generation. No persisted token, retry or alternate provider.
        auth = self._post(AUTH_URL, urlencode({"scope": self.scope}).encode("ascii"),
                          "Basic " + self.credentials, oauth=True)
        try:
            envelope = _json(auth)
        except (ValueError, UnicodeError):
            raise GenerationUnavailableError("GigaChat OAuth response is not valid JSON") from None
        token = envelope.get("access_token") if isinstance(envelope, dict) else None
        if not isinstance(token, str) or not token or any(char.isspace() for char in token):
            raise GenerationUnavailableError("GigaChat OAuth response lacks a valid access token")
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "stream": False,
            "response_format": {"type": "json_schema", "schema": reply_schema, "strict": True},
            "messages": [
                {"role": "system", "content": SCIENTIFIC_ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": self._user_prompt(
                    question, evidence, answer_style=answer_style, answer_language=answer_language)},
            ],
        }
        raw = self._post(CHAT_URL, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"), "Bearer " + token)
        try:
            response = _json(raw)
        except (ValueError, UnicodeError):
            raise GenerationOutputError("GigaChat response is not valid JSON") from None
        return self._parse_response(response)

    def _parse_response(self, payload: Any) -> ProviderResult:
        if not isinstance(payload, dict):
            raise GenerationOutputError("GigaChat response root must be an object")
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise GenerationOutputError("GigaChat response must contain exactly one choice")
        choice = choices[0]
        if choice.get("finish_reason") != "stop":
            raise GenerationOutputError("GigaChat response is incomplete or filtered; expected finish_reason=stop")
        message = choice.get("message")
        if (not isinstance(message, dict) or message.get("role") != "assistant" or message.get("refusal")
                or message.get("function_call") or message.get("tool_calls")):
            raise GenerationOutputError("GigaChat response must contain plain assistant content without refusal or function calls")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise GenerationOutputError("GigaChat response lacks message.content")
        try:
            generated = _Answer.model_validate(_json(content))
        except (ValueError, UnicodeError, ValidationError):
            raise GenerationOutputError("GigaChat answer does not match the required JSON schema") from None
        if generated.answerable != bool(generated.claims):
            raise GenerationOutputError("GigaChat answerable and claims are inconsistent")
        if any(not claim.text.strip() for claim in generated.claims):
            raise GenerationOutputError("GigaChat claims must contain non-empty text")
        return ProviderResult(
            answerable=generated.answerable,
            claims=[GeneratedClaim(text=claim.text.strip(), citation_ids=claim.citation_ids) for claim in generated.claims],
            provider="gigachat",
            model=self.model,
        )
