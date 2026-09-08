"""Replay saved grouping windows through snippet and selected-full-text adequacy.

Run before and after a gate change with distinct output paths. No retrieval or
external generation is performed. The database must match the snapshot corpus.
"""

import argparse
import hashlib
import json
from dataclasses import asdict, fields
from pathlib import Path
from types import SimpleNamespace

from app.db.models import Chunk
from app.db.session import SessionLocal
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.evidence_selection import select_answer_evidence
from app.generation.service import _cross_lingual_matched_concepts, _cross_lingual_selection_queries, _evidence_from_response
from app.retrieval.cross_lingual import glossary_terms_for_concepts
from app.retrieval.search import SearchResponse, SearchResult

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("snapshots", nargs="+", type=Path)
parser.add_argument("--baseline", type=Path)
args = parser.parse_args()
report = {"inputs": {}, "records": []}
allowed = {field.name for field in fields(SearchResult)}
with SessionLocal() as session:
    for path in args.snapshots:
        report["inputs"][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        for method, data in snapshot["methods"].items():
            for record in data["questions"]:
                row = record["variants"]["flat"]
                results = []
                for payload in row["results"]:
                    chunk = session.get(Chunk, payload["chunk_id"])
                    if chunk is None:
                        raise ValueError(f"Snapshot chunk missing: {payload['chunk_id']}")
                    results.append(SearchResult(**{k: v for k, v in payload.items() if k in allowed}, full_text=chunk.text))
                metadata = row["retrieval_metadata"]
                selection = select_answer_evidence(row["query"], results, additional_queries=_cross_lingual_selection_queries(metadata))
                full = _evidence_from_response(SearchResponse(query=row["query"], results=selection.results), use_full_text=True)
                snippet = [SimpleNamespace(text=result.snippet) for result in results]
                concepts = glossary_terms_for_concepts(_cross_lingual_matched_concepts(metadata))
                report["records"].append(
                    {
                        "snapshot": str(path),
                        "method": method,
                        "id": row["id"],
                        "query": row["query"],
                        "answerable": row["answerable"],
                        "selected_chunk_ids": [result.chunk_id for result in selection.results],
                        "selection_metadata": selection.metadata,
                        "snippet": asdict(assess_evidence_adequacy(row["query"], snippet)),
                        "selected_full": asdict(assess_evidence_adequacy(row["query"], full, concept_terms=concepts)),
                    }
                )
if args.baseline:
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if baseline["inputs"] != report["inputs"]:
        raise ValueError("Baseline snapshot hashes differ")
    changes = []
    selection_changes = []
    for before, after in zip(baseline["records"], report["records"], strict=True):
        identity = ("snapshot", "method", "id", "query", "answerable")
        if any(before[key] != after[key] for key in identity):
            raise ValueError("Baseline record identities differ")
        if "selected_chunk_ids" in before and before["selected_chunk_ids"] != after["selected_chunk_ids"]:
            selection_changes.append(
                {
                    **{key: after[key] for key in identity},
                    "before": before["selected_chunk_ids"],
                    "after": after["selected_chunk_ids"],
                    "retention": after["selection_metadata"].get("required_concept_retention"),
                }
            )
        for view in ("snippet", "selected_full"):
            if before[view]["adequate"] != after[view]["adequate"]:
                changes.append(
                    {
                        **{key: after[key] for key in identity},
                        "view": view,
                        "before": before[view]["adequate"],
                        "after": after[view]["adequate"],
                        "required_concepts": after[view]["required_concepts"],
                    }
                )
    report["changes"] = changes
    report["selection_changes"] = selection_changes
    print(json.dumps({"changed_verdicts": len(changes), "changed_selections": len(selection_changes)}))
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"records": len(report["records"]), "output": str(args.output)}))
