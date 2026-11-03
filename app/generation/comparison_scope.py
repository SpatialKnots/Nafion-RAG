"""Finite source scope for swelling transitions and conductivity superlatives."""

from __future__ import annotations

import re
from typing import Any


def swelling_transition(question: str) -> bool:
    text = question.casefold()
    swelling = "набухани" in text or "swelling" in text
    forms = (("протонирован" in text and "литирован" in text)
             or ("protonated" in text and "lithiated" in text)
             or ("h-nafion" in text and "li-nafion" in text))
    change = any(term in text for term in ("меня", "измен", "переход", "change", "transition", "compare"))
    return bool(swelling and forms and change and re.search(r"\b(?:nafion|нафион)\b", text))


def transition_constraints(question: str) -> list[str]:
    allowed = set((
        "покажи как меняется меняются изменение изменяется изменяются насколько степень степени набухания "
        "мембраны мембран мембрана нафион nafion пре при переходе переход от протонированной протонированная "
        "протонной к литированной литированная литиевой формы форме форм сравнение сравнить по сравнению "
        "в растворителях разных для h li show how does swelling degree change changes transition from protonated "
        "to lithiated form forms h nafion li membrane membranes when changing compare comparison"
    ).split())
    return sorted(set(re.findall(r"[a-zа-яё0-9]+", question.casefold())) - allowed)


def conductivity_superlative(question: str) -> dict[str, Any] | None:
    text = question.casefold()
    relevant = (re.search(r"(?:li[-‑–]nafion|литирован\w*\s+nafion)", text)
                and re.search(r"смес\w*|mixture\w*|blend\w*", text)
                and re.search(r"проводимост\w*|conductivit\w*", text)
                and re.search(r"наилучш\w*|лучш\w*|максимальн\w*|best|highest|maximum", text))
    if not relevant:
        return None
    # Selected top-k fragments cannot establish a corpus/literature optimum.
    # Scoped optimal-composition/temperature extraction is not implemented;
    # an explicit question scope alone must not be mistaken for source support.
    return {"version": "conductivity_best_scope_v0.1", "eligible": False,
            "reason": "conductivity_optimum_not_verified_for_comparable_scope",
            "required": ["comparison_universe", "same_material_form", "composition_at_optimum", "temperature_basis"],
            "scope": "selected_fragments_not_complete_literature", "winner_established": False,
            "scoped_optimum_extraction": "not_implemented"}
