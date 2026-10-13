"""Derived review views; original proposal/source records never get overwritten."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.terms.classification import category_members


def project_review(base: dict[str, Any], decisions: dict[str, dict[str, Any]], sid: str,
                   cutoff: int, mode: str = "effective") -> dict[str, Any]:
    if mode not in {"effective", "proposals", "reviewed"}:
        raise ValueError("Unknown Terms review view")
    graph = deepcopy(base)
    graph.update(schema="tac_terms_graph_v0.3", state="local_review_overlay")
    graph["review"] = {"snapshot_id": sid, "revision_cutoff": cutoff, "mode": mode,
                       "decisions": decisions, "independent_acceptance": False}
    for axis in graph["taxonomy"]["categories"]:
        graph["taxonomy"]["categories"][axis].update(review_rejected="Назначение отклонено", unreviewed="Без решения",
                                                    term_rejected="Term отклонён по релевантности")
    for article in graph["articles"]:
        memberships: dict[str, dict[str, set[str]]] = {}
        by_group: dict[str, dict[str, list[dict[str, Any]]]] = {axis: {} for axis in ("type", "role", "origin")}
        for assignment in article["assignments"]:
            event = decisions.get(f"classification:{assignment['assignment_id']}")
            relevance = decisions.get(f"relevance:{assignment['term_id']}")
            assignment["review_decision"] = event
            if mode != "proposals" and relevance and relevance["effective_action"] == "reject":
                categories = {"term_rejected"}
            elif mode == "proposals" or not event:
                categories = {"unreviewed"} if mode == "reviewed" else category_members(assignment)
            elif event["effective_action"] in {"confirm", "correct"}:
                categories = set(event["categories"])
            else:
                categories = {"review_rejected" if event["effective_action"] == "reject" else "unclassified"}
            axis = assignment["axis"]
            for category in categories:
                memberships.setdefault(assignment["term_id"], {}).setdefault(axis, set()).add(category)
                by_group[axis].setdefault(category, []).append(assignment)
        for axis, labels in graph["taxonomy"]["categories"].items():
            order = [g["category"] for g in article["category_groups"][axis]]
            order.extend(category for category in labels if category not in order)
            article["category_groups"][axis] = []
            for category in order:
                label = labels[category]
                matches = by_group[axis].get(category, [])
                term_ids = {a["term_id"] for a in matches}
                article["category_groups"][axis].append({"id": f"{axis}:{article['article_id']}:{category}", "kind": category,
                    "category": category, "label": label, "axis": axis, "filters": {axis: category}, "sort": "rank",
                    "term_ids": [t["term_id"] for t in article["terms"] if t["term_id"] in term_ids],
                    "use_ids": sorted({a["use_id"] for a in matches}), "count": len(term_ids)})
        for term in article["terms"]:
            term["memberships"] = {axis: sorted(values) for axis, values in memberships[term["term_id"]].items()}
            term["relevance_decision"] = decisions.get(f"relevance:{term['term_id']}")
    return graph


def review_queue(graph: dict[str, Any], decisions: dict[str, dict[str, Any]], axis: str = "type",
                 state: str = "conflicts") -> list[dict[str, Any]]:
    if axis not in {"type", "role", "origin"} or state not in {"conflicts", "unknown", "all"}:
        raise ValueError("Unknown Terms review queue filter")
    result = []
    for article in graph["articles"]:
        for term in article["terms"]:
            assignments = [a for a in article["assignments"] if a["term_id"] == term["term_id"] and a["axis"] == axis
                           and (not decisions.get(f"classification:{a['assignment_id']}")
                                or decisions[f"classification:{a['assignment_id']}"]["effective_action"] == "uncertain")]
            conflicts = [a for a in assignments if a["state"] == "unresolved"]
            unknown = [a for a in assignments if a["state"] == "unclassified"]
            matches = conflicts if state == "conflicts" else unknown if state == "unknown" else assignments
            if matches:
                result.append({"article_id": article["article_id"], "term_id": term["term_id"], "label": term["label"],
                               "title": article["title"], "assignment_ids": [a["assignment_id"] for a in matches],
                               "priority": 0 if conflicts else 1 if unknown else 2})
    return sorted(result, key=lambda r: r["priority"])
