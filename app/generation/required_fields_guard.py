"""Explicit whole-answer delivery guard, retaining a separate native review."""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from app.generation.providers import (
    AnswerLanguage,
    AnswerProvider,
    AnswerStyle,
    Evidence,
    GenerationOutputError,
    ProviderResult,
)
from app.generation.required_answer_fields import build, canonical, check

VERSION = "required_fields_delivery_guard_v0.1"


def _present_token(value: str, text: str) -> bool:
    if re.fullmatch(r'\d+(?:[.,]\d+)?', value):
        return bool(re.search(r'(?<![\d.,])' + re.escape(value).replace(r'\.', '[.,]') + r'(?![\d.,])', text))
    return bool(re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', text))


def evaluate(question: str, evidence: list[Evidence], native: ProviderResult) -> dict[str, Any]:
    """Review a saved or live parsed result; performs no provider call or output repair."""
    if type(native.answerable) is not bool or native.answerable != bool(native.claims):
        raise GenerationOutputError("Underlying provider answerable/claims contract mismatch")
    try:
        checked = check(question, native.claims, evidence)
    except ValueError as exc:
        raise GenerationOutputError('Underlying result cannot be bound to guard sources: ' + str(exc)) from exc
    reasons = []
    for row in checked['rows']:
        if row['state'] == 'literal_fields_present_not_semantic_acceptance':
            continue
        if row['state'] == 'missing_required_literal_fields':
            requirement = next(r for r in checked['plan']['requirements'] if r['id'] == row['id'])
            fields = requirement['observations'][0]['fields']
            # Distinguish missing expected tokens from wording outside the finite checker.
            # Neither branch proves a scientific error or that literature lacks the result.
            tokens = [v for k, v in fields.items() if k in {'value', 'component', 'cycles'}]
            text = '\n'.join(c.text for c in native.claims)
            present = bool(tokens) and all(_present_token(v, text) for v in tokens)
            state = 'answer_wording_or_binding_not_recognized' if present else 'required_literal_not_observed'
        elif row['state'] == 'ambiguous_source_candidates':
            state = 'source_candidates_ambiguous'
        else:
            state = 'source_support_not_established_by_finite_grammar'
        reasons.append({'id': row['id'], 'state': state, 'scientific_error_established': False})
    blocked = bool(native.answerable and checked['plan']['status'] == 'mapped' and reasons)
    decision = ('insufficient_confirmation' if blocked else 'provider_abstained' if not native.answerable
                else 'not_evaluated' if checked['plan']['status'] != 'mapped' else 'required_literal_fields_present')
    return {'version': VERSION, 'decision': decision, 'withheld': blocked, 'reasons': reasons,
        'native_result': asdict(native), 'question': question, 'evidence': [asdict(e) for e in evidence], 'check': checked,
        'native_answerable': native.answerable, 'delivered_answerable': native.answerable and not blocked,
        'scientific_support': 'not_evaluated', 'scientific_error_established': False,
        'origin': 'deterministic_experimental_delivery_guard', 'retry_performed': False, 'repair_performed': False}


class RequiredFieldsGuardProvider:
    """An explicit provider decorator; collector is required to retain native review."""

    def __init__(self, provider: AnswerProvider, *, on_review: Callable[[dict[str, Any]], None]) -> None:
        self.provider, self.on_review = provider, on_review

    def generate(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = 'claims',
                 answer_language: AnswerLanguage = 'auto') -> ProviderResult:
        build(question, evidence)  # Input budgets/scopes validated before the one provider invocation.
        original = canonical([question, [asdict(e) for e in evidence]])
        native = self.provider.generate(question, evidence, answer_style=answer_style, answer_language=answer_language)
        if canonical([question, [asdict(e) for e in evidence]]) != original:
            raise GenerationOutputError('Underlying provider changed guard question/evidence')
        reviewed = evaluate(question, evidence, native)
        blocked = reviewed['withheld']  # Callback cannot change the decision or native result.
        self.on_review(deepcopy(reviewed))
        if blocked:
            return ProviderResult(False, [], native.provider, native.model)
        return native
