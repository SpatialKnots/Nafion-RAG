"""Read-only candidate-window experiment; no retrieval settings are changed."""

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from time import perf_counter

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.evaluation.retrieval import (
    _article_checksums_for_results,
    _chunk_texts_for_results,
    _evaluate_extended_question,
    _result_payloads_from_response,
    load_extended_questions,
)
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.evidence_selection import select_answer_evidence
from app.generation.required_concepts import assess_required_concepts
from app.generation.service import _evidence_from_response
from app.retrieval.search import SearchResponse, search_chunks

questions = {}
for path in ("docs/evaluation_questions_extended.yaml", "docs/evaluation_questions_cross_lingual_extended.yaml"):
    questions.update({question.id: question for question in load_extended_questions(Path(path))})
cases = [
    ("qext035_chernyuk_dissertation_solvent_table_ru", "semantic"),
    ("xling_en_ru_kayumov_li_conducting_membranes", "exact"),
    ("xling_ru_en_sanginov_ec_sl_conductivity", "semantic"),
    ("xling_ru_en_istomina_swelling_temperature", "semantic"),
    ("xling_ru_en_istomina_swelling_temperature", "hybrid"),
]
records = []
settings = get_settings()
with SessionLocal() as session:
    for question_id, method in cases:
        question = questions[question_id]
        baseline_ids = None
        for top_k in (10, 25, 50):
            start = perf_counter()
            response = search_chunks(session, question.query, "literature", top_k, method=method, settings=settings)
            elapsed_ms = (perf_counter() - start) * 1000
            payload = _result_payloads_from_response(response)
            evaluated = _evaluate_extended_question(
                question,
                response,
                _article_checksums_for_results(session, payload),
                _chunk_texts_for_results(session, payload),
                elapsed_ms=elapsed_ms,
                top_k=top_k,
            )
            ids = [result.chunk_id for result in response.results]
            if baseline_ids is None:
                baseline_ids = ids
            selection = select_answer_evidence(question.query, response.results)
            full = _evidence_from_response(SearchResponse(query=question.query, results=selection.results), use_full_text=True)
            gate = assess_evidence_adequacy(question.query, full)
            identity_hits = []
            for rank, result in enumerate(response.results, 1):
                coverage = assess_required_concepts(question.query, [result.full_text or result.snippet])
                if coverage.matched:
                    identity_hits.append({"rank": rank, "matched": coverage.matched, **payload[rank - 1]})
            row = {
                "id": question_id,
                "query": question.query,
                "method": method,
                "top_k": top_k,
                "top10_prefix_unchanged": ids[: len(baseline_ids)] == baseline_ids,
                "gate": asdict(gate),
                "identity_hits": identity_hits,
                "evaluation": evaluated,
            }
            records.append(row)
            print(
                json.dumps(
                    {
                        "id": question_id,
                        "method": method,
                        "top_k": top_k,
                        "adequate": gate.adequate,
                        "missing": gate.required_concepts.missing,
                        "expected_rank": evaluated["rank_of_first_relevant"],
                        "gold_passed": evaluated["passed"],
                        "identity_hit_ranks": [hit["rank"] for hit in identity_hits],
                        "prefix_unchanged": row["top10_prefix_unchanged"],
                    }
                ),
                flush=True,
            )


def encode(value):
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(type(value).__name__)


Path("tmp/stage2_candidate_coverage_audit.json").write_text(
    json.dumps(records, ensure_ascii=False, indent=2, default=encode), encoding="utf-8"
)
