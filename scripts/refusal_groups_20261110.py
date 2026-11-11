"""Capture the remaining refusal cohort and exact registered/PDF source inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

import fitz  # type: ignore[import-untyped]
from sqlalchemy import select, text

from scripts import bilingual_lexical_admission_20261110 as parent
from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/refusal_groups_20261110'
PROTOCOL = f.ROOT / 'docs/records/refusal_groups_2026-11-10_v0.1.md'


def read(path):
    return json.loads(path.read_bytes())


def capture():
    from app.db.models import Article, Chunk, Page
    from app.db.session import SessionLocal
    from app.documents.service import resolve_article_pdf

    settings = f.configure()
    previous = parent.BASE / 'comparison_v03'
    f.verify_manifest(previous)
    f.verify(read(previous / 'bindings.json'))
    cohort = read(previous / 'summary.json')['cases']
    questions = {c['id']: c for c in read(parent.QUESTIONS)['cases']}
    refused = [r['id'] for r in cohort if not r['after_reached']]
    if len(refused) != 21:
        raise ValueError('Unexpected refusal scope')
    app = f.bindings([*f.ROOT.joinpath('app').rglob('*.py'), *f.ROOT.joinpath('app').rglob('*.yaml')])
    folder = BASE / 'capture_v01'
    folder.mkdir(parents=True, exist_ok=False)
    articles, chunks, pages, pdfs = {}, {}, {}, {}
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if session.execute(text('SHOW transaction_read_only')).scalar_one() != 'on':
            raise ValueError('Read-only transaction required')
        for aid in sorted({c['article_id'] for c in questions.values()}):
            article = session.get(Article, UUID(aid))
            pdf = resolve_article_pdf(article, settings).path
            if f.sha(pdf.read_bytes()) != article.checksum_sha256:
                raise ValueError('Original PDF drift')
            articles[aid] = {'article_id': aid, 'title': article.title, 'authors': article.authors,
                'year': article.year, 'doi': article.doi, 'pdf_path': str(pdf), 'pdf_sha256': article.checksum_sha256}
            with fitz.open(pdf) as document:
                pdfs[aid] = [{'page': i + 1, 'text': p.get_text('text')} for i, p in enumerate(document)]
            for page in session.scalars(select(Page).where(Page.article_id == article.id).order_by(Page.page_number)):
                pages[str(page.id)] = {'article_id': aid, 'page_number': page.page_number,
                    'text': page.text, 'text_layer': page.selected_text_layer,
                    'fresh_original_text_exact': page.text == pdfs[aid][page.page_number - 1]['text']}
            for chunk in session.scalars(select(Chunk).where(Chunk.article_id == article.id).order_by(Chunk.chunk_index, Chunk.id)):
                chunks[str(chunk.id)] = {'article_id': aid, 'chunk_id': str(chunk.id), 'chunk_index': chunk.chunk_index,
                    'page_start': chunk.page_start, 'page_end': chunk.page_end, 'source_type': chunk.source_type,
                    'text_layer': chunk.text_layer, 'text': chunk.text}
        session.rollback()
    cases = []
    for row in cohort:
        cid = row['id']
        record = read(previous / cid / 'after.json')
        for evidence in record['trace']['evidence']:
            raw = chunks[evidence['chunk_id']]
            if any(raw[k] != evidence[k] for k in ('article_id', 'page_start', 'page_end', 'source_type', 'text')):
                raise ValueError('Selected evidence differs from current registry: ' + cid)
        cases.append({'case': questions[cid], 'refused': cid in refused, 'preparation': record,
                      'selected_pages': sorted({p for e in record['trace']['evidence']
                                                for p in range(e['page_start'], e['page_end'] + 1)})})
    f.write(folder / 'cases.json', cases)
    f.write(folder / 'articles.json', articles)
    f.write(folder / 'chunks.json', chunks)
    f.write(folder / 'registered_pages.json', pages)
    f.write(folder / 'original_pdf_text.json', pdfs)
    for label in ('Kondo', 'Nambu', 'Peng'):
        aid = next(c['case']['article_id'] for c in cases if c['case']['id'].startswith(label))
        f.save(folder / (label + '_all_pages.txt'), '\n\n'.join(
            '=== PDF PAGE ' + str(p['page']) + ' ===\n' + p['text'] for p in pdfs[aid]).encode())
    f.verify(app)
    f.write(folder / 'app_bindings.json', app)
    f.save(folder / 'service.py', (f.ROOT / 'app/generation/service.py').read_bytes())
    f.save(folder / 'bilingual_lexical.py', (f.ROOT / 'app/generation/bilingual_lexical.py').read_bytes())
    f.write(folder / 'bindings.json', f.bindings([PROTOCOL, Path(__file__), previous / 'manifest.json',
        parent.QUESTIONS, *[Path(a['pdf_path']) for a in articles.values()]]))
    summary = {'refusals': len(refused), 'controls_ready': len(cases) - len(refused), 'articles': len(articles),
               'registered_pages': len(pages), 'registered_chunks': len(chunks),
               'original_pdf_pages': sum(map(len, pdfs.values())),
               'registered_pages_match_fresh_original': sum(p['fresh_original_text_exact'] for p in pages.values()),
               'transaction': 'read_only_repeatable_read_rollback', 'model_calls': 0, 'oauth_calls': 0}
    f.write(folder / 'summary.json', summary)
    f.manifest(folder)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('capture',))
    parser.parse_args()
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    value = capture()
    if policy.denied:
        raise ValueError('External network attempt during refusal capture')
    print(json.dumps(value))
