"""Source-bound catalogue correction and offline replay; never dispatch a model call."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import fitz  # type: ignore[import-untyped]
from sqlalchemy import select, text

from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as transfer

BASE = f.ROOT / 'output/kondo_metadata_repair_20261110'
PLAN = BASE / 'plan_v02'
ARTICLE = '3e970332-cced-4895-b44e-50a48bdc8e17'
PDF_SHA = '615828f87ad5a0d95872524c2bf3e96e5fed696f18b31a9f6903a128728950f3'
DOI = '10.1002/adma.202514060'
FIELDS = ('title', 'authors', 'year', 'journal')
BEFORE = dict(title='Kond 2025', authors=None, year=None, journal=None)
AUTHORS = ('Yasuyuki Kondo', 'Haruna Nakajima', 'Yu Katayama', 'Nao Kobayashi',
           'Shinya Otani', 'Akinori Tani', 'Shigeaki Yamazaki', 'Yuki Yamada')
AFTER = {
    'title': 'Electrolyte Li+ Chemical Potential Correlates with Graphite Negative Electrode Reactions in Lithium-Ion Batteries',
    'authors': [{'name': name, 'source': 'source_reviewed_catalogue_correction_20261110'} for name in AUTHORS],
    'year': 2026, 'journal': 'Advanced Materials',
}
ANCHORS = {
    'title': 'Electrolyte Li+ Chemical Potential Correlates with Graphite\nNegative Electrode Reactions in Lithium-Ion Batteries',
    'authors': 'Yasuyuki Kondo, Haruna Nakajima, Yu Katayama, Nao Kobayashi, Shinya Otani,\n'
               'Akinori Tani, Shigeaki Yamazaki, and Yuki Yamada*',
    'year': 'Adv. Mater. 2026, 38, e14060',
    'journal': '© 2025 The Author(s). Advanced Materials published by Wiley-VCH\nGmbH.',
    'doi': 'DOI: 10.1002/adma.202514060',
}


def read(path):
    return json.loads(path.read_bytes())


def snapshot(session):
    from app.db.models import Article
    return {str(a.id): json.loads(json.dumps({c.name: getattr(a, c.name) for c in Article.__table__.columns},
                                           default=str))
            for a in session.scalars(select(Article).order_by(Article.id))}


def source(article):
    from app.documents.service import resolve_article_pdf
    path = resolve_article_pdf(article, f.configure()).path
    if article.checksum_sha256 != PDF_SHA or article.doi != DOI or f.sha(path.read_bytes()) != PDF_SHA:
        raise ValueError('Original PDF or registered DOI identity drift')
    with fitz.open(path) as document:
        page = document[0].get_text('text')
    anchors = {}
    for field, quote in ANCHORS.items():
        if page.count(quote) != 1:
            raise ValueError('Bibliographic source anchor is absent or ambiguous: ' + field)
        start = page.index(quote)
        anchors[field] = {'start': start, 'end': start + len(quote), 'quote': quote}
    return {'article_id': ARTICLE, 'pdf_path': str(path), 'pdf_sha256': PDF_SHA, 'page_number': 1,
            'page_text': page, 'page_text_sha256': f.sha(page.encode()), 'anchors': anchors,
            'review_origin': 'assistant source review; full original first-page image inspected',
            'year_basis': 'printed issue citation, not copyright year or filename',
            'independent_expert_confirmation': False}


def stage(session, expected, before):
    """Lock exactly the identified row; reject stale state before touching metadata."""
    from app.db.models import Article
    article = session.scalar(select(Article).where(Article.id == UUID(ARTICLE)).with_for_update())
    if article is None or snapshot(session) != expected or {k: getattr(article, k) for k in FIELDS} != before:
        raise ValueError('Stale catalogue state; correction not applied')
    provenance = source(article)
    for field in FIELDS:
        setattr(article, field, AFTER[field])
    session.flush()
    expected_after = json.loads(json.dumps(expected))
    expected_after[ARTICLE].update(AFTER)
    if snapshot(session) != expected_after:
        raise ValueError('Correction changed fields outside the four-field plan')
    return provenance, expected_after


def plan():
    from app.db.session import SessionLocal
    transfer.fixed_version()
    folder = PLAN
    folder.mkdir(parents=True, exist_ok=False)
    with SessionLocal() as session:
        before = snapshot(session)
        provenance, after = stage(session, before, BEFORE)
        session.rollback()
        if snapshot(session) != before:
            raise ValueError('Dry-run rollback did not preserve catalogue')
        session.rollback()
    f.write(folder / 'before.json', before)
    f.write(folder / 'expected_after.json', after)
    f.write(folder / 'source.json', provenance)
    f.write(folder / 'plan.json', {'article_id': ARTICLE, 'before': BEFORE, 'after': AFTER,
        'changed_fields': list(FIELDS), 'dry_run_rolled_back': True, 'app_changes': 0,
        'pdf_renaming': False, 'fuzzy_author_or_year_matching': False, 'model_calls': 0})
    f.write(folder / 'bindings.json', f.bindings([Path(__file__), transfer.FIXED / 'manifest.json',
                                               Path(provenance['pdf_path'])]))
    f.manifest(folder)
    return {'planned_articles': 1, 'changed_fields': list(FIELDS), 'dry_run_rolled_back': True}


def apply():
    from app.db.session import SessionLocal
    folder = PLAN
    f.verify_manifest(folder)
    f.verify(read(folder / 'bindings.json'))
    # An interrupted application requires explicit state review, never an automatic retry.
    f.write(BASE / 'apply_intent.json', {'plan_manifest_sha256': f.sha((folder / 'manifest.json').read_bytes()),
                                      'article_id': ARTICLE, 'fields': list(FIELDS)})
    with SessionLocal() as session:
        provenance, after = stage(session, read(folder / 'before.json'), BEFORE)
        if provenance != read(folder / 'source.json') or after != read(folder / 'expected_after.json'):
            raise ValueError('Correction plan/source drift')
        session.commit()
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        actual = snapshot(session)
        session.rollback()
    if actual != after:
        raise ValueError('Committed catalogue differs from correction plan')
    f.write(BASE / 'applied.json', {'articles_changed': 1, 'fields_changed': list(FIELDS),
        'catalogue_after': actual, 'app_changes': 0, 'model_calls': 0, 'oauth_calls': 0})
    return {'articles_changed': 1, 'fields_changed': list(FIELDS), 'model_calls': 0}


def prepare(case, policy):
    transfer.fixed_version()
    f.verify_manifest(PLAN)
    if not (BASE / 'applied.json').exists():
        raise ValueError('Source-bound correction must be committed before replay')
    settings = f.configure()
    folder = BASE / 'prepared_v01' / case['id']
    folder.mkdir(parents=True, exist_ok=False)
    old = transfer.BASE / 'prepared_v01' / case['id']
    f.verify_manifest(old)
    request = read(old / 'api_request.json')
    f.write(folder / 'api_request.json', request)
    obs = transfer.Observation(folder, settings, policy, case=case)
    reached, response_body = False, None
    with patch.object(f, 'QUESTION', case['question']):
        try:
            response = transfer.run_route(obs, request)
            response_body = {'http_status': response.status_code, 'body': response.json()}
            f.write(folder / 'preparation_api_response.json', response_body)
            if response.status_code != 200:
                raise ValueError('Unexpected offline API error')
        except f.PreparedBoundary:
            reached = True
    if obs.trace is None or obs.sources is None or obs.readonly != 'on' or policy.denied:
        raise ValueError('Incomplete or unsafe preparation')
    ref = obs.trace['retrieval']['metadata'].get('explicit_source_reference', {})
    if not ref.get('resolved') or ref.get('article_id') != case['article_id'] or not obs.scope_ok:
        raise ValueError('Explicit reference/evidence does not resolve to exactly the requested article')
    same = {name: (old / name).exists() == (folder / name).exists() and
                  (not (folder / name).exists() or (old / name).read_bytes() == (folder / name).read_bytes())
            for name in ('api_request.json', 'trace.json', 'sources.json', 'articles.json', 'request.json',
                         'preparation_api_response.json')}
    result = {'id': case['id'], 'resolved': ref, 'all_selected_match': obs.scope_ok,
        'generation_reached': reached, 'request_bytes': len(obs.body or b''),
        'baseline_api_response': response_body, 'exact_previous_files': same,
        'transaction_read_only': obs.readonly, 'transaction_end': 'rollback',
        'network_denials': policy.denied, 'model_calls': 0, 'oauth_calls': 0,
        'dispatch_authorized': False, 'scientific_accuracy': None}
    f.write(folder / 'result.json', result)
    f.manifest(folder)
    return {k: result[k] for k in ('id', 'all_selected_match', 'generation_reached', 'request_bytes')}


def batch():
    settings, results = f.configure(), []
    cases = read(transfer.BASE / 'input_freeze_v01/questions.json')['cases']
    for case in cases:
        done = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'scripts.repair_kondo_metadata_20261110',
                               'prepare', '--case-id', case['id']], cwd=f.ROOT, capture_output=True, encoding='utf-8')
        logs = BASE / 'worker_logs' / case['id']
        logs.mkdir(parents=True, exist_ok=False)
        for name, raw in (('stdout', done.stdout), ('stderr', done.stderr)):
            for secret in (settings.gigachat_credentials, settings.database_url):
                if secret:
                    raw = raw.replace(secret, '[REDACTED]')
            f.save(logs / (name + '.txt'), raw.encode())
        if done.returncode:
            raise RuntimeError('Offline preparation failed: ' + case['id'] + '; see saved logs')
        row = json.loads(done.stdout.strip().splitlines()[-1])
        results.append(row)
        print(json.dumps(row), flush=True)
    f.write(BASE / 'batch.json', results)
    return {'prepared': len(results), 'model_calls': 0, 'oauth_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'apply', 'prepare', 'prepare-all'))
    parser.add_argument('--case-id', choices=transfer.IDS)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    policy = f.NetworkPolicy()
    sys.addaudithook(policy)
    if args.mode == 'plan':
        value = plan()
    elif args.mode == 'apply':
        value = apply()
    elif args.mode == 'prepare-all':
        value = batch()
    else:
        case = next(c for c in read(transfer.BASE / 'input_freeze_v01/questions.json')['cases'] if c['id'] == args.case_id)
        value = prepare(case, policy)
    if policy.denied:
        raise RuntimeError('External network attempt during metadata correction')
    print(json.dumps(value), flush=True)
