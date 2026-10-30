"""Sparse preliminary relation comparison; no closed-world negative assumptions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

VERSION = "real_relation_evaluation_v0.1"


def compare_relations(text: str, annotation: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    nodes = graph["nodes"]
    for node in nodes:
        span = node["span"]
        if not 0 <= span["start"] < span["end"] <= len(text) or text[span["start"]:span["end"]] != span["text"]:
            raise ValueError("Graph node differs from exact input")
    if [n["id"] for n in nodes] != list(range(len(nodes))):
        raise ValueError("Expected contiguous graph node IDs")
    proposals = [(i, a) for i, a in enumerate(graph["attempts"]) if a["state"] == "dependency_proposal_unverified"]
    for _, edge in proposals:
        if not 0 <= edge["parent"] < edge["child"] < len(nodes):
            raise ValueError("Invalid directed graph dependency")
    reviewed_proposals: set[int] = set()
    rows: dict[str, list[dict[str, Any]]] = {}
    for field in ("required_dependencies", "forbidden_measurement_context_dependencies"):
        result = []
        for relation in annotation[field]:
            aligned = []
            for role in ("parent", "child"):
                span = relation[role]
                if not 0 <= span["start"] < span["end"] <= len(text) or text[span["start"]:span["end"]] != span["text"]:
                    raise ValueError("Annotation anchor differs from exact input")
                aligned.append([n["id"] for n in nodes if n["span"]["start"] <= span["start"]
                                and span["end"] <= n["span"]["end"]])
            if any(len(ids) != 1 for ids in aligned) or aligned[0] == aligned[1]:
                result.append({"reference": relation, "state": "unmappable_reference_not_scored", "aligned_unit_ids": aligned})
                continue
            parent, child = aligned[0][0], aligned[1][0]
            matches = [i for i, edge in proposals if edge["parent"] == parent and edge["child"] == child]
            reviewed_proposals.update(matches)
            if field == "required_dependencies":
                state = "matched_preliminary_reference" if matches else "missed_preliminary_reference"
            else:
                state = "forbidden_measurement_context_proposed" if matches else "forbidden_measurement_context_not_proposed"
            result.append({"reference": relation, "state": state, "aligned_unit_ids": [parent, child], "proposal_ids": matches})
        rows[field] = result
    return {"version": VERSION, **rows, "proposal_count": len(proposals),
            "unannotated_proposal_ids": [i for i, _ in proposals if i not in reviewed_proposals],
            "unannotated_pairs": "not_assumed_negative", "independent_accuracy": None,
            "scientific_answer_evaluation": "not_performed"}


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    required = [r for case in results for r in case["required_dependencies"]]
    forbidden = [r for case in results for r in case["forbidden_measurement_context_dependencies"]]
    return {"cases": len(results), "required_references": len(required),
            "matched_preliminary_references": sum(r["state"] == "matched_preliminary_reference" for r in required),
            "missed_preliminary_references": sum(r["state"] == "missed_preliminary_reference" for r in required),
            "unmappable_required_references": sum(r["state"] == "unmappable_reference_not_scored" for r in required),
            "forbidden_measurement_context_references": len(forbidden),
            "forbidden_context_violations": sum(r["state"] == "forbidden_measurement_context_proposed" for r in forbidden),
            "unmappable_forbidden_references": sum(r["state"] == "unmappable_reference_not_scored" for r in forbidden),
            "unannotated_proposals": sum(len(c["unannotated_proposal_ids"]) for c in results),
            "cases_without_proposal": sum(c["proposal_count"] == 0 for c in results),
            "independent_accuracy": None, "scientific_answer_evaluation": "not_performed"}
