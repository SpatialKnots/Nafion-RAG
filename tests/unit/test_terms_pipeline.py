"""Real subprocess pipeline tests on synthetic PDFs; no production DB or scientific gold labels."""
import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import fitz
import pytest

from app.terms.review_store import canonical, current_snapshot, load_snapshot, sha
from scripts.tac_experiment import span
from scripts.tac_terms_pipeline import capture, run_once


def bundle(tmp_path):
    pdf = tmp_path/'paper.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50,80),'Synthetic method article',fontsize=16)
        page.insert_text((50,120),'ABSTRACT: Conductivity was measured by impedance spectroscopy.',fontsize=10)
        doc.save(pdf)
        text = page.get_text()
    root = Path.cwd()
    path = pdf.relative_to(root).as_posix()
    checksum = sha(pdf.read_bytes())
    page = dict(page=1,text=text,text_sha256=sha(text.encode()),layer='original',layer_id='synthetic',
                layer_pdf_path=path,layer_pdf_sha256=checksum)
    article = dict(article_id='synthetic-one',title='Synthetic method article',doi=None,original_pdf_path=path,
                   original_pdf_sha256=checksum,pages=[page],chunks=[])
    snapshot = dict(schema='synthetic test snapshot',articles=[article],pdf_hashes={path:checksum})
    snapshot_path = tmp_path/'snapshot.json'
    snapshot_path.write_bytes(canonical(snapshot))
    profile = dict(article_id=article['article_id'],metadata_title=article['title'],original_pdf_path=path,
                   original_pdf_sha256=checksum,sections=[asdict(span(page,'A',text.index('Conductivity'),len(text),'synthetic'))],
                   diagnostics=[],layout_warnings=[])
    profiles = dict(schema='synthetic test profiles',snapshot_sha256=sha(snapshot_path.read_bytes()),profiles=[profile])
    profiles_path = tmp_path/'profiles.json'
    profiles_path.write_bytes(canonical(profiles))
    metadata = dict(articles=[dict(article_id=article['article_id'],checksum_sha256=checksum,authors=None,journal=None,year=None)])
    metadata_path = tmp_path/'metadata.json'
    metadata_path.write_bytes(canonical(metadata))
    review_root = tmp_path/'review'
    cfg = dict(snapshot=str(snapshot_path),profiles=str(profiles_path),metadata=str(metadata_path),review_root=str(review_root))
    config = tmp_path/'bundle.json'
    config.write_bytes(canonical(cfg))
    return config, tmp_path/'pipeline',review_root,snapshot,profiles,metadata


def test_real_pipeline_build_noop_and_changed_corpus_recompute_memberships(tmp_path):
    config,out,store,snapshot,profiles,metadata = bundle(tmp_path)
    first = run_once(config,out,Path.cwd())
    sid = first['snapshot_id']
    _, frozen = load_snapshot(store)
    assert first['state']=='built' and len(frozen['graph']['articles'])==1
    assert frozen['graph']['taxonomy']['schema']=='tac_terms_taxonomy_v0.4'
    assert any(t['term']=='impedance spectroscopy' for t in frozen['graph']['articles'][0]['terms'])
    again = run_once(config,out,Path.cwd())
    assert again['state']=='unchanged' and again['snapshot_id']==sid
    assert len(list((out/'runs').iterdir()))==1
    cfg = json.loads(config.read_bytes())
    other = deepcopy(snapshot['articles'][0])
    other['article_id']='synthetic-new-upload'
    snapshot['articles'].append(other)
    Path(cfg['snapshot']).write_bytes(canonical(snapshot))
    p = deepcopy(profiles['profiles'][0])
    p['article_id']=other['article_id']
    profiles['profiles'].append(p)
    profiles['snapshot_sha256']=sha(Path(cfg['snapshot']).read_bytes())
    Path(cfg['profiles']).write_bytes(canonical(profiles))
    metadata['articles'].append(dict(metadata['articles'][0],article_id=other['article_id']))
    Path(cfg['metadata']).write_bytes(canonical(metadata))
    second = run_once(config,out,Path.cwd())
    assert second['state']=='built' and second['snapshot_id']!=sid
    _, grown = load_snapshot(store)
    assert len(grown['graph']['articles'])==2
    assert {t['term_id'] for t in grown['graph']['articles'][0]['terms']}.isdisjoint(
        {t['term_id'] for t in grown['graph']['articles'][1]['terms']})
    assert load_snapshot(store,sid)[1]==frozen


def test_failed_source_binding_retains_previous_active_snapshot_and_cache_tamper_is_rejected(tmp_path):
    config,out,store,_,profiles,_ = bundle(tmp_path)
    first = run_once(config,out,Path.cwd())
    cfg = json.loads(config.read_bytes())
    original = Path(cfg['profiles']).read_bytes()
    profiles['profiles'][0]['sections'][0]['quote']='invented evidence'
    Path(cfg['profiles']).write_bytes(canonical(profiles))
    with pytest.raises(RuntimeError,match='failed'):
        run_once(config,out,Path.cwd())
    assert current_snapshot(store)==first['snapshot_id']
    Path(cfg['profiles']).write_bytes(original)
    Path(first['table']).write_text('corrupted output',encoding='utf-8')
    with pytest.raises(ValueError,match='checksum mismatch'):
        run_once(config,out,Path.cwd())
    assert not (store/'pipeline.lock').exists()


def test_changed_snapshot_retires_old_tac_and_metadata_automatically(tmp_path):
    config,out,store,snapshot,_,_=bundle(tmp_path)
    initial=run_once(config,out,Path.cwd())
    cfg=json.loads(config.read_bytes())
    extra=deepcopy(snapshot['articles'][0])
    extra['article_id']='new-scope-from-updated-corpus'
    snapshot['articles'].append(extra)
    Path(cfg['snapshot']).write_bytes(canonical(snapshot))
    rebuilt=run_once(config,out,Path.cwd())
    assert rebuilt['state']=='built' and rebuilt['snapshot_id']!=initial['snapshot_id']
    assert len(rebuilt['retired_inputs'])==2
    _, frozen=load_snapshot(store)
    assert len(frozen['graph']['articles'])==2
    assert all(c['boundary_status']=='unreviewed' for a in frozen['graph']['articles'] for c in a['contexts'])


def test_concurrent_writer_guard_and_workspace_path_boundary(tmp_path):
    config,out,store,*_ = bundle(tmp_path)
    store.mkdir()
    lock=store/'pipeline.lock'
    lock.mkdir()
    (lock/'owner.json').write_text('another active writer')
    with pytest.raises(FileExistsError):
        run_once(config,out,Path.cwd())
    assert (lock/'owner.json').read_text()=='another active writer'
    with pytest.raises(ValueError,match='outside source root'):
        run_once(config,Path.cwd().parent/'outside-workspace',Path.cwd())


def test_code_and_input_change_fingerprints_are_distinct(tmp_path):
    config,_,_,snapshot,_,_=bundle(tmp_path)
    before=capture(config,Path.cwd())[2]
    cfg=json.loads(config.read_bytes())
    snapshot['articles'][0]['title']='Different frozen metadata'
    Path(cfg['snapshot']).write_bytes(canonical(snapshot))
    assert capture(config,Path.cwd())[2]!=before
