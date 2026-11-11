"""Freeze the actual complete explicit-article ranking pool for all 30 questions."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import fitz
from sqlalchemy import text

from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/peng_best_ce_20261111'
PARENT = f.ROOT / 'output/nambu_order_binding_20261111/comparison_v02'
PDF = f.ROOT / 'data/pdf/6ab4542d9156e377_Peng_2021.pdf'


def main():
    f.configure()
    from app.db.session import SessionLocal
    from app.retrieval.search import SearchFilters, _source_reference_chunks
    from app.retrieval.source_reference import rank_context

    f.verify_manifest(PARENT)
    out = BASE / 'capture_v02'
    out.mkdir(exist_ok=False)
    cases = []
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if session.execute(text('SHOW transaction_read_only')).scalar_one() != 'on':
            raise ValueError('Read-only required')
        for case in json.loads((PARENT / 'result.json').read_bytes())['cases']:
            cid = case['id']
            api = json.loads((PARENT / cid / 'api_request.json').read_bytes())
            trace = json.loads((PARENT / cid / 'after.json').read_bytes())['trace']
            ref = trace['retrieval']['metadata']['explicit_source_reference']
            rows = _source_reference_chunks(session, api['question'], api['collection'], SearchFilters(), ref['article_id'])
            selected, metadata = rank_context(api['question'], rows, top_k=api['top_k'])
            if [asdict(r) for r in selected] != trace['retrieval']['results']:
                raise ValueError('Fresh complete-pool baseline differs: ' + cid)
            if any(ref[k] != v for k, v in metadata.items()):
                raise ValueError('Fresh role metadata differs')
            cases.append({'id': cid, 'rows': [asdict(r) for r in rows]})
        session.rollback()
    f.write(out / 'cases.json', cases)
    with fitz.open(PDF) as doc:
        page = doc[4]
        f.save(out / 'page5.txt', page.get_text().encode())
        done = subprocess.run([shutil.which('pdftoppm'), '-f', '5', '-l', '5', '-scale-to', '2000',
            '-singlefile', '-png', str(PDF), str(out / 'page5')], capture_output=True)
        f.save(out / 'render_stderr.txt', done.stderr)
        if done.returncode:
            raise RuntimeError('Render failed')
    f.write(out / 'result.json', {'fresh_pool_cases_exact': len(cases), 'transaction': 'read_only_rollback',
        'real_model_calls': 0, 'real_oauth_calls': 0})
    f.write(out / 'bindings.json', f.bindings([Path(__file__), PARENT / 'manifest.json', PDF]))
    f.manifest(out)
    print(json.dumps({'fresh_pool_cases_exact': len(cases), 'model_oauth_calls': 0}))


if __name__ == '__main__':
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    main()
    if policy.denied:
        raise ValueError('Unexpected external network attempt')
