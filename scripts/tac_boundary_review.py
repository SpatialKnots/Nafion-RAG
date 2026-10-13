"""Validate source-bound development boundary assessments; never infer review decisions."""

from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA = "tac_boundary_review_v0.1"
LABELS = {
    "pass": "Границы: без замечаний агента",
    "boundary_error": "Ошибка границ",
    "missed": "Пропуск",
    "not_separately_delimited": "Отдельный раздел не выделен в проверенной структуре",
    "unresolved": "Не определено",
}
KINDS = ("T", "A", "C")


def validate_review(
    snapshot: dict[str, Any], profiles: dict[str, Any], review: dict[str, Any], profiles_sha256: str,
) -> dict[str, dict[str, Any]]:
    """Reject stale, incomplete or internally inconsistent development annotations.

    Integrity checks cannot establish that a reviewer actually inspected a page or
    that their judgment is scientifically correct. Original files/images are
    checksum-verified by the local audit recipe, not by this pure-data validator.
    """
    if review.get("schema") != SCHEMA:
        raise ValueError("Unsupported boundary review schema")
    if review.get("independent") is not False or review.get("human_confirmation") != "pending":
        raise ValueError("Boundary review must remain an unconfirmed development audit")
    if review.get("reviewer") != "assistant_development_audit" or not isinstance(review.get("policy"), dict):
        raise ValueError("Boundary review reviewer/policy missing")
    if review.get("snapshot_sha256") != profiles["snapshot_sha256"] or review.get("profiles_sha256") != profiles_sha256:
        raise ValueError("Boundary review input hash mismatch")
    articles = {a["article_id"]: a for a in snapshot["articles"]}
    predicted = {p["article_id"]: p for p in profiles["profiles"]}
    records = review.get("articles", [])
    annotations = {a["article_id"]: a for a in records}
    if len(annotations) != len(records) or set(annotations) != set(articles) or set(predicted) != set(articles):
        raise ValueError("Boundary review inventory mismatch")
    for identifier, record in annotations.items():
        article, profile = articles[identifier], predicted[identifier]
        if record.get("original_pdf_sha256") != article["original_pdf_sha256"]:
            raise ValueError("Boundary review PDF checksum mismatch")
        reviewed = record.get("reviewed_pages", [])
        page_numbers = [p["page"] for p in reviewed]
        sources = {p["page"]: p for p in article["pages"]}
        if not reviewed or len(set(page_numbers)) != len(page_numbers):
            raise ValueError("Boundary review pages missing or duplicated")
        for page in reviewed:
            source = sources.get(page["page"])
            if source is None or any(page.get(k) != source[k] for k in ("layer", "layer_id", "text_sha256")):
                raise ValueError("Boundary review page source mismatch")
            if not isinstance(page.get("image"), str) or not page["image"] or not isinstance(page.get("image_sha256"), str):
                raise ValueError("Boundary review render identity missing")
        assessments = record.get("assessments", {})
        if set(assessments) != set(KINDS):
            raise ValueError("Boundary review must assess T/A/C explicitly")
        for kind, assessment in assessments.items():
            status = assessment.get("status")
            if status not in LABELS or not isinstance(assessment.get("note"), str) or not assessment["note"].strip():
                raise ValueError("Boundary review status/note invalid")
            expected = [s for s in profile["sections"] if s["kind"] == kind]
            if assessment.get("proposals") != expected:
                raise ValueError("Boundary review proposals differ from frozen output")
            if any(s["page"] not in page_numbers for s in expected):
                raise ValueError("Boundary review lacks a proposed page")
            if status in {"pass", "boundary_error"} and not expected:
                raise ValueError("Boundary review cannot pass or bound an absent proposal")
            if status in {"missed", "not_separately_delimited"} and expected:
                raise ValueError("Boundary review missing-section status conflicts with proposal")
    return annotations


def review_counts(review: dict[str, Any]) -> dict[str, Any]:
    """Keep every record and slot; disclose structural exclusions separately."""
    by_kind = {
        k: dict(Counter(a["assessments"][k]["status"] for a in review["articles"])) for k in KINDS
    }
    total = Counter(s["status"] for a in review["articles"] for s in a["assessments"].values())
    slots = len(review["articles"]) * len(KINDS)
    return {"by_kind": by_kind, "total": dict(total), "slots": slots,
            "applicable_slots": slots - total["not_separately_delimited"], "independent": False}
