"""Replay reviewed source occurrences; context cues are not scientific approval."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.db.models import Article, Chunk, PageTextLayer
from app.db.session import SessionLocal
from app.facts.extraction import diagnose_numeric_occurrences


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, default=Path('docs/numeric_occurrence_pdf_review.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.review.read_bytes()
    review = json.loads(raw)
    if not review['records']:
        raise ValueError('Empty source review')
    records = []
    originals = {}
    with SessionLocal() as session:
        for record in review['records']:
            chunk = session.get(Chunk, UUID(record['target'][0]))
            if chunk is None or chunk.text_layer != record['text_layer']:
                raise ValueError('Missing chunk or changed selected layer')
            article = session.get(Article, chunk.article_id)
            if article is None or article.checksum_sha256 != record['article_checksum']:
                raise ValueError('Article identity changed')
            pdf = Path(article.pdf_original_path).resolve()
            if str(pdf) not in originals:
                originals[str(pdf)] = sha(pdf.read_bytes())
            if originals[str(pdf)] != record['article_checksum']:
                raise ValueError('Original PDF changed')
            _, occurrences = diagnose_numeric_occurrences(chunk)
            for old in record['occurrences']:
                matches = [o for o in occurrences if (o.start, o.end) == (old['start'], old['end'])]
                if len(matches) != 1:
                    raise ValueError('Occurrence span changed')
                occurrence = matches[0]
                if (occurrence.text != record['target'][2] or occurrence.decision != old['decision']
                        or occurrence.reason != old['reason']
                        or chunk.text[occurrence.line_start:occurrence.line_end] != old['line']):
                    raise ValueError('Occurrence text or decision changed')
                for location in old['locations']:
                    if not chunk.page_start <= location['page'] <= chunk.page_end:
                        raise ValueError('Page outside chunk range')
                    layer = session.scalars(select(PageTextLayer).where(
                        PageTextLayer.article_id == article.id, PageTextLayer.page_number == location['page'],
                        PageTextLayer.layer_type == record['text_layer'])).one()
                    fragment = location['text']
                    if (sha(fragment.encode()) != location['text_sha256']
                            or layer.text[location['start']:location['start'] + len(fragment)] != fragment
                            or layer.text.count(old['line']) != location['line_occurrences']):
                        raise ValueError('Reviewed page fragment changed')
                cues = [asdict(cue) for cue in occurrence.context_cues]
                if any(chunk.text[c['start']:c['end']] != c['text'] for c in cues):
                    raise ValueError('Context cue span mismatch')
                records.append(dict(chunk_id=str(chunk.id), start=occurrence.start, text=occurrence.text,
                                    decision=occurrence.decision, context_cues=cues,
                                    page_mapping_status=old['page_mapping_status']))
    for path, checksum in originals.items():
        if sha(Path(path).read_bytes()) != checksum:
            raise ValueError('Original PDF changed during replay')
    report = dict(applied=False, scientific_approval=False, review_sha256=sha(raw),
                  extractor_sha256=sha(Path('app/facts/extraction.py').read_bytes()),
                  context_cues_sha256=sha(Path('app/facts/context_cues.py').read_bytes()),
                  targets=len(review['records']), occurrences=len(records), verified_originals=originals, records=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in {'records', 'verified_originals'}}))


if __name__ == '__main__':
    main()
