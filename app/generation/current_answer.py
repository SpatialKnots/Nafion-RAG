"""Current web pipeline: one rewrite, existing source pipeline, one guarded answer."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.documents.service import DocumentAccessError
from app.generation import query_rewriting as rewriting
from app.generation import service
from app.generation.gigachat import AUTH_URL, CHAT_URL, GigaChatAnswerProvider, _json
from app.generation.presentation import capture_sources
from app.generation.providers import GenerationOutputError, GenerationUnavailableError
from app.generation.required_answer_fields import RequirementGuidedAnswerProvider
from app.generation.required_fields_guard import RequiredFieldsGuardProvider
from app.generation.rewrite_context import resolve_context
from app.retrieval.search import _validate_top_k
from app.retrieval.vector_index import VectorIndexUnavailableError

VERSION = "current_answer_web_v0.1"


class ObservedTransport:
    """Record only chat bodies and operation counts; never OAuth tokens or headers."""

    def __init__(self) -> None:
        self.exchanges: list[dict[str, Any]] = []
        self.attempts = {"oauth": 0, "model": 0}

    def post(self, provider: GigaChatAnswerProvider, url: str, body: bytes, authorization: str,
             *, oauth: bool = False) -> bytes:
        self.attempts["oauth" if oauth else "model"] += 1
        exchange: dict[str, Any] = {}
        if not oauth:
            exchange = {"request": _json(body), "raw_response": None}
            self.exchanges.append(exchange)
        result = GigaChatAnswerProvider._post(provider, url, body, authorization, oauth=oauth)
        if not oauth:
            exchange["raw_response"] = result.decode("utf-8", errors="replace")
        return result


class RewriteProvider(GigaChatAnswerProvider):
    def __init__(self, settings: Settings, observation: ObservedTransport) -> None:
        super().__init__(**provider_options(settings))
        self.observation = observation

    def rewrite(self, question: str, context: dict[str, str] | None) -> dict[str, Any]:
        auth = self.observation.post(self, AUTH_URL, urlencode({"scope": self.scope}).encode("ascii"),
                                     "Basic " + self.credentials, oauth=True)
        try:
            envelope = _json(auth)
        except (ValueError, UnicodeError):
            raise GenerationUnavailableError("GigaChat rewriting OAuth response is not valid JSON") from None
        token = envelope.get("access_token") if isinstance(envelope, dict) else None
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise GenerationUnavailableError("GigaChat rewriting OAuth response lacks a valid access token")
        case = {"question_original": question, **(context or {})}
        body = rewriting.request(case, self.model, context)
        raw = self.observation.post(self, CHAT_URL, body, "Bearer " + token)
        try:
            return rewriting.parse_response(raw, question, context)
        except (ValueError, UnicodeError) as exc:
            raise GenerationOutputError("Rewriting rejected: " + str(exc)) from exc


class ObservedAnswerProvider(RequirementGuidedAnswerProvider):
    def __init__(self, settings: Settings, observation: ObservedTransport) -> None:
        super().__init__(**provider_options(settings))
        self.observation = observation

    def _post(self, url: str, body: bytes, authorization: str, *, oauth: bool = False) -> bytes:
        return self.observation.post(self, url, body, authorization, oauth=oauth)


def provider_options(settings: Settings) -> dict[str, Any]:
    if settings.rag_provider != "gigachat":
        raise ValueError("Current answer pipeline requires the configured GigaChat provider")
    return {"credentials": settings.gigachat_credentials, "scope": settings.gigachat_scope,
            "model": settings.rag_model, "max_tokens": settings.rag_gigachat_max_tokens,
            "timeout_seconds": settings.rag_timeout_seconds, "ca_bundle_file": settings.gigachat_ca_bundle_file}


def run(session: Session, settings: Settings, options: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """Caller owns a read-only transaction. Failures retain completed-stage diagnostics."""
    # The legacy process cache holds session-owned ORM rows. A read-only rollback
    # expires them, breaking the next request. Keep arrays/rows request-local here;
    # fixing the shared legacy cache for other API routes is a separate change.
    settings = settings.model_copy(update={"vector_index_cache_enabled": False})
    question = options["question"].strip()
    observed_rewrite, observed_answer = ObservedTransport(), ObservedTransport()
    payload: dict[str, Any] = {"version": VERSION, "question": question, "stage": "source_context", "status": "preparing",
        "rewriting": {"version": rewriting.VERSION, "validator_version": rewriting.VALIDATOR_VERSION,
                      "plan": None, "meaning_review": "not_performed", "scientific_support": "not_evaluated"},
        "answer": None, "review": None, "delivery_status": "not_reached",
        "transport": {"rewriting": observed_rewrite.exchanges, "answer": observed_answer.exchanges},
        "attempts": {"rewriting": observed_rewrite.attempts, "answer": observed_answer.attempts},
        "retry_performed": False, "fallback_performed": False, "server_persistence": False}
    payload["vector_index_cache"] = "disabled_for_request_scoped_orm_rows"
    sources: dict[str, Any] = {}
    try:
        if not question:
            raise ValueError("question must not be empty")
        if options["method"] != "hybrid_cross_lingual":
            raise ValueError("Current rewriting profile requires hybrid_cross_lingual retrieval")
        _validate_top_k(options["top_k"], settings)
        context, proof = resolve_context(session, settings, question, options["collection"], options["library_source_id"])
        payload["rewriting"]["context_diagnostics"] = proof
        payload["stage"] = "rewriting"
        plan = RewriteProvider(settings, observed_rewrite).rewrite(rewriting.question_body(question), context)
        payload["rewriting"]["plan"] = plan
        payload["stage"] = "retrieval_and_answer"
        reviews: list[dict[str, Any]] = []
        def collect_review(review: dict[str, Any]) -> None:
            reviews.append(review)
            payload["review"] = review

        provider = RequiredFieldsGuardProvider(ObservedAnswerProvider(settings, observed_answer), on_review=collect_review)

        def capture(retrieval: Any, evidence: Any, metadata: Any) -> None:
            sources.update(capture_sources(retrieval, evidence))
            payload["preparation"] = {"metadata": metadata, "evidence_count": len(evidence),
                "evidence": [asdict(item) for item in evidence],
                "sources": {key: asdict(value) for key, value in sources.items()},
                "retrieval": asdict(retrieval)}

        result = service.answer_question(session, settings, **options, provider=provider,
                                         rewrite_plan=plan, trace_observer=capture)
        payload["answer"] = service.answer_response_to_dict(result)
        payload["review"] = reviews[0] if reviews else None
        payload["delivery_status"] = reviews[0]["decision"] if reviews else "baseline_preprovider_refusal"
        payload.update(stage="complete", status=result.status)
        return 200, payload, sources
    except (GenerationUnavailableError, GenerationOutputError, VectorIndexUnavailableError, DocumentAccessError, ValueError) as exc:
        code = (503 if isinstance(exc, (GenerationUnavailableError, VectorIndexUnavailableError)) else
                502 if isinstance(exc, GenerationOutputError) else 409 if isinstance(exc, DocumentAccessError) else 400)
        payload.update(status="error", error=str(exc))
        return code, payload, sources


def diagnostic_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
