"""Build reviewed glyph-only operations from exact original-page observations."""

from __future__ import annotations

import json
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f
from scripts.peng_glyph_probe_20261111 import BASE, PDF

POLICY = 'reviewed_pdf_glyph_aliases_v0.1'
CATALOGUE = f.ROOT / 'app/resources/reviewed_pdf_glyph_aliases_v01.json'
REPLACEMENTS = {'\x01': '−', '\x03': '~', '\ue09d': 'ft'}


def read(path):
    return json.loads(path.read_bytes())


def main():
    probe = BASE / 'pdf_probe_v01'
    f.verify_manifest(probe)
    f.verify(read(probe / 'bindings.json'))
    chunks = read(f.ROOT / 'output/refusal_groups_20261110/capture_v01/chunks.json')
    parent = f.ROOT / 'output/quantitative_binding_20261111/comparison_v05'
    selected = {e['chunk_id'] for cid in ('Peng_05', 'Peng_08')
                for e in read(parent / cid / 'after.json')['trace']['evidence']}
    observations, pages = read(probe / 'observations.json'), {}
    with fitz.open(PDF) as doc:
        for pno in (4, 5):
            text = doc[pno - 1].get_text()
            positions = [(i, c) for i, c in enumerate(text) if c in REPLACEMENTS]
            observed = [o for o in observations if o['page'] == pno]
            if [c for _, c in positions] != [o['raw_character'] for o in observed]:
                raise ValueError('Original text and positioned glyph streams differ')
            pages[pno] = (text, {pos: o for (pos, _), o in zip(positions, observed, strict=True)})
    entries = []
    for cid in sorted(selected):
        chunk, operations = chunks[cid], []
        raw = chunk['text']
        for i, char in enumerate(raw):
            if char not in REPLACEMENTS:
                continue
            left, right = max(0, i - 35), min(len(raw), i + 36)
            context, matches = raw[left:right], []
            for pno, (text, glyphs) in pages.items():
                if not chunk['page_start'] <= pno <= chunk['page_end']:
                    continue
                at = text.find(context)
                if at < 0 or text.find(context, at + 1) >= 0:
                    continue
                pos = at + i - left
                if pos not in glyphs:
                    raise ValueError('Glyph address mismatch')
                matches.append((pno, pos, glyphs[pos]))
            if len(matches) != 1:
                # Other pages and uncertain contexts remain deliberately unaltered.
                continue
            pno, pos, observed = matches[0]
            operations.append({'raw_start': i, 'raw_end': i + 1, 'raw_character': char,
                'decoded': REPLACEMENTS[char], 'pdf_page': pno, 'pdf_text_offset': pos,
                'font': observed['font'], 'font_xref': observed['font_xref'],
                'font_program_sha256': observed['font_program_sha256'], 'bbox': observed['bbox']})
        if operations:
            entries.append({k: chunk[k] for k in ('article_id', 'chunk_id', 'page_start', 'page_end',
                            'source_type', 'text_layer')} | {'raw_sha256': f.sha(raw.encode()), 'operations': operations})
    catalogue = {'policy': POLICY, 'pdf_sha256': f.sha(PDF.read_bytes()),
        'review_basis': 'agent_visual_review_of_complete_Poppler_pages_4_and_5_and_positioned_embedded_font_glyphs',
        'automatic_font_name_semantics': False, 'scientific_validity': 'not_evaluated', 'entries': entries}
    CATALOGUE.parent.mkdir(exist_ok=True)
    f.write(CATALOGUE, catalogue)
    audit = BASE / 'catalogue_audit_v01'
    audit.mkdir()
    f.write(audit / 'catalogue.json', catalogue)
    f.write(audit / 'bindings.json', f.bindings([Path(__file__), CATALOGUE, PDF, probe / 'manifest.json']))
    f.manifest(audit)
    print(json.dumps({'entries': len(entries), 'operations': sum(len(e['operations']) for e in entries)}))


if __name__ == '__main__':
    main()
