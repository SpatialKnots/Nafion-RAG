"""Measure production grouping on one live top-10 window per query/method."""
import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.evaluation.retrieval import (
    load_extended_questions, _evaluate_extended_question,
    _result_payloads_from_response, _article_checksums_for_results,
    _chunk_texts_for_results,
)
from app.retrieval.search import SearchResponse, group_results_by_article, search_chunks

gold = Path('docs/evaluation_questions_extended.yaml')
questions = load_extended_questions(gold)
output = Path('tmp/stage2_grouping_audit.json')
report = {'gold': str(gold), 'gold_sha256': hashlib.sha256(gold.read_bytes()).hexdigest(),
          'collection': 'literature', 'top_k': 10,
          'protocol': 'Live ungrouped search; production grouping of the identical window; no refill.',
          'methods': {}}

def encode(value):
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(type(value).__name__)

with SessionLocal() as session:
    for method in ['exact', 'semantic', 'hybrid', 'hybrid_cross_lingual']:
        records = []
        for question in questions:
            response = search_chunks(session, question.query, 'literature', 10,
                                     method=method, settings=get_settings())
            payload = _result_payloads_from_response(response)
            checksums = _article_checksums_for_results(session, payload)
            texts = _chunk_texts_for_results(session, payload)
            variants = {}
            for label, cap in [('flat', None), ('uncapped', None), ('cap1', 1), ('cap2', 2)]:
                candidate = response if label == 'flat' else SearchResponse(
                    query=response.query, results=[],
                    metadata={**response.metadata, 'group_by': 'article'},
                    groups=group_results_by_article(response.results, chunks_per_article=cap))
                evaluated = _evaluate_extended_question(question, candidate, checksums, texts,
                                                       elapsed_ms=0, top_k=10)
                if label != 'flat':
                    assert {r['article_id'] for r in evaluated['results']} == {r['article_id'] for r in payload}
                if label == 'uncapped':
                    assert sorted(r['chunk_id'] for r in evaluated['results']) == sorted(r['chunk_id'] for r in payload)
                visible = {r['chunk_id'] for r in evaluated['results']}
                evaluated['removed_results_with_original_rank'] = [
                    {'original_rank': rank, **r} for rank, r in enumerate(payload, 1) if r['chunk_id'] not in visible]
                variants[label] = evaluated
            records.append({'id': question.id, 'variants': variants})
        summary = {}
        for label in ['flat', 'uncapped', 'cap1', 'cap2']:
            rows = [r['variants'][label] for r in records]
            answerable = [r for r in rows if r['answerable']]
            metrics = {}
            for field in ['article_recall_at_k', 'chunk_recall_at_k']:
                values = [r[field] for r in answerable if r[field] is not None]
                metrics[field] = sum(values) / len(values) if values else None
                metrics[field + '_denominator'] = len(values)
            summary[label] = {**metrics, 'passed': sum(r['passed'] for r in rows),
                              'visible_chunks': sum(r['result_count'] for r in rows),
                              'trace_complete': all(r['evidence_trace_complete'] for r in rows),
                              'chunk_recall_regressions': [r['id'] for r in records
                                  if r['variants'][label]['chunk_recall_at_k'] is not None
                                  and r['variants'][label]['chunk_recall_at_k'] < r['variants']['flat']['chunk_recall_at_k']]}
        report['methods'][method] = {'summary': summary, 'questions': records}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=encode), encoding='utf-8')
        print(json.dumps({'method': method, 'summary': summary}), flush=True)
