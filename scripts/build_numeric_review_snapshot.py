"""Build a source-verified UI review snapshot; never apply facts or prior verdicts."""

import argparse
import json
import os
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Article, Chunk, PageTextLayer
from app.db.session import SessionLocal
from app.facts.extraction import diagnose_numeric_occurrences
from app.facts.review_store import code_hashes, sha


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diff', required=True, type=Path)
    parser.add_argument('--prior-labels', type=Path)
    args = parser.parse_args()
    raw = args.diff.read_bytes()
    diff = json.loads(raw)
    hashes = code_hashes()
    if diff['current_code_sha256'] != hashes['extraction.py']:
        raise ValueError('Extractor changed; regenerate diff')
    prior = [] if args.prior_labels is None else json.loads(args.prior_labels.read_bytes())['labels']
    sources, records, originals = {}, [], {}
    with SessionLocal() as session:
        for row in diff['records']:
            chunk = session.get(Chunk, UUID(row['chunk_id']))
            if chunk is None or chunk.text != row['text']:
                raise ValueError('Diff chunk changed')
            article = session.get(Article, chunk.article_id)
            if article is None:
                raise ValueError('Source article missing')
            pdf = Path(article.pdf_original_path).resolve()
            if str(pdf) not in originals:
                originals[str(pdf)] = sha(pdf.read_bytes())
            if originals[str(pdf)] != article.checksum_sha256:
                raise ValueError('PDF checksum mismatch')
            sources[str(chunk.id)] = dict(article_id=str(article.id), title=article.title, pdf_path=str(pdf),
                                          pdf_sha256=article.checksum_sha256, chunk_sha256=sha(chunk.text.encode()),
                                          text=chunk.text, page_start=chunk.page_start, page_end=chunk.page_end,
                                          text_layer=chunk.text_layer, source_type=chunk.source_type)
            sources[str(chunk.id)]['page_hashes'] = {
                str(layer.page_number): sha(layer.text.encode())
                for layer in session.scalars(select(PageTextLayer).where(
                    PageTextLayer.article_id == article.id, PageTextLayer.layer_type == chunk.text_layer,
                    PageTextLayer.page_number >= chunk.page_start, PageTextLayer.page_number <= chunk.page_end))
            }
            _, diagnostics = diagnose_numeric_occurrences(chunk)
            by_span = {(o.start, o.end): asdict(o) for o in diagnostics}
            for direction in ('added', 'removed'):
                for candidate in row[direction]:
                    if candidate['source_chunk_id'] != str(chunk.id) or candidate['article_id'] != str(article.id):
                        raise ValueError('Candidate provenance mismatch')
                    occurrences = []
                    for match in re.finditer(re.escape(candidate['field_value_text']), chunk.text):
                        start, end = match.span()
                        occurrence = by_span.get((start, end), dict(
                            start=start, end=end, decision='not_recognized', reason='no_exact_current_match', context_cues=[],
                        ))
                        occurrences.append({**occurrence, 'context_start': max(0, start - 180),
                                            'context_end': min(len(chunk.text), end + 180)})
                    if not occurrences:
                        raise ValueError('Candidate missing from source')
                    identity = [str(chunk.id), direction, candidate]
                    previous = [p for p in prior if p['chunk_id'] == str(chunk.id) and p['direction'] == direction
                                and p['candidate'] == candidate]
                    records.append(dict(id=sha(json.dumps(identity, sort_keys=True).encode()), chunk_id=str(chunk.id),
                                        direction=direction, candidate=candidate, occurrences=occurrences,
                                        historical_annotations=previous))
    if len(records) != diff['added'] + diff['removed'] or len({r['id'] for r in records}) != len(records):
        raise ValueError('Invalid diff counts/identities')
    for path, checksum in originals.items():
        if sha(Path(path).read_bytes()) != checksum:
            raise ValueError('PDF changed during snapshot build')
    if hashes != code_hashes():
        raise ValueError('Code changed during snapshot build')
    records.sort(key=lambda r: (sources[r['chunk_id']]['title'] or '', sources[r['chunk_id']]['page_start'], r['id']))
    snapshot = dict(schema_version=1, created_at=datetime.now(UTC).isoformat(), diff_sha256=sha(raw),
                    code_hashes=hashes, sources=sources, records=records,
                    prior_labels_sha256=None if args.prior_labels is None else sha(args.prior_labels.read_bytes()))
    payload = (json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n').encode()
    snapshot_id = sha(payload)
    root = get_settings().data_root / 'reviews' / 'numeric'
    (root / 'snapshots').mkdir(parents=True, exist_ok=True)
    with (root / 'snapshots' / f'{snapshot_id}.json').open('xb') as stream:
        stream.write(payload)
    pointer = root / f'current-{uuid4().hex}.tmp'
    pointer.write_text(snapshot_id, encoding='utf-8')
    os.replace(pointer, root / 'current')
    print(json.dumps(dict(snapshot_id=snapshot_id, items=len(records), sources=len(sources), decisions_imported=0)))


if __name__ == '__main__':
    main()
