"""Live local-provider probes for diglyme retention and the PBI refusal guard."""

import json
from dataclasses import asdict
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.evaluation.retrieval import load_extended_questions
from app.generation.providers import ExtractiveAnswerProvider
from app.generation.service import answer_question

questions = {question.id: question.query for question in load_extended_questions(Path("docs/evaluation_questions_extended.yaml"))}
cases = [
    ("qext035_chernyuk_dissertation_solvent_table_ru", "exact"),
    ("qext035_chernyuk_dissertation_solvent_table_ru", "hybrid"),
    ("qext035_chernyuk_dissertation_solvent_table_ru", "semantic"),
    ("qext042_absent_high_temperature_pbi", "hybrid_cross_lingual"),
]
records = []
with SessionLocal() as session:
    for question_id, method in cases:
        response = answer_question(
            session,
            get_settings(),
            questions[question_id],
            collection="literature",
            top_k=10,
            method=method,
            provider=ExtractiveAnswerProvider(max_claims=10),
        )
        records.append({"id": question_id, "method": method, "response": asdict(response)})
        print(
            json.dumps(
                {
                    "id": question_id,
                    "method": method,
                    "status": response.status,
                    "adequacy": response.metadata["evidence_adequacy"],
                    "selection": response.metadata["answer_evidence_selection"],
                    "cited_chunks": [citation.chunk_id for citation in response.citations],
                },
                ensure_ascii=True,
            ),
            flush=True,
        )
Path("tmp/stage2_retention_live.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
