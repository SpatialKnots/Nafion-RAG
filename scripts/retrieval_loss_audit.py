"""Explicit source-anchor retention in captured retrieval stages; no scientific inference."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

VERSION = "retrieval_loss_audit_v0.1"


def anchor_presence(
    rows: Sequence[dict[str, Any]], *, article_id: str, page_number: int, exact_text: str,
) -> dict[str, Any]:
    """Page-range overlap alone does not establish that an anchor is in a chunk."""
    if not exact_text.strip() or page_number < 1:
        raise ValueError("A nonblank exact anchor and positive page number are required")
    covering, containing = [], []
    for rank, row in enumerate(rows, 1):
        if row["article_id"] != article_id or not row["page_start"] <= page_number <= row["page_end"]:
            continue
        item = {"chunk_id": row["chunk_id"], "rank": rank, "text_layer": row.get("text_layer", "unknown")}
        covering.append(item)
        # Only the actual full source/evidence text counts, never a snippet/title.
        source = row.get("full_text") if "full_text" in row else row.get("text")
        if isinstance(source, str) and exact_text in source:
            containing.append(item)
    return {"page_range_matches": covering, "exact_anchor_matches": containing,
            "anchor_present": bool(containing)}


def retention_path(
    stages: Sequence[dict[str, Any]], *, article_id: str, page_number: int, exact_text: str,
) -> list[dict[str, Any]]:
    """Report ordered observations. Branched channels must be analysed separately."""
    names = [stage["name"] for stage in stages]
    if len(names) != len(set(names)):
        raise ValueError("Stage names must be unique within a declared path")
    output = []
    previous = None
    for stage in stages:
        presence = anchor_presence(stage["results"], article_id=article_id, page_number=page_number, exact_text=exact_text)
        present = presence["anchor_present"]
        transition = "initial" if previous is None else "retained" if present == previous else "entered" if present else "lost"
        output.append({"name": stage["name"], "count": len(stage["results"]), **presence, "transition": transition})
        previous = present
    return output
