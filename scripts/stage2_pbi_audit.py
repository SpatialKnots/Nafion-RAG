"""Read-only PBI source-layer audit and local answer-gate replay; no external provider."""

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Article, PageTextLayer
from app.db.session import SessionLocal
from app.generation.providers import ExtractiveAnswerProvider
from app.generation.service import answer_question

pattern = re.compile(r"polybenzimidazol\w*|\bpbi\b|phosphoric|полибензимидазол\w*|фосфорн\w*", re.I)
report = {"protocol": "All stored original/OCR layers; lexical absence is not visual PDF verification.", "hits": []}
with SessionLocal() as session:
    rows = session.execute(select(Article, PageTextLayer).join(PageTextLayer, PageTextLayer.article_id == Article.id)).all()
    report["layers_scanned"] = len(rows)
    report["articles_scanned"] = len({article.id for article, page in rows})
    articles = {article.id: article for article, page in rows}
    report["original_hashes_match"] = all(
        hashlib.sha256(Path(article.pdf_original_path).read_bytes()).hexdigest() == article.checksum_sha256 for article in articles.values()
    )
    for article, page in rows:
        for match in pattern.finditer(page.text):
            report["hits"].append(
                {
                    "article": article.title,
                    "doi": article.doi,
                    "pdf": article.pdf_original_path,
                    "checksum": article.checksum_sha256,
                    "page": page.page_number,
                    "layer": page.layer_type,
                    "match": match.group(),
                    "excerpt": page.text[max(0, match.start() - 250) : match.end() + 350],
                }
            )
    response = answer_question(
        session,
        get_settings(),
        question="polybenzimidazole phosphoric acid anhydrous fuel cell Nafion composite",
        collection="literature",
        top_k=10,
        method="hybrid_cross_lingual",
        provider=ExtractiveAnswerProvider(max_claims=5),
    )
    report["answer_gate_replay"] = asdict(response)
output = Path("tmp/stage2_pbi_source_audit.json")
output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps({key: value for key, value in report.items() if key != "answer_gate_replay"}, ensure_ascii=True))
print(json.dumps({"status": response.status, "adequacy": response.metadata["evidence_adequacy"]}, ensure_ascii=True))
