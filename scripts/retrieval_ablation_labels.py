"""Offline label accounting v0.2, using the repository's existing fixture matcher."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.evaluation.retrieval import _load_extended_expected_articles, _result_matches_extended_article

VERSION = "retrieval_ablation_article_labels_v0.2"


def label_retention(case: dict[str, Any], rows: list[dict[str, Any]], articles: dict[str, Any]) -> dict[str, Any]:
    raw = list(case.get('expected', {}).get('articles', []))
    raw.extend({'doi': value} for value in case.get('expected_article_dois', []))
    raw.extend({'checksum': value} for value in case.get('expected_article_checksums', []))
    raw.extend({'title': value} for value in case.get('expected_article_titles', []))
    targets = _load_extended_expected_articles(raw, case.get('id', 'unlabelled_development_case'))
    if case.get('answerable') is False and targets:
        raise ValueError('A declared negative fixture cannot supply positive article labels')
    checksums = {key: value['original_pdf_sha256'] for key, value in articles.items()}
    matches = sorted({row['article_id'] for row in rows if any(
        _result_matches_extended_article(row, target, checksums) for target in targets)})
    return {'metric_version': VERSION, 'has_existing_positive_article_label': bool(targets),
            'any_expected_article_present': bool(matches) if targets else None, 'matching_article_ids': matches,
            'existing_targets': [asdict(target) for target in targets],
            'scope': 'Existing repository fixture identity matcher; not scientific answer accuracy'}
