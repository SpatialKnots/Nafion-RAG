"""Section-boundary correction; preserve measured v0.5 and immutable v0.4."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from scripts import source_reference_chains as v5

VERSION = "source_reference_chains_v0.6"
HEADING = re.compile(
    r"^[ \t■#*]*(?:\d+(?:\.\d+)*\.?\s+)?(?:"
    r"(?i:experimental(?:\s+section)?|results(?:\s+and\s+discussion)?|discussion|methods|conclusions|"
    r"экспериментальн\w*(?:\s+часть)?|результаты(?:\s+и\s+обсуждение)?|методы|выводы)"
    r"|[A-Z][A-Z0-9 /_-]{3,}|[А-ЯЁ][А-ЯЁ0-9 /_-]{3,})[ \t]*$", re.M,
)


def audit(question: str, sources: list[dict[str, Any]], *, baseline_adequate: bool) -> dict[str, Any]:
    result = v5.audit(question, sources, baseline_adequate=baseline_adequate)
    result["version"] = VERSION
    paths, groups = [], {}
    for graph in result["chain_sources"]:
        retained, rejected = [], []
        for path in graph["paths"]:
            headings = []
            for hop in path["hops"]:
                span = hop["span"]
                headings.extend({"start": span["start"] + m.start(), "end": span["start"] + m.end(), "text": m.group()}
                                for m in HEADING.finditer(span["text"]))
            if headings:
                rejected.append({"path": path, "heading_spans": headings, "diagnostics": ["section_heading_blocks_inheritance"]})
            else:
                retained.append(path)
        graph["paths"] = retained
        graph["heading_rejections"] = rejected
        linked = {(h["reference_span"]["start"], h["reference_span"]["end"]) for p in retained for h in p["hops"]}
        for ref in graph["references"]:
            was_linked = ref["linked"]
            ref["linked"] = (ref["span"]["start"], ref["span"]["end"]) in linked
            if was_linked and not ref["linked"]:
                ref["diagnostics"].append("section_heading_blocks_inheritance")
        for index, path in enumerate(retained):
            address = {"evidence_index": graph["evidence_index"], "path_index": index}
            paths.append({**address, "complete_chain_roles": path["complete_chain_roles"],
                          "textual_requirements_met": path["textual_requirements_met"], "scientific_admission": False})
            digest = hashlib.sha256("\0".join([path["declaration"]["span"]["text"],
                                               *[h["span"]["text"] for h in path["hops"]]]).encode()).hexdigest()
            groups.setdefault(digest, []).append(address)
    result.update(source_chains=paths,
                  chain_textual_requirements_met=any(p["textual_requirements_met"] for p in paths)
                  if result["requirements"]["in_scope"] else None,
                  exact_chain_groups=[{"raw_chain_sha256": digest, "addresses": addresses} for digest, addresses in groups.items()])
    return result
