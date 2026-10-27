"""Scoped pre-inference source eligibility; no scientific or network authorization."""

from __future__ import annotations

import re
from typing import Any

from app.evaluation.dsc_context_run import guard_wire, wire_text
from app.evaluation.evidence_gaps_run import frozen_questions
from app.evaluation.query_packet import MAX_BYTES
from app.generation.query_qualifiers import extract_qualifiers, occurrences
from app.records.schema import SourceRegion

VERSION = 'dsc_source_admission_v0.1'
ROLES = {'B1': 'bibliographic_title', 'B2': 'bibliographic_authors', 'B3': 'bibliographic_publication',
    'B4': 'bibliographic_doi', 'M1': 'dsc_methods_description'}
SOURCE_CUES = {
    'dsc_instrument': r'\bDSC\b[\s\S]*?\bcalorimeter\b',
    'measurement_environment': r'\bmeasurements\s+were\s+performed\s+under\b',
    'measurement_temperature_range': r'\btemperature\s+range\s+from\b',
    'temperature_programme': r'\btemperature\s+programme\s+was\s+used\s*:',
}


def located(context: dict[str, Any], span: dict[str, Any]) -> dict[str, Any]:
    return {'citation_id': context['citation_id'], 'region_id': context['region_id'],
        'page_number': context['page_number'], 'start': context['start'] + span['start'],
        'end': context['start'] + span['end'], 'text': span['text']}


def assess(wire: dict[str, Any], sources: list[SourceRegion], plan: dict[str, Any]) -> dict[str, Any]:
    # Malformed packets fail loudly; scientific/coverage refusals below remain explicit.
    guard_wire(wire, sources, plan['pages'])
    contexts = wire['contexts']
    by_id = {c['citation_id']: c for c in contexts}
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        checks.append({'id': name, 'passed': passed, 'evidence': evidence})

    check('exact_source_packet', True, 'Unchanged SourceRegion and stage47 boundary/byte/full-page guards passed.')
    check('supported_question_scope', wire['question'] == frozen_questions()['dsc_protocol'], wire['question'])
    check('unique_citation_roles', {c['citation_id']: c['role'] for c in contexts} == ROLES,
        {c['citation_id']: c['role'] for c in contexts})
    identities = {(c['article_id'], c['original_pdf_sha256']) for c in contexts}
    check('single_registered_article', identities == {(plan['document']['article_id'], plan['document']['original_pdf_sha256'])},
        [list(identity) for identity in sorted(identities)])
    header_ok = plan['identity']['verified'] and all(
        key in by_id and by_id[key]['role'] == ROLES[key] and by_id[key]['page_number'] == 1
        and by_id[key]['text'] == plan['identity']['spans'][field]['text']
        for key, field in (('B1', 'title'), ('B2', 'authors'), ('B3', 'publication'), ('B4', 'doi')))
    check('bound_header_identity', header_ok, plan['identity'])
    method_contexts = [c for c in contexts if c['citation_id'] == 'M1' and c['role'] == ROLES['M1']]
    method = method_contexts[0] if len(method_contexts) == 1 else None
    qualifiers, warnings = extract_qualifiers(wire['question'])
    qualifier_results = []
    for qualifier in qualifiers:
        matches = []
        if qualifier.kind == 'article':
            authors, publication = by_id.get('B2'), by_id.get('B3')
            if (header_ok and authors and publication and authors['article_id'] == publication['article_id']
                    and authors['role'] == ROLES['B2'] and publication['role'] == ROLES['B3']):
                author_hits = occurrences(authors['text'], qualifier.aliases[0])
                year_hits = occurrences(publication['text'], str(qualifier.year))
                if author_hits and year_hits:
                    matches = [located(authors, h) for h in author_hits] + [located(publication, h) for h in year_hits]
        elif qualifier.kind == 'method_or_property_mention' and method:
            matches = [located(method, h) for alias in qualifier.aliases for h in occurrences(method['text'], alias)]
        qualifier_results.append({'qualifier_kind': qualifier.kind, 'key': qualifier.key,
            'state': 'mentioned' if matches else 'not_established', 'source_spans': matches})
    check('necessary_query_mentions', bool(qualifier_results) and not warnings
        and all(q['state'] == 'mentioned' for q in qualifier_results),
        {'parse_warnings': warnings, 'qualifiers': qualifier_results, 'meaning': 'necessary_mentions_only_not_entailment'})
    cue_matches: dict[str, Any] = {}
    for name, pattern in SOURCE_CUES.items():
        hits = list(re.finditer(pattern, method['text'], re.IGNORECASE)) if method else []
        spans = [located(method, {'start': h.start(), 'end': h.end(), 'text': h.group()}) for h in hits] if method else []
        cue_matches[name] = spans
        check(name, bool(spans), {'pattern': pattern, 'source_spans': spans, 'meaning': 'finite_source_wording_only'})
    programme = cue_matches['temperature_programme']
    actions = []
    if method and len(programme) == 1:
        begin = programme[0]['end'] - method['start']
        actions = [located(method, {'start': begin + h.start(), 'end': begin + h.end(), 'text': h.group()})
            for h in re.finditer(r'\b(?:heating|cooling)\b', method['text'][begin:], re.IGNORECASE)]
    check('programme_action_order', [a['text'].lower() for a in actions] == ['heating', 'cooling', 'heating'],
        {'source_spans': actions, 'meaning': 'raw_action_order_no_numeric_or_scientific_interpretation'})
    method_pages = [p for p in plan['pages'] if p['page_number'] == 4]
    boundaries = bool(method and len(method_pages) == 1 and method_pages[0]['mapping_diagnostic'] is None
        and method['text'].rstrip().endswith('.'))
    check('source_context_boundaries', boundaries, 'Complete section bounded by headings; original mapping and terminal punctuation.')
    expected_unknowns = {'sample_identity': 'not_established', 'per_result_applicability': 'not_established',
        'scientific_acceptance': 'not_evaluated'}
    check('unknowns_preserved', wire.get('unknowns') == expected_unknowns, wire.get('unknowns'))
    check('actual_wire_budget', len(wire_text(wire).encode('utf-8')) <= MAX_BYTES,
        {'wire_bytes': len(wire_text(wire).encode('utf-8')), 'byte_ceiling': MAX_BYTES, 'provider_envelope': 'not_constructed'})
    blockers = [c['id'] for c in checks if not c['passed']]
    eligible = not blockers
    return {'version': VERSION, 'question': wire['question'], 'checks': checks,
        'source_packet_eligible_for_frozen_experiment': eligible,
        'source_packet_status': 'eligible_for_frozen_experiment_preparation' if eligible else 'blocked_by_current_source_checks',
        'current_source_blocking_reasons': blockers,
        'historical_blocking_reasons': plan['historical_blocking_reasons'],
        'execution': {'network_ready': False, 'api_calls_authorized': False, 'generation_performed': False,
            'external_request_constructed': False,
            'blocking_reasons': ['active_user_api_prohibition', 'frozen_experiment_contract_not_prepared',
                'provider_request_for_this_packet_not_constructed_or_validated']},
        'scientific_acceptance': 'not_evaluated', 'independent_scientific_reference': False,
        'limitations': ['exposed_source_development_not_independent_gold', 'finite_english_source_cues',
            'mentions_and_action_order_do_not_prove_scientific_truth', 'no_numeric_interpretation',
            'no_per_result_assignment', 'no_general_entailment_or_corpus_completeness_claim'],
        'summary': {'source_checks': len(checks), 'source_checks_passed': sum(c['passed'] for c in checks),
            'current_source_blockers': len(blockers), 'historical_blockers_retained': len(plan['historical_blocking_reasons']),
            'wire_bytes': len(wire_text(wire).encode('utf-8')), 'network_ready': False,
            'model_calls': 0, 'retrieval_calls': 0, 'embedding_calls': 0, 'database_access': False}}
