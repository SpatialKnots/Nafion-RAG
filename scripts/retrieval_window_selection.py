"""Offline-only, finite source-cue selection before a fixed feature cutoff.

Neither lexical qualification nor a same-sentence dependency cue verifies a
scientific relationship. No article metadata or reference outcomes are read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.retrieval import search
from scripts.retrieval_ablation import CUES

VERSION = "retrieval_window_selection_v0.1"
QUALIFIERS = ("body_coverage", "local_relation")
DEPENDENCY = re.compile(
    r"\b(?:depend\w*|affect\w*|influenc\w*|var(?:y|ies|ied|ying)|chang\w*|"
    r"завис\w*|влия\w*|меня\w*|измен\w*)\b",
    re.I,
)
BLOCKERS = {
    "negation": re.compile(r"\b(?:not|no|never|without|не|нет|без)\b", re.I),
    "future_or_proposal": re.compile(r"\b(?:will|would|future|propos\w*|planned|буд\w*|планир\w*|предполага\w*)\b", re.I),
    "mixed_material": re.compile(
        r"\b(?:pbi|pvdf|ptfe|polybenzimidazole|полибензимидазол\w*|"
        r"поливинилиденфторид\w*|another material|other polymer|друг\w* материал\w*)\b",
        re.I,
    ),
}
SENTENCE_BOUNDARY = re.compile(r"[.!?](?=\s|$)|\n\s*\n")


def in_scope(question: str) -> bool:
    text = question.lower().translate(search.LIGATURES)
    return all(re.search(pattern, text) for pattern in CUES)


def sentence_spans(raw: str) -> list[tuple[int, int]]:
    """Raw spans including terminal punctuation; decimal points are not split."""
    spans = []
    start = 0
    for boundary in SENTENCE_BOUNDARY.finditer(raw):
        end = boundary.end()
        if raw[start:end].strip():
            spans.append((start, end))
        start = end
    if raw[start:].strip():
        spans.append((start, len(raw)))
    return spans


def assess_source(raw: str | None) -> dict[str, Any]:
    text = raw or ""
    normalized = text.lower().translate(search.LIGATURES)
    body_matches = [bool(re.search(pattern, normalized)) for pattern in CUES]
    regions = []
    for start, end in sentence_spans(text):
        region = text[start:end]
        view = region.lower().translate(search.LIGATURES)
        matches = [bool(re.search(pattern, view)) for pattern in CUES]
        dependency = bool(DEPENDENCY.search(view))
        # Preserve diagnostics for incomplete regions containing at least one
        # requested cue; they are never silently treated as negative gold.
        if not any(matches):
            continue
        blocked = [name for name, pattern in BLOCKERS.items() if pattern.search(view)]
        if "?" in region:
            blocked.append("question")
        regions.append(
            {
                "start": start,
                "end": end,
                "exact_text": region,
                "cue_matches": matches,
                "dependency_cue": dependency,
                "blockers": blocked,
                "qualified": all(matches) and dependency and not blocked,
            }
        )
    return {
        "body_coverage": all(body_matches),
        "body_cue_matches": body_matches,
        "local_relation": any(region["qualified"] for region in regions),
        "regions": regions,
        "status": "cue_proposal_only; ownership_and_scientific_sufficiency_unverified",
    }


@dataclass(frozen=True)
class Selection:
    results: list[Any]
    metadata: dict[str, Any]


def rerank_window(results: list[Any], bundle: Any, *, window_size: int, qualifier: str) -> Selection:
    if qualifier not in QUALIFIERS:
        raise ValueError("Unknown source qualifier")
    if window_size <= 0:
        raise ValueError("Feature window must be positive")
    if not in_scope(bundle.original):
        baseline = search._rerank_cross_lingual_results(results, bundle, window_size=window_size)
        return Selection(baseline.results, baseline.metadata)
    if len({row.chunk_id for row in results}) != len(results):
        raise ValueError("Duplicate chunk identity in frozen candidates")
    diagnostics = {row.chunk_id: assess_source(row.full_text) for row in results}

    def prioritize(rows: list[Any]) -> list[Any]:
        return sorted(rows, key=lambda row: not diagnostics[row.chunk_id][qualifier])

    legacy = search._legacy_rerank_cross_lingual_results(results, bundle)
    diverse = search._diversify_cross_lingual_results(legacy, preferred_per_article=2)
    ordered = prioritize(diverse)
    window, tail = ordered[:window_size], ordered[window_size:]
    feature = search.feature_rerank_cross_lingual_results(
        window,
        original_query=bundle.original,
        query_language=bundle.language,
        query_variants=[(variant.source, variant.text) for variant in bundle.variants],
    )
    ranked = [*prioritize(feature.results), *tail]
    if len(ranked) != len(results) or {id(row) for row in ranked} != {id(row) for row in results}:
        raise ValueError("Candidate identities changed")
    return Selection(
        ranked,
        {
            **feature.metadata,
            "window_size": window_size,
            "legacy_window_preserved": False,
            "feature_window_selection": VERSION,
            "source_qualifier": qualifier,
            "source_diagnostics": diagnostics,
            "input_chunk_ids": [row.chunk_id for row in results],
            "selected_window_chunk_ids": [row.chunk_id for row in window],
            "qualified_chunk_ids": [row.chunk_id for row in ordered if diagnostics[row.chunk_id][qualifier]],
            "scientific_admission": False,
        },
    )
