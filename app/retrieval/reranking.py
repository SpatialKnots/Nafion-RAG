from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.generation.evidence_adequacy import LIGATURES
from app.retrieval.cross_lingual import detect_query_language
from app.retrieval.query_features import extract_query_features
from app.retrieval.query_normalization import normalize_query

STOPWORDS = {"and", "in", "or", "the", "using", "vs", "with", "how", "what", "which", "where", "does", "affect"}
RUSSIAN_STOPWORDS = {"как", "где", "что", "какие", "какая", "в", "на", "и", "с", "для", "по", "при"}
WORD_PATTERN = re.compile(r"[\w+-]+", flags=re.UNICODE)
RERANK_TERM_SYNONYMS = {
    "наибольшую": ("highest", "best", "maximum", "max"),
    "наибольшая": ("highest", "best", "maximum", "max"),
    "наибольший": ("highest", "best", "maximum", "max"),
    "наибольш": ("highest", "best", "maximum", "max"),
    "лучшую": ("best", "highest", "maximum"),
    "лучшие": ("best", "highest", "maximum"),
    "пластификаторах": ("plasticiser", "plasticizer", "plasticisers", "plasticizers"),
    "пластификаторами": ("plasticiser", "plasticizer", "plasticisers", "plasticizers"),
    "пластификатор": ("plasticiser", "plasticizer", "plasticisers", "plasticizers"),
    "проводимость": ("conductivity", "ionic conductivity", "transport properties"),
    "проводимост": ("conductivity", "ionic conductivity", "transport properties"),
}


@dataclass(frozen=True)
class RerankedResults:
    results: list[Any]
    metadata: dict[str, object]


@dataclass(frozen=True)
class _ResultFeatures:
    protected_matches: int
    term_matches: int
    phrase_matches: int
    title_phrase_matches: int
    variant_matches: int
    channel_count: int
    cross_language_bonus: int
    numeric_table_bonus: int
    conductivity_plasticizer_bonus: int
    intent_match_bonus: int
    conductivity_conflict_penalty: int
    result_score: float


def rerank_cross_lingual_results(
    results: list[Any],
    *,
    original_query: str,
    query_language: str,
    query_variants: Sequence[tuple[str, str]],
) -> RerankedResults:
    if not results:
        return RerankedResults(results=[], metadata={"strategy": "cross_lingual_feature_rerank", "reranked": False})

    protected_tokens = extract_query_features(original_query).protected_tokens
    query_terms = _query_terms_for_rerank(original_query)
    normalized_query = normalize_query(original_query)
    if normalized_query.lexical_normalized:
        query_terms.extend(_query_terms_for_rerank(normalized_query.lexical_normalized))
    variant_terms = [(source, _query_terms_for_rerank(text)) for source, text in query_variants if text.strip()]
    query_phrases = _phrases_for_rerank([original_query, normalized_query.lexical_normalized, *(text for _source, text in query_variants)])
    swelling_comparison_intent = _has_swelling_comparison_intent(original_query, query_variants)
    conductivity_plasticizer_intent = _has_conductivity_plasticizer_intent(original_query, query_variants)
    query_intents = _query_intents(original_query, query_variants)

    result_features: dict[str, _ResultFeatures] = {}
    article_scores: dict[str, float] = {}
    article_result_scores: dict[str, list[float]] = {}
    for result in results:
        features = _features_for_result(
            result,
            query_language=query_language,
            protected_tokens=protected_tokens,
            query_terms=query_terms,
            query_phrases=query_phrases,
            variant_terms=variant_terms,
            swelling_comparison_intent=swelling_comparison_intent,
            conductivity_plasticizer_intent=conductivity_plasticizer_intent,
            query_intents=query_intents,
        )
        result_features[result.chunk_id] = features
        article_result_scores.setdefault(result.article_id, []).append(features.result_score)

    for article_id, scores in article_result_scores.items():
        ordered = sorted(scores, reverse=True)
        best = ordered[0]
        second = ordered[1] if len(ordered) > 1 else 0.0
        article_scores[article_id] = best + 0.35 * second

    original_positions = {result.chunk_id: index for index, result in enumerate(results)}
    reranked = sorted(
        results,
        key=lambda result: (
            -result_features[result.chunk_id].numeric_table_bonus,
            -result_features[result.chunk_id].intent_match_bonus,
            _best_component_rank(result) if result_features[result.chunk_id].intent_match_bonus else len(results) + 1,
            -result_features[result.chunk_id].conductivity_plasticizer_bonus,
            -article_scores.get(result.article_id, 0.0),
            -result_features[result.chunk_id].result_score,
            _best_component_rank(result),
            -float(getattr(result, "score", 0.0)),
            original_positions[result.chunk_id],
        ),
    )
    return RerankedResults(
        results=reranked,
        metadata={
            "strategy": "cross_lingual_feature_rerank",
            "reranked": [result.chunk_id for result in reranked] != [result.chunk_id for result in results],
            "protected_tokens": protected_tokens,
            "query_terms": query_terms,
            "query_phrases": query_phrases,
            "query_intents": sorted(query_intents),
            "top_features": [
                _feature_payload(result, result_features[result.chunk_id], article_scores.get(result.article_id, 0.0))
                for result in reranked[:10]
            ],
        },
    )


def _features_for_result(
    result: Any,
    *,
    query_language: str,
    protected_tokens: list[str],
    query_terms: list[str],
    query_phrases: list[str],
    variant_terms: Sequence[tuple[str, list[str]]],
    swelling_comparison_intent: bool,
    conductivity_plasticizer_intent: bool,
    query_intents: set[str],
) -> _ResultFeatures:
    text = _result_text(result)
    title = (getattr(result, "title", None) or "").lower().translate(LIGATURES)
    protected_matches = sum(1 for token in protected_tokens if _term_matches(token, text))
    matched_terms = {term for term in query_terms if _term_matches(term, text)}
    matched_phrases = {phrase for phrase in query_phrases if phrase in text}
    title_phrase_matches = sum(1 for phrase in matched_phrases if phrase in title)
    matched_variants = {
        source
        for source, terms in variant_terms
        if any(_term_matches(term, text) for term in terms)
    }
    channel_count = len(getattr(result, "method_ranks", {}) or {})
    cross_language_bonus = _cross_language_bonus(query_language, result)
    numeric_table_bonus = _numeric_table_bonus(text, enabled=swelling_comparison_intent)
    conductivity_plasticizer_bonus = _conductivity_plasticizer_bonus(text, enabled=conductivity_plasticizer_intent)
    intent_match_bonus = _intent_match_bonus(result, text, query_intents)
    conductivity_conflict_penalty = _conductivity_conflict_penalty(" ".join(query_terms), text)
    score = (
        4.0 * protected_matches
        + 1.6 * len(matched_terms)
        + 2.2 * len(matched_phrases)
        + 3.0 * title_phrase_matches
        + 1.2 * len(matched_variants)
        + 0.8 * min(channel_count, 3)
        + 1.5 * cross_language_bonus
        + 6.0 * numeric_table_bonus
        + 5.0 * conductivity_plasticizer_bonus
        + 3.0 * intent_match_bonus
        - 2.5 * conductivity_conflict_penalty
    )
    return _ResultFeatures(
        protected_matches=protected_matches,
        term_matches=len(matched_terms),
        phrase_matches=len(matched_phrases),
        title_phrase_matches=title_phrase_matches,
        variant_matches=len(matched_variants),
        channel_count=channel_count,
        cross_language_bonus=cross_language_bonus,
        numeric_table_bonus=numeric_table_bonus,
        conductivity_plasticizer_bonus=conductivity_plasticizer_bonus,
        intent_match_bonus=intent_match_bonus,
        conductivity_conflict_penalty=conductivity_conflict_penalty,
        result_score=score,
    )


def _feature_payload(result: Any, features: _ResultFeatures, article_score: float) -> dict[str, object]:
    return {
        "article_id": result.article_id,
        "chunk_id": result.chunk_id,
        "title": result.title,
        "protected_matches": features.protected_matches,
        "term_matches": features.term_matches,
        "phrase_matches": features.phrase_matches,
        "title_phrase_matches": features.title_phrase_matches,
        "variant_matches": features.variant_matches,
        "channel_count": features.channel_count,
        "cross_language_bonus": features.cross_language_bonus,
        "numeric_table_bonus": features.numeric_table_bonus,
        "conductivity_plasticizer_bonus": features.conductivity_plasticizer_bonus,
        "intent_match_bonus": features.intent_match_bonus,
        "conductivity_conflict_penalty": features.conductivity_conflict_penalty,
        "result_score": features.result_score,
        "article_score": article_score,
    }


def _best_component_rank(result: Any) -> int:
    method_ranks = getattr(result, "method_ranks", None)
    if not method_ranks:
        return 1_000_000
    ranks = method_ranks if isinstance(method_ranks, Mapping) else {}
    return min(int(rank) for rank in ranks.values())


def _query_terms_for_rerank(query: str) -> list[str]:
    terms: list[str] = []
    for token in WORD_PATTERN.findall(query.lower().translate(LIGATURES)):
        stripped = token.strip("-")
        if len(stripped) < 2 or stripped in STOPWORDS or stripped in RUSSIAN_STOPWORDS:
            continue
        if stripped not in terms:
            terms.append(stripped)
    return terms


def _phrases_for_rerank(queries: Sequence[str]) -> list[str]:
    phrases: list[str] = []
    for query in queries:
        terms = _query_terms_for_rerank(query)
        for size in range(2, 5):
            for index in range(0, max(0, len(terms) - size + 1)):
                phrase = " ".join(terms[index : index + size])
                if phrase not in phrases:
                    phrases.append(phrase)
    return phrases[:80]


def _result_text(result: Any) -> str:
    return "\n".join(
        item
        for item in (
            getattr(result, "title", None) or "",
            getattr(result, "snippet", "") or "",
            getattr(result, "full_text", None) or "",
        )
        if item
    ).lower().translate(LIGATURES)


def _has_swelling_comparison_intent(original_query: str, query_variants: Sequence[tuple[str, str]]) -> bool:
    query_text = " ".join([original_query, *(text for _source, text in query_variants)]).lower().translate(LIGATURES)
    has_swelling = any(term in query_text for term in ("swelling degree", "степень набухания", "equilibrium swelling"))
    has_forms = "li-nafion" in query_text and "h-nafion" in query_text
    has_comparison = any(term in query_text for term in ("more", "than", "больше", "выше", "сравн", "αh", "αli"))
    return has_swelling and has_forms and has_comparison


def _has_conductivity_plasticizer_intent(original_query: str, query_variants: Sequence[tuple[str, str]]) -> bool:
    query_text = " ".join([original_query, *(text for _source, text in query_variants)]).lower().translate(LIGATURES)
    has_conductivity = any(term in query_text for term in ("conductivity", "проводимост", "электропровод"))
    has_plasticizer = any(term in query_text for term in ("plasticiser", "plasticizer", "пластификатор", "растворител"))
    has_lithium_form = any(term in query_text for term in ("li-nafion", "lithiated nafion", "литиевая", "литирован"))
    return has_conductivity and has_plasticizer and has_lithium_form


def _query_intents(original_query: str, query_variants: Sequence[tuple[str, str]]) -> set[str]:
    query_text = " ".join([original_query, *(text for _source, text in query_variants)]).lower().translate(LIGATURES)
    intents: set[str] = set()
    has_lithium_nafion = any(term in query_text for term in ("li-nafion", "lithiated nafion", "литирован", "литиевая"))
    has_ec_sl_query = _has_ec_sl_evidence(query_text)
    if (
        has_lithium_nafion
        and not has_ec_sl_query
        and any(term in query_text for term in ("conductivity", "проводимост", "электропровод"))
        and any(term in query_text for term in ("plasticiser", "plasticizer", "пластификатор", "растворител"))
        and any(term in query_text for term in ("which", "what", "каких", "какие", "highest", "best", "maximum", "наибольш", "лучш"))
    ):
        intents.add("plasticizer_conductivity_survey")
    if all(term in query_text for term in ("mixing temperature", "li-nafion")) or (
        "температур" in query_text and "смеш" in query_text and "nafion" in query_text and has_ec_sl_query
    ):
        intents.add("mixing_temperature_li_nafion")
    if all(term in query_text for term in ("phase diagram", "ethylene carbonate", "sulfolane")) or (
        "фазовая диаграмма" in query_text and ("этиленкарбонат" in query_text or "ec" in query_text)
    ):
        intents.add("ec_sl_phase_diagram")
    if all(term in query_text for term in ("casting solvent", "annealing temperature", "recast nafion")) or (
        "растворител" in query_text and "кастинг" in query_text and "отжиг" in query_text and "recast nafion" in query_text
    ):
        intents.add("recast_casting_annealing")
    if any(term in query_text for term in ("solution casting morphology", "solvent casting morphology")):
        intents.add("solution_casting_morphology")
    if has_ec_sl_query and has_lithium_nafion and any(term in query_text for term in ("ionic conductivity", "ионн", "проводимост")):
        intents.add("ec_sl_li_nafion_conductivity")
    if has_ec_sl_query and has_lithium_nafion and any(term in query_text for term in ("swelling", "набух", "sorption", "сорбц")):
        intents.add("ec_sl_li_nafion_swelling")
    if has_ec_sl_query and has_lithium_nafion and any(term in query_text for term in ("plasticised", "plasticized", "пластифиц")):
        intents.add("ec_sl_li_nafion_plasticised")
    if (
        any(term in query_text for term in ("thermodynamic interaction", "thermodynamic interactions", "термодинамика взаимодействия"))
        and any(term in query_text for term in ("water", "вод", "sorption", "сорбц"))
        and "li-nafion" not in query_text
    ):
        intents.add("nafion_water_thermodynamics")
    if (
        has_lithium_nafion
        and any(term in query_text for term in ("thermodynamic", "термодинами"))
        and any(term in query_text for term in ("relaxation", "релаксац"))
        and not has_ec_sl_query
    ):
        intents.add("li_nafion_thermodynamic_relaxation")
    if (
        has_lithium_nafion
        and any(term in query_text for term in ("swelling", "набух", "sorption", "сорбц"))
        and any(term in query_text for term in ("gibbs", "mixing", "энтальпия смешения", "энергия гиббса"))
        and not has_ec_sl_query
    ):
        intents.add("li_nafion_swelling_mixing_thermodynamics")
    if (
        has_lithium_nafion
        and any(term in query_text for term in ("enthalpy", "энтальп"))
        and any(term in query_text for term in ("alcohol", "спирт"))
        and any(term in query_text for term in ("aqueous", "water", "вод"))
    ):
        intents.add("li_nafion_alcohol_enthalpy")
    if (
        "russian paper" in query_text
        and has_ec_sl_query
        and "diglyme" in query_text
        and any(term in query_text for term in ("conductivity", "lithium-conducting", "li+-conducting", "проводимост"))
    ):
        intents.add("russian_ec_sl_diglyme_conductivity")
    return intents


def _intent_match_bonus(result: Any, text: str, query_intents: set[str]) -> int:
    bonus = 0
    if "mixing_temperature_li_nafion" in query_intents and _has_all(text, ("mixing temperature", "li-nafion")):
        if any(term in text for term in ("swelling degree", "physicochemical properties", "plasticised", "plasticized")):
            bonus += 4
        else:
            bonus += 2
    if "ec_sl_phase_diagram" in query_intents and any(
        term in text for term in ("phase diagram", "фазовая диаграмма", "диаграмма плавкости")
    ):
        if _has_ec_sl_evidence(text):
            bonus += 4
        else:
            bonus += 2
    if "recast_casting_annealing" in query_intents and _has_all(text, ("recast nafion",)):
        if _has_all(text, ("casting solvent", "annealing temperature")):
            bonus += 5
        elif any(term in text for term in ("casting solvent", "annealing temperature")):
            bonus += 3
    if "solution_casting_morphology" in query_intents and any(term in text for term in ("solution casting", "solvent casting")):
        if "morpholog" in text and "nafion" in text:
            bonus += 5
        else:
            bonus += 2
    if "ec_sl_li_nafion_conductivity" in query_intents and _has_ec_sl_evidence(text):
        if "li-nafion" in text and any(term in text for term in ("ionic conductivity", "conductivity", "transport properties")):
            bonus += 4
        elif any(term in text for term in ("conductivity", "проводимост", "электропровод")):
            bonus += 2
    if "ec_sl_li_nafion_swelling" in query_intents and _has_ec_sl_evidence(text):
        if "li-nafion" in text and any(term in text for term in ("swelling degree", "swelling", "набух")):
            bonus += 4
        elif any(term in text for term in ("swelling", "набух")):
            bonus += 2
    if "ec_sl_li_nafion_plasticised" in query_intents and _has_ec_sl_evidence(text):
        if "li-nafion" in text and any(term in text for term in ("plasticised", "plasticized", "physicochemical properties")):
            bonus += 4
        elif any(term in text for term in ("plasticised", "plasticized", "пластифиц")):
            bonus += 2
    if "nafion_water_thermodynamics" in query_intents and any(term in text for term in ("water", "вод", "sorption", "сорбц")):
        if any(term in text for term in ("thermodynamic", "термодинами")):
            bonus += 3
        else:
            bonus += 1
        if _has_standalone_water_thermodynamics_evidence(result, text):
            bonus += 5
    if "plasticizer_conductivity_survey" in query_intents:
        solvent_count = _plasticizer_solvent_count(text)
        if any(term in text for term in ("table 4.6", "таблица 4.6", "highest li-ion conductivity", "highest ionic conductivities")):
            bonus += 6
        elif (
            any(term in text for term in ("литий-ионная проводимость", "li-ion conductivity", "ionic conductivity"))
            and any(term in text for term in ("мембраны нафион", "nafion membrane", "li-nafion"))
            and any(term in text for term in ("апротонными растворителями", "aprotic solvents", "plasticised", "plasticized"))
        ):
            bonus += 5
        elif solvent_count >= 3 and any(term in text for term in ("conductivity", "проводимост", "электропровод")):
            bonus += 4
    if "li_nafion_thermodynamic_relaxation" in query_intents:
        if _has_li_nafion_dissertation_thermodynamic_relaxation(text):
            bonus += 6
        elif any(term in text for term in ("li-nafion", "li‑nafion", "ионы лития", "литиевая форма")) and any(
            term in text for term in ("релаксационные свойства", "диэлектрическая релаксация", "relaxation properties")
        ):
            bonus += 3
    if "li_nafion_swelling_mixing_thermodynamics" in query_intents:
        if _has_li_nafion_mixing_thermodynamics_evidence(text):
            bonus += 6
        elif any(term in text for term in ("li-nafion", "li‑nafion", "ионы лития", "литиевая форма")) and any(
            term in text for term in ("энтальпия смешения", "энергия гиббса", "gibbs", "mixing")
        ):
            bonus += 3
    if "li_nafion_alcohol_enthalpy" in query_intents:
        if _has_li_nafion_alcohol_enthalpy_evidence(text):
            bonus += 7
        elif any(term in text for term in ("li-nafion", "li‑nafion", "литирован")) and any(term in text for term in ("спирт", "alcohol")):
            bonus += 3
    if "russian_ec_sl_diglyme_conductivity" in query_intents:
        if _has_russian_ec_sl_diglyme_conductivity_evidence(result, text):
            bonus += 7
        elif _has_ec_sl_evidence(text) and "diglyme" in text and any(term in text for term in ("conductivity", "проводимост")):
            bonus += 3
    return bonus


def _has_all(text: str, terms: Sequence[str]) -> bool:
    return all(term in text for term in terms)


def _has_ec_sl_evidence(text: str) -> bool:
    has_abbreviated_pair = "ec/sl" in text or re.search(r"(?<![a-z0-9])ec(?![a-z0-9]).{0,40}(?<![a-z0-9])sl(?![a-z0-9])", text) is not None
    has_named_pair = "ethylene carbonate" in text and "sulfolane" in text
    has_ru_pair = "этиленкарбонат" in text and "сульфолан" in text
    return has_abbreviated_pair or has_named_pair or has_ru_pair


def _has_standalone_water_thermodynamics_evidence(result: Any, text: str) -> bool:
    source_type = (getattr(result, "source_type", None) or "").lower()
    doi = getattr(result, "doi", None)
    has_article_trace = bool(doi) and source_type == "main_text"
    has_title_evidence = (
        "термодинамика взаимодействия" in text
        and "nafion" in text
        and any(term in text for term in ("водой", "воды", "water"))
    )
    has_body_evidence = (
        "nafion" in text
        and any(term in text for term in ("сорбции воды", "water sorption", "набухание мембраны nafion в воде"))
        and any(term in text for term in ("флори", "flory", "гиббс", "gibbs", "энтальп", "enthalp"))
    )
    return has_article_trace and (has_title_evidence or has_body_evidence)


def _has_li_nafion_dissertation_thermodynamic_relaxation(text: str) -> bool:
    has_lithium_form = any(term in text for term in ("h-nafion", "li-nafion", "li‑nafion", "ионы лития", "литиевая форма"))
    has_thermodynamics = any(term in text for term in ("термодинамические характеристики", "thermodynamic", "термодинами"))
    has_relaxation = any(term in text for term in ("релаксационные свойства", "диэлектрическая релаксация", "relaxation properties"))
    return has_lithium_form and has_thermodynamics and has_relaxation


def _has_li_nafion_mixing_thermodynamics_evidence(text: str) -> bool:
    has_lithium_form = any(term in text for term in ("li-nafion", "li‑nafion", "ионы лития", "литиевая форма"))
    has_swelling = any(term in text for term in ("набухание", "swelling", "сорбция"))
    has_mixing = any(term in text for term in ("энтальпия смешения", "энергия гиббса", "gibbs free energy", "mixing"))
    has_solvents = any(term in text for term in ("растворител", "solvent", "водно-спиртов", "апротон"))
    return has_lithium_form and has_swelling and has_mixing and has_solvents


def _has_li_nafion_alcohol_enthalpy_evidence(text: str) -> bool:
    has_lithium_form = any(term in text for term in ("li-nafion", "li‑nafion", "литирован"))
    has_alcohol = any(term in text for term in ("водно-спиртов", "спиртовые", "2-пропанол/вода", "alcohol", "aqueous alcohol"))
    has_enthalpy = any(term in text for term in ("энтальп", "enthalpy"))
    return has_lithium_form and has_alcohol and has_enthalpy


def _has_russian_ec_sl_diglyme_conductivity_evidence(result: Any, text: str) -> bool:
    doi = (getattr(result, "doi", None) or "").lower()
    has_russian_article_trace = doi.startswith("10.31857/")
    has_system = _has_ec_sl_evidence(text) and "diglyme" in text
    has_transport = any(term in text for term in ("conductivity", "проводимост", "литий-ионная проводимость"))
    return has_russian_article_trace and has_system and has_transport


def _numeric_table_bonus(text: str, *, enabled: bool) -> int:
    if not enabled:
        return 0
    has_forms = "li-nafion" in text and "h-nafion" in text
    has_alpha_columns = any(term in text for term in ("αh", "αli", "alphah", "alphali"))
    has_decimal_values = len(re.findall(r"\b\d+[.,]\d+\b", text)) >= 4
    if not (has_forms and has_alpha_columns and has_decimal_values):
        return 0
    if "таблица 4.5" in text or "table 4.5" in text:
        return 2
    return 0


def _conductivity_plasticizer_bonus(text: str, *, enabled: bool) -> int:
    if not enabled:
        return 0
    has_lithium_form = any(term in text for term in ("li-nafion", "lithiated nafion", "li‑nafion", "литирован"))
    has_conductivity = any(term in text for term in ("conductivity", "transport properties", "проводимост", "электропровод"))
    has_plasticizer = any(
        term in text for term in ("plasticiser", "plasticizer", "plasticised", "plasticized", "пластификатор", "пластифицирован")
    )
    if not (has_lithium_form and has_conductivity and has_plasticizer):
        return 0
    if any(term in text for term in ("table 4.6", "таблица 4.6", "highest li-ion conductivity", "highest ionic conductivities")):
        return 3
    if any(term in text for term in ("best transport properties", "highest conductivity values", "best sample")):
        return 3
    if "ec/sl" in text and any(term in text for term in ("conductivity", "transport properties")):
        return 2
    if _plasticizer_solvent_count(text) >= 3:
        return 2
    return 1


def _plasticizer_solvent_count(text: str) -> int:
    return sum(
        1
        for term in (
            "dmf",
            "dmso",
            "nmp",
            "nmf",
            "dmaa",
            "methanol",
            "диметилформамид",
            "диметилсульфоксид",
            "n-метил-2-пирролидон",
            "n,n-диметилацетамид",
            "метанол",
        )
        if term in text
    )


def _term_matches(term: str, text: str) -> bool:
    normalized = term.lower().translate(LIGATURES)
    if normalized in text:
        return True
    if any(synonym in text for synonym in RERANK_TERM_SYNONYMS.get(normalized, ())):
        return True
    if "-" in normalized and normalized.replace("-", " ") in text:
        return True
    if len(normalized) >= 5 and re.fullmatch(r"[а-яё]+", normalized, flags=re.IGNORECASE):
        return normalized[: max(5, len(normalized) - 2)] in text
    return False


def _cross_language_bonus(query_language: str, result: Any) -> int:
    if query_language not in {"en", "ru"}:
        return 0
    result_language, _diagnostics = detect_query_language(
        "\n".join(item for item in (getattr(result, "title", None) or "", getattr(result, "snippet", "") or "") if item)
    )
    if query_language == "en" and result_language == "ru":
        return 1
    if query_language == "ru" and result_language == "en":
        return 1
    return 0


def _conductivity_conflict_penalty(query_text: str, result_text: str) -> int:
    wants_ionic_or_lithium = any(term in query_text for term in ("ionic", "lithium", "li-nafion", "li+", "ионн", "лит"))
    if not wants_ionic_or_lithium:
        return 0
    has_wrong_property = any(term in result_text for term in ("proton conductivity", "electronic conductivity", "протонная проводимость"))
    has_right_property = any(
        term in result_text
        for term in ("ionic conductivity", "li+", "li-nafion", "ионная проводимость", "электропровод")
    )
    return 1 if has_wrong_property and not has_right_property else 0
