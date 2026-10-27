"""Finite lexical evidence inventories; never scientific relation resolution."""

from __future__ import annotations

import re
from typing import Any

from app.records.schema import text_hash

VERSION = 'evidence_gap_audit_v0.2'
PATTERNS = {
    'conductivity': r'conductiv|проводим',
    'impedance': r'impedance|импеданс',
    'dsc': r'\bDSC\b|\bДСК\b|calorim|калорим',
    'sample': r'membrane|мембран|sample|образц|na(?:fi|ﬁ)on|нафион',
    'nafion': r'na(?:fi|ﬁ)on|нафион',
    'equilibration': r'equilibr|равновес|уравновеш|выдерж|stabili[sz]|стабилиз|condition(?:ed|ing)',
    'atmosphere': r'argon|аргон|nitrogen|азот|atmospher|атмосфер|vacuum|вакуум|inert|инерт|\bair\b|воздух',
    'programme': r'heat|cool|нагрев|охлажд|\brate\b|скорост|температур|temperature|\d\s*[°◦]\s*[CСK]',
    'mars': r'\bmars\b|марс',
    'regolith': r'regolith|реголит',
}
# Question-specific requirements, not a universal sample/method/condition schema.
REQUIREMENTS = {
    'conductivity_protocol': (
        ('conductivity', 'Сведения об измерении проводимости'),
        ('impedance', 'Указание метода измерения'),
        ('equilibration', 'Уравновешивание образцов перед измерением'),
        ('sample', 'Идентификация применимых образцов'),
    ),
    'dsc_protocol': (('dsc', 'Методика DSC'), ('programme', 'Условия и температурная программа DSC')),
    'preparation_atmosphere': (
        ('atmosphere', 'Атмосфера подготовки и отдельно среда измерения'),
        ('impedance', 'Контекст измерения проводимости'),
    ),
    'absent_material': (
        ('mars', 'Явный Mars qualifier'), ('regolith', 'Явный regolith qualifier'),
        ('nafion', 'Явное название Nafion'), ('conductivity', 'Контекст проводимости'),
    ),
}
RELATIONS = {
    'conductivity_protocol': (
        'Нужно явное указание, к каким образцам относится метод и процедура уравновешивания; '
        'общая методика или соседние упоминания не устанавливают связь.',
        'Проверить раздел методики и ссылки на образцы/таблицы; сохранить явные ограничения области применимости.',
    ),
    'dsc_protocol': (
        'Нужен исходный абзац DSC именно запрошенной статьи с условиями и программой; '
        'совпадение температурных терминов или чужая статья этого не устанавливает.',
        'Сопоставить полный абзац DSC, названные образцы и описанную программу; не заимствовать условия других методов.',
    ),
    'preparation_atmosphere': (
        'Нужно прямое указание среды при измерении или явная связь с атмосферой подготовки. '
        'Подготовка в аргоне сама по себе не доказывает измерение в аргоне.',
        'Проверить отдельно предложения о сборке/подготовке и о выполнении измерения; при отсутствии связи оставить unknown.',
    ),
    'absent_material': (
        'Отрицательный контроль: нужна поддержка всей предпосылки Nafion + Mars regolith + conductivity, '
        'если источник действительно её содержит. Существование такого измерения не предполагается.',
        'Показать неподдержанные qualifiers и фактически проверенные источники; '
        'не создавать измерение и не заявлять отсутствие во всём корпусе.',
    ),
}


def inventory(text: str, offset: int = 0) -> dict[str, list[dict[str, Any]]]:
    return {key: [{'start': offset + m.start(), 'end': offset + m.end(), 'text': m.group()}
                  for m in re.finditer(pattern, text, re.IGNORECASE)] for key, pattern in PATTERNS.items()}


def search_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits = []
    for page in pages:
        for block in page['blocks']:
            raw = page['text'][block['page_start']:block['page_end']]
            matches = {k: v for k, v in inventory(raw, block['page_start']).items() if v}
            if matches:
                hits.append({'page_ref': page['page_ref'], 'start': block['page_start'], 'end': block['page_end'],
                    'text': raw, 'text_sha256': text_hash(raw), 'bbox': block['bbox'], 'matches': matches,
                    'interpretation': 'lexical_candidate_only_negation_citation_and_applicability_not_resolved'})
    return hits


def in_packet(hit: dict[str, Any], page: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    # Exact block containment only; no substring/fuzzy or cross-article matching.
    return any(row['selected'] and row['source']['article_id'] == page['article_id']
        and row['source']['original_pdf_sha256'] == page['original_pdf_sha256']
        and row['source']['text_layer'] == page['text_layer']
        and row['source']['text_layer_id'] == page['text_layer_id']
        and row['source']['page'] == page['page_number'] and row['start'] <= hit['start']
        and row['end'] >= hit['end'] and row['text'][hit['start'] - row['start']:hit['end'] - row['start']] == hit['text']
        for row in rows)


def document_checklist(question_id: str, document: dict[str, Any], pages: list[dict[str, Any]],
                       hits: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_page = {p['page_ref']: p for p in pages}
    own_hits = [(i, h) for i, h in enumerate(hits) if by_page[h['page_ref']]['article_id'] == document['article_id']]
    own_pages = [p for p in pages if p['article_id'] == document['article_id']]
    attribution = question_id != 'dsc_protocol' or document.get('requested_identity_verified', False)
    requirements = []
    for key, label in REQUIREMENTS[question_id]:
        indices = [i for i, h in own_hits if key in h['matches']]
        selected = [i for i, h in own_hits if key in h['matches'] and in_packet(h, by_page[h['page_ref']], rows)]
        state = ('source_identity_unresolved' if not attribution else 'not_inspected' if not own_pages
            else 'supported_in_packet' if selected else 'found_outside_packet' if indices
            else 'not_found_in_inspected_scope')
        requirements.append({'key': key, 'required_evidence': label, 'status': state, 'hit_indices': indices,
            'selected_hit_indices': selected, 'support_scope': 'exact_lexical_source_presence_only_not_scientific_entailment',
            'gap': 'Научная роль и применимость найденного текста не установлены.' if indices
                else 'Буквальный признак не найден в проверенном поисковом тексте; это не отсутствие сведений в PDF.',
            'next_check': RELATIONS[question_id][1]})
    return {'article_id': document['article_id'], 'requirements': requirements,
        'historical_sample_bindings': [{'node_id': row['node_id'], 'source': row['source'],
            'event_context': event['context'], 'bindings': event['bindings'],
            'original_guards': event['original_guards'],
            'original_boundary_diagnostics': event['original_boundary_diagnostics']}
            for row in rows if row['source']['article_id'] == document['article_id'] and row['selected']
            for event in row['events'] if event['bindings']],
        'relation': {'status': 'relation_unresolved', 'required_evidence': RELATIONS[question_id][0],
            'next_check': RELATIONS[question_id][1], 'priority': 'blocking', 'automatically_resolved': False},
        'coverage': {'text_pages': len(own_pages), 'empty_text_pages': [p['page_number'] for p in own_pages if not p['text'].strip()],
            'unproven_mapping_pages': [p['page_number'] for p in own_pages if p['mapping_diagnostic']],
            'visual_coverage': 'not_inspected_by_algorithm', 'ocr_performed': False},
        'all_qualifiers_cooccurring_is_not_entailment': question_id == 'absent_material'}
