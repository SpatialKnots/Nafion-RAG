"""Offline counterexamples for lexical gate proposals; never a runtime override.

An accepted lexical probe is not a scientific confirmation. Variants temporarily
replace only the existing matcher dictionaries and always restore them. They are
not installed in the application and cannot dispatch an answer provider here.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.generation import evidence_adequacy as gate

VERSION = "lithiation_gate_audit_v0.1"
VARIANTS = ("baseline", "noun_alias_only", "drop_question_words_only", "alias_and_drop")
QUESTION = "Какие существуют методики литирования Nafion?"

# Deliberately minimal proposals to test, not a Russian morphology dictionary.
NOUN_ALIAS = {"литирования": ["литирование"]}
DROP_WORDS = {"существуют", "методики"}


@contextmanager
def variant_scope(variant: str) -> Iterator[None]:
    if variant not in VARIANTS:
        raise ValueError(f"Unknown offline gate variant: {variant}")
    synonyms = {**gate.DOMAIN_TERM_SYNONYMS}
    common = set(gate.COMMON_QUERY_TERMS)
    if variant in {"noun_alias_only", "alias_and_drop"}:
        synonyms.update(NOUN_ALIAS)
    if variant in {"drop_question_words_only", "alias_and_drop"}:
        common.update(DROP_WORDS)
    with patch.object(gate, "DOMAIN_TERM_SYNONYMS", synonyms), patch.object(gate, "COMMON_QUERY_TERMS", common):
        yield


def probe(
    question: str, texts: Sequence[str], variant: str,
    *, concept_terms: dict[str, dict[str, list[str]]] | None = None,
) -> dict[str, Any]:
    """Consume source text only, with no case labels, provider, DB or retrieval."""
    with variant_scope(variant):
        return asdict(gate.assess_evidence_adequacy(
            question, [SimpleNamespace(text=text) for text in texts], concept_terms=concept_terms,
        ))


def source_occurrences(text: str) -> list[dict[str, Any]]:
    """Locate exact source surfaces without replacing the stored source text."""
    import re

    return [{"start": match.start(), "end": match.end(), "exact_text": match.group(),
             "query_surface": query, "source_surface": surface}
            for query, alternatives in NOUN_ALIAS.items()
            for surface in [query, *alternatives]
            for match in re.finditer(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", text, re.IGNORECASE)]


def constructed_controls() -> list[dict[str, Any]]:
    # All labels are assistant-authored counterexample intent, not independent
    # scientific annotation. No labels enter probe() or the application matcher.
    values = [
        ("affirmative_other_form", ["Nafion. Проводили литирование ионным обменом в водном растворе LiOH."],
         "affirmative_operation_cue"),
        ("affirmative_exact_form", ["Nafion. Для литирования использовали водный раствор LiOH."],
         "affirmative_operation_cue"),
        ("no_operation", ["Nafion membrane conductivity was measured."], "no_lithiation_description"),
        ("negated_other_form", ["Nafion. Литирование не проводили."], "explicit_nonperformance"),
        ("negated_exact_form", ["Nafion. Литирования не проводили."], "explicit_nonperformance"),
        ("heading_only", ["Литирование Nafion."], "heading_without_procedure"),
        ("future_only", ["В будущем планируется литирование Nafion."], "future_not_performed"),
        ("different_material", ["Проводили литирование полиэтилена. Nafion использовали без обработки."],
         "different_material_operation"),
        ("split_fragments", ["Nafion membrane.", "Проводили литирование полиэтилена."],
         "no_same_fragment_material_operation"),
        ("protonation_only", ["Nafion протонировали раствором HCl и промывали водой."], "different_operation"),
    ]
    return [{"id": case_id, "question": QUESTION, "texts": texts, "constructed_intent": intent,
             "annotation_origin": "assistant_constructed_development_control_not_independent_gold",
             "variants": {variant: probe(QUESTION, texts, variant) for variant in VARIANTS}}
            for case_id, texts, intent in values]
