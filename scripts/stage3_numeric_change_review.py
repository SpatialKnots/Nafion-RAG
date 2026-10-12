"""Build a source-verified review queue; source presence never approves facts.

Annotations bind to one immutable diff. --check fails on blockers or unreviewed
changes. This command never refreshes structured_facts or writes to the database.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.db.models import Article, Chunk, PageTextLayer
from app.db.session import SessionLocal
from app.facts.extraction import diagnose_numeric_occurrences


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(chunk_id: str, direction: str, candidate: dict) -> tuple:
    return (chunk_id, direction, candidate['field_name'], candidate['field_value_text'],
            candidate['field_value_numeric'], candidate['unit'])


def validate_occurrence_label(chunk: Chunk, label: dict) -> None:
    """Optional occurrence binding; legacy labels remain fragment-only reviews."""
    fields = {'chunk_occurrence_start', 'chunk_occurrence_end', 'occurrence_decision', 'occurrence_reason'}
    if not fields.intersection(label):
        return
    if not fields.issubset(label):
        raise ValueError('Incomplete occurrence binding')
    _, occurrences = diagnose_numeric_occurrences(chunk)
    matches = [o for o in occurrences if o.start == label['chunk_occurrence_start']
               and o.end == label['chunk_occurrence_end']]
    if len(matches) != 1:
        raise ValueError('Reviewed occurrence span missing')
    occurrence = matches[0]
    if (occurrence.text != label['candidate']['field_value_text']
            or occurrence.decision != label['occurrence_decision']
            or occurrence.reason != label['occurrence_reason']):
        raise ValueError('Reviewed occurrence decision changed')
    # A repeated lexeme alone cannot establish that this is the reviewed context.
    line = chunk.text[occurrence.line_start:occurrence.line_end]
    if line not in label['text']:
        raise ValueError('Reviewed fragment does not contain occurrence line')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diff', type=Path, required=True)
    parser.add_argument('--labels', type=Path, default=Path('docs/numeric_change_review.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    raw = args.diff.read_bytes()
    diff = json.loads(raw)
    label_raw = args.labels.read_bytes()
    annotations = json.loads(label_raw)
    if annotations['diff_sha256'] != digest(raw):
        raise ValueError('Review labels belong to a different diff')
    if diff['current_code_sha256'] != digest(Path('app/facts/extraction.py').read_bytes()):
        raise ValueError('Extractor changed since the diff; regenerate and review a new snapshot')
    labels = {}
    for label in annotations['labels']:
        key = identity(label['chunk_id'], label['direction'], label['candidate'])
        if key in labels:
            raise ValueError('Duplicate review label')
        if label['verdict'] not in {'blocker', 'acceptable'} or label['review_status'] != 'assistant_pdf_reviewed':
            raise ValueError('Invalid reviewed verdict/status')
        labels[key] = label
    used = set()
    records = []
    originals = {}
    with SessionLocal() as session:
        for row in diff['records']:
            chunk = session.get(Chunk, UUID(row['chunk_id']))
            if chunk is None or chunk.text != row['text']:
                raise ValueError(f"Changed or missing chunk: {row['chunk_id']}")
            article = session.get(Article, chunk.article_id)
            if article is None:
                raise ValueError('Missing source article')
            pdf = Path(article.pdf_original_path).resolve()
            if str(pdf) not in originals:
                originals[str(pdf)] = digest(pdf.read_bytes())
            if originals[str(pdf)] != article.checksum_sha256:
                raise ValueError(f'Original PDF checksum mismatch: {pdf}')
            for direction in ('added', 'removed'):
                for candidate in row[direction]:
                    if candidate['source_chunk_id'] != str(chunk.id) or candidate['article_id'] != str(article.id):
                        raise ValueError('Candidate provenance mismatch')
                    lexeme = candidate['field_value_text']
                    occurrences = []
                    for match in re.finditer(re.escape(lexeme), chunk.text):
                        start, end = match.span()
                        occurrences.append({'start': start, 'end': end,
                                            'context': chunk.text[max(0, start-100):end+100]})
                    if not occurrences:
                        raise ValueError('Candidate lexeme absent from source chunk')
                    key = identity(str(chunk.id), direction, candidate)
                    label = labels.get(key)
                    if label:
                        used.add(key)
                        validate_occurrence_label(chunk, label)
                        layer = session.scalars(select(PageTextLayer).where(
                            PageTextLayer.article_id == article.id, PageTextLayer.page_number == label['page'],
                            PageTextLayer.layer_type == label['text_layer'])).one()
                        text = label['text']
                        if (label['article_checksum'] != article.checksum_sha256
                                or label['text_layer'] != chunk.text_layer
                                or not chunk.page_start <= label['page'] <= chunk.page_end
                                or digest(text.encode()) != label['text_sha256']
                                or layer.text[label['start']:label['start']+len(text)] != text
                                or lexeme not in text):
                            raise ValueError('Reviewed PDF fragment changed or inconsistent')
                    records.append({
                        'review_id': digest(json.dumps(key, ensure_ascii=False).encode()),
                        'direction': direction, 'candidate': candidate,
                        'review_status': label['verdict'] if label else 'unreviewed', 'annotation': label,
                        'article': {'id': str(article.id), 'title': article.title, 'doi': article.doi,
                                    'checksum': article.checksum_sha256, 'pdf_path': str(pdf)},
                        'chunk': {'id': str(chunk.id), 'page_start': chunk.page_start, 'page_end': chunk.page_end,
                                  'source_type': chunk.source_type, 'text_layer': chunk.text_layer,
                                  'text_sha256': digest(chunk.text.encode())},
                        'lexeme_occurrences_not_unique_attribution': occurrences,
                    })
    if used != set(labels):
        raise ValueError('Review labels refer to absent candidates')
    for path, checksum in originals.items():
        if digest(Path(path).read_bytes()) != checksum:
            raise ValueError(f'Original PDF changed during review: {path}')
    counts = Counter(r['review_status'] for r in records)
    directions = Counter(r['direction'] for r in records)
    if directions['added'] != diff['added'] or directions['removed'] != diff['removed']:
        raise ValueError('Diff totals inconsistent with candidate records')
    summary = {'total_changes': len(records), 'added': directions['added'], 'removed': directions['removed'],
               'blockers': counts['blocker'], 'acceptable': counts['acceptable'], 'unreviewed': counts['unreviewed'],
               'bulk_refresh_ready': bool(records) and not counts['blocker'] and not counts['unreviewed']}
    report = {'diff_sha256': digest(raw), 'labels_sha256': digest(label_raw), 'applied': False,
              'independent_review': annotations['independent_review'], 'verified_originals': originals,
              'summary': summary, 'records': records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary))
    if args.check and not summary['bulk_refresh_ready']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
