"""Pin three visually reviewed electrolyte-unit and anion-charge minuses on PDF2."""
from __future__ import annotations

import json
from pathlib import Path

import fitz

from scripts import gigachat_answer_smoke as f

BASE = f.ROOT / 'output/nambu_conductivity_explanation_20261111'
PDF = f.ROOT / 'data/pdf/5cafe6e931ef4dc7_Nambu_2016.pdf'


def main():
    fixture = json.loads((f.ROOT / 'tests/fixtures/nambu_conductivity_explanation_source_v01.json').read_bytes())
    parents = [e for e in fixture['trace']['evidence'] if e['page_start'] == 2 and e['page_end'] == 3]
    if len(parents) != 1:
        raise ValueError('One complete selected PDF2 parent required')
    source = parents[0]
    observations, operations = [], []
    with fitz.open(PDF) as document:
        for pno in (2,):
            page = document[pno - 1]
            text = page.get_text()
            start = text.index('We used LiPF6')
            end = text.index('may serve as an anion-attracting group.', start) + len('may serve as an anion-attracting group.')
            targets = {i for i in range(start, end) if text[i] == '¹'}
            if len(targets) != 3 or text.strip() not in source['text']:
                raise ValueError('Unexpected raw glyph or source-page scope')
            raw_base = source['text'].index(text.strip()) - len(text) + len(text.lstrip())
            position, seen = 0, set()
            for block in page.get_text('rawdict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        for char in span['chars']:
                            offset = text.find(char['c'], position)
                            if offset < 0:
                                raise ValueError('Positioned character mapping failed')
                            position = offset + len(char['c'])
                            if offset not in targets:
                                continue
                            fonts = [row for row in page.get_fonts() if row[3].split('+', 1)[-1] == span['font']]
                            if len(fonts) != 1:
                                raise ValueError('Nonunique glyph font')
                            xref = fonts[0][0]
                            observation = {'pdf_page': pno, 'pdf_text_offset': offset, 'raw_character': char['c'],
                                'decoded': '−', 'font': span['font'], 'font_xref': xref,
                                'bbox': char['bbox'], 'font_program_sha256': f.sha(document.extract_font(xref)[3])}
                            observations.append(observation)
                            left = raw_base + offset
                            if source['text'][left:left + 1] != char['c']:
                                raise ValueError('Raw glyph address differs')
                            operations.append({**observation, 'raw_start': left, 'raw_end': left + 1})
                            seen.add(offset)
            if seen != targets:
                raise ValueError('Not all reviewed glyphs positioned')
    resource = f.ROOT / 'app/resources/reviewed_conductivity_explanation_glyph_aliases_v01.json'
    f.write(resource, {'policy': 'reviewed_pdf_glyph_aliases_v0.1', 'pdf_sha256': f.sha(PDF.read_bytes()),
        'reviewer': 'agent_source_visual_review', 'automatic_font_name_semantics': False,
        'entries': [{**{k: source[k] for k in ('article_id', 'chunk_id', 'page_start', 'page_end', 'source_type')},
                     'raw_sha256': f.sha(source['text'].encode()), 'operations': operations}]})
    out = BASE / 'catalogue_audit_v01'
    out.mkdir(exist_ok=False)
    f.write(out / 'observations.json', observations)
    f.write(out / 'bindings.json', f.bindings([Path(__file__), PDF, resource]))
    f.manifest(out)
    print(json.dumps({'operations': len(operations), 'parents': 1, 'catalogue_sha256': f.sha(resource.read_bytes())}))


if __name__ == '__main__':
    main()
