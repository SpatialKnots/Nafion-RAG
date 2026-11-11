"""Bind two visually reviewed concentration exponent minuses to three exact raw chunks."""

from __future__ import annotations

import json
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/nambu_order_binding_20261111'
PDF = f.ROOT / 'data/pdf/5cafe6e931ef4dc7_Nambu_2016.pdf'
PARENT = f.ROOT / 'output/peng_table_binding_20261111/comparison_v01'


def main():
    data = json.loads((PARENT / 'Nambu_06/after.json').read_bytes())['trace']['evidence']
    entries, observations = [], []
    with fitz.open(PDF) as doc:
        page = doc[1]
        text = page.get_text()
        left = text.index('We used LiPF6')
        right = text.index('The conductivities increased', left)
        targets = [i for i in range(left, right) if text[i] == '¹']
        if len(targets) != 2:
            raise ValueError('Expected exactly two reviewed unit glyphs')
        positioned, position = {}, 0
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    for char in span['chars']:
                        offset = text.find(char['c'], position)
                        if offset < 0:
                            raise ValueError('Positioned text character mapping failed')
                        position = offset + len(char['c'])
                        if offset not in targets:
                            continue
                        fonts = [row for row in page.get_fonts() if row[3].split('+', 1)[-1] == span['font']]
                        if len(fonts) != 1:
                            raise ValueError('Nonunique font')
                        xref = fonts[0][0]
                        positioned[offset] = {'raw_character': char['c'], 'decoded': '−', 'pdf_page': 2,
                            'pdf_text_offset': offset, 'font': span['font'], 'font_xref': xref, 'bbox': char['bbox'],
                            'font_program_sha256': f.sha(doc.extract_font(xref)[3])}
        if set(positioned) != set(targets):
            raise ValueError('Not all reviewed unit glyphs positioned')
        observations = list(positioned.values())
        for source in data:
            raw = source['text']
            if text.strip() not in raw:
                continue
            base_offset = raw.index(text.strip())
            operations = []
            for offset in targets:
                raw_offset = base_offset + offset - len(text) + len(text.lstrip())
                if raw[raw_offset] != '¹':
                    raise ValueError('Raw glyph binding failed')
                operations.append({**positioned[offset], 'raw_start': raw_offset, 'raw_end': raw_offset + 1})
            entries.append({**{k: source[k] for k in ('article_id', 'chunk_id', 'page_start', 'page_end', 'source_type')},
                'raw_sha256': f.sha(raw.encode()), 'operations': operations})
    if len(entries) != 3:
        raise ValueError('Three complete raw parents required')
    resource = f.ROOT / 'app/resources/reviewed_conductivity_glyph_aliases_v01.json'
    f.write(resource, {'policy': 'reviewed_pdf_glyph_aliases_v0.1', 'pdf_sha256': f.sha(PDF.read_bytes()),
        'reviewer': 'agent_source_visual_review', 'automatic_font_name_semantics': False,
        'scope': 'two visually reviewed concentration exponent minuses, PDF2, repeated in three exact raw parents',
        'entries': entries})
    out = BASE / 'catalogue_audit_v01'
    out.mkdir(exist_ok=False)
    f.write(out / 'observations.json', observations)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), PDF, resource, PARENT / 'manifest.json']))
    f.manifest(out)
    print(json.dumps({'entries': len(entries), 'operations': 6, 'catalogue_sha256': f.sha(resource.read_bytes())}))


if __name__ == '__main__':
    main()
