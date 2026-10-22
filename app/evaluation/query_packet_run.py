"""Freeze questions, capture the unchanged answer context without inference, then build offline packets."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Chunk, PageTextLayer
from app.documents.service import PageLayer
from app.evaluation.answer_trace import PreparationComplete, TraceCollector
from app.evaluation.context_compaction import SourcePage, complete_pages_in_request
from app.evaluation.query_packet import VERSION, aligned_pages, build_packet
from app.generation.providers import AnswerLanguage, AnswerStyle, Evidence, OpenAIAnswerProvider, ProviderResult
from app.generation.service import answer_question
from app.records.condition_transfer_export import read_frozen
from app.records.extraction import write_json
from app.records.multi_run import verify_hashes
from app.records.openai_backend import responses_content
from app.records.protocol_association import VERSION as ASSOCIATION_VERSION
from app.records.protocol_association import AssociationReply, parse_reply, resolve_reply, validate_case
from app.records.protocol_association_run import load as load_associations
from app.records.schema import SourceRegion
from app.records.sources import file_hash, source_region_from_page, verify_live_region

QUESTIONS = (
    ('conductivity_protocol', 'Каким методом измеряли проводимость мембран и как выполняли уравновешивание образцов перед измерением?'),
    ('dsc_protocol', 'For Istomina 2021, what conditions and temperature programme were used for DSC measurements?'),
    ('preparation_atmosphere', 'Можно ли считать атмосферу подготовки ячеек средой измерения проводимости?'),
    ('absent_material', 'What conductivity was reported for Nafion membranes containing Mars regolith?'),
)
CODE = ('app/evaluation/query_packet.py', 'app/evaluation/query_packet_run.py', 'scripts/query_evidence_packet.py',
        'tests/unit/test_query_evidence_packet.py', 'docs/records/query_packet_protocol_v0.1.md')
SUPPORT = ('app/generation/service.py', 'app/generation/providers.py', 'app/generation/evidence_selection.py',
           'app/generation/evidence_adequacy.py', 'app/generation/required_concepts.py', 'app/retrieval/search.py',
           'app/retrieval/vector_index.py', 'app/retrieval/cross_lingual.py', 'app/retrieval/cross_lingual_glossary.yaml',
           'app/records/sources.py', 'app/db/models.py', 'app/documents/service.py', 'app/evaluation/answer_trace.py')


class CaptureOnlyProvider(OpenAIAnswerProvider):
    """Use production formatting but stop before any generation, with no real credential."""
    def __init__(self) -> None:
        super().__init__(base_url='https://api.openai.com/v1', api_key='capture-only-not-a-credential',
                         model='not-called', timeout_seconds=1, max_tokens=1)

    def generate(self, question: str, evidence: list[Evidence], *, answer_style: AnswerStyle = 'claims',
                 answer_language: AnswerLanguage = 'auto') -> ProviderResult:
        raise PreparationComplete('Query packet capture stops before inference')


def prepare(association_prepared: Path, association_run: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load_associations(association_prepared)
    manifest, additions = read_frozen(association_run, ASSOCIATION_VERSION, Path.cwd())
    if manifest['phase'] != 'executed_bounded_api':
        raise ValueError('Query packet requires executed frozen associations')
    if any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Association preparation/run source bindings conflict')
    bindings.update(additions)
    report = json.loads((association_run / 'report.json').read_bytes())
    if [r['case_id'] for r in report['results']] != [c['case_id'] for c in plan['cases']]:
        raise ValueError('Query packet association case inventory differs')
    associations = []
    for case, result in zip(plan['cases'], report['results'], strict=True):
        if result['status'] != 'integrity_valid':
            raise ValueError('Query packet preparation requires explicitly replayable source-valid association replies')
        reply = parse_reply(responses_content((association_run / case['case_id'] / 'response.json').read_bytes()))
        if resolve_reply(case, reply) != result['resolved']:
            raise ValueError('Association raw replay differs before query packet preparation')
        associations.append({'case': case, 'reply': reply.model_dump(mode='json')})
    code = {str(Path(n).resolve()): file_hash(Path(n)) for n in (*CODE, *SUPPORT)}
    verify_hashes(bindings | code)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', {'version': VERSION, 'questions': [{'id': i, 'question': q} for i, q in QUESTIONS],
        'associations': associations, 'collection': 'literature', 'method': 'hybrid_cross_lingual', 'top_k': 5,
        'answer_style': 'claims', 'answer_language': 'auto', 'new_model_calls': 0,
        'exposure': 'Development questions/source associations; no independent scientific reference labels.'})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'prepared_before_current_context_capture',
        'inputs': bindings, 'code': code, 'outputs': {'plan.json': file_hash(output / 'plan.json')}})
    return {'questions': len(QUESTIONS), 'association_cases': len(associations), 'new_model_calls': 0}


def load(prepared: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest, bindings = read_frozen(prepared, VERSION, Path.cwd())
    if manifest['phase'] != 'prepared_before_current_context_capture' or 'plan.json' not in manifest['outputs']:
        raise ValueError('Query packet requires a separate prepared plan')
    expected = {str(Path(n).resolve()): file_hash(Path(n)) for n in (*CODE, *SUPPORT)}
    if manifest['code'] != expected:
        raise ValueError('Query packet code inventory differs from frozen preparation')
    plan = json.loads((prepared / 'plan.json').read_bytes())
    if (plan['version'] != VERSION or [(q['id'], q['question']) for q in plan['questions']] != list(QUESTIONS)
            or (plan['collection'], plan['method'], plan['top_k'], plan['answer_style'], plan['answer_language'])
            != ('literature', 'hybrid_cross_lingual', 5, 'claims', 'auto')):
        raise ValueError('Query packet questions or baseline settings changed')
    return plan, bindings


def collect_sources(session: Session, settings: Settings, evidence: list[Evidence]) -> dict[str, Any]:
    chunks: dict[str, Any] = {}
    pages: dict[str, Any] = {}
    layers: dict[str, str] = {}
    diagnostics: list[dict[str, Any]] = []
    for item in evidence:
        if item.source_type == 'table_derived':
            diagnostics.append({'citation_id': item.citation_id, 'state': 'derived_source_retained_without_raw_chunk_binding'})
            continue
        chunk = session.get(Chunk, UUID(item.chunk_id))
        if chunk is None:
            raise ValueError('Current answer evidence chunk is missing from the read-only database snapshot')
        if str(chunk.article_id) != item.article_id:
            raise ValueError('Current answer chunk belongs to a different article')
        layers[item.chunk_id] = chunk.text_layer
        chunks[item.chunk_id] = {'article_id': str(chunk.article_id), 'text_layer': chunk.text_layer,
            'page_start': chunk.page_start, 'page_end': chunk.page_end, 'source_type': chunk.source_type, 'text': chunk.text}
        if chunk.text != item.text:
            layers.pop(item.chunk_id)
            diagnostics.append({'citation_id': item.citation_id, 'state': 'baseline_text_differs_from_raw_chunk_no_association_binding'})
        for number in range(item.page_start, item.page_end + 1):
            key = f'{item.article_id}:{number}:{chunk.text_layer}'
            if key in pages:
                continue
            row = session.scalars(select(PageTextLayer).where(PageTextLayer.article_id == chunk.article_id,
                PageTextLayer.page_number == number, PageTextLayer.layer_type == chunk.text_layer)).one_or_none()
            if row is not None and not row.text:
                diagnostics.append({'citation_id': item.citation_id, 'page': number, 'state': 'empty_registered_text_page'})
                continue
            region = source_region_from_page(session, settings, chunk.article_id, number, layer=cast(PageLayer, chunk.text_layer),
                selection_basis='retrieval', selection_note='Read-only current answer context capture; no scientific acceptance.')
            pages[key] = region.model_dump(mode='json')
    return {'chunks': chunks, 'pages': pages, 'chunk_layers': layers, 'diagnostics': diagnostics}


def capture(prepared: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    from app.db.session import SessionLocal
    settings = Settings()
    index_root = settings.data_root / 'processed' / 'vector_indexes'
    index_hashes = {str(p.resolve()): file_hash(p) for p in sorted(index_root.rglob('*')) if p.is_file()}
    bindings.update(index_hashes)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with SessionLocal() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        for entry in plan['associations']:
            verify_live_region(session, settings, validate_case(entry['case']))
        for query in plan['questions']:
            observer, provider = TraceCollector(), CaptureOnlyProvider()
            baseline_status = 'context_prepared_before_generation'
            try:
                answer = answer_question(session, settings, query['question'], collection=plan['collection'], method=plan['method'],
                    top_k=plan['top_k'], answer_style=plan['answer_style'], answer_language=plan['answer_language'],
                    provider=provider, trace_observer=observer)
                baseline_status = answer.status
            except PreparationComplete:
                pass  # Explicit pre-generation boundary, not a model answer or scientific abstention.
            if observer.trace is None:
                raise ValueError('Current answer context capture did not observe the real pipeline')
            evidence = [Evidence(**e) for e in observer.trace['evidence']]
            source = collect_sources(session, settings, evidence)
            for raw in source['pages'].values():
                region = SourceRegion.model_validate(raw)
                bindings[str(Path(region.original_pdf_path).resolve())] = region.original_pdf_sha256
                bindings[str(Path(region.layer_pdf_path).resolve())] = region.layer_pdf_sha256
            rows.append({**query, 'baseline_status': baseline_status, 'trace': observer.trace, 'sources': source,
                         'current_prompt': provider._user_prompt(query['question'], evidence,
                             answer_style=plan['answer_style'], answer_language=plan['answer_language'])})
        session.rollback()
    verify_hashes(bindings)
    write_json(output / 'capture.json', {'version': VERSION, 'queries': rows, 'new_model_calls': 0,
        'baseline': {k: plan[k] for k in ('collection', 'method', 'top_k', 'answer_style', 'answer_language')}})
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'read_only_current_context_captured', 'inputs': bindings,
        'code': {}, 'outputs': {'capture.json': file_hash(output / 'capture.json')}})
    return {'questions': len(rows), 'baseline_statuses': [r['baseline_status'] for r in rows],
            'selected_evidence_items': sum(len(r['trace']['evidence']) for r in rows), 'new_model_calls': 0}


def export(prepared: Path, captured: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(output)
    plan, bindings = load(prepared)
    manifest, additions = read_frozen(captured, VERSION, Path.cwd())
    if manifest['phase'] != 'read_only_current_context_captured':
        raise ValueError('Query packet export requires an unchanged read-only capture')
    if any(n in bindings and bindings[n] != h for n, h in additions.items()):
        raise ValueError('Query packet capture/preparation bindings conflict')
    bindings.update(additions)
    current = json.loads((captured / 'capture.json').read_bytes())
    if [(q['id'], q['question']) for q in current['queries']] != [(q['id'], q['question']) for q in plan['questions']]:
        raise ValueError('Query packet capture question inventory differs')
    associations = [(a['case'], AssociationReply.model_validate(a['reply'])) for a in plan['associations']]
    rows, cards = [], []
    for row in current['queries']:
        evidence = [Evidence(**e) for e in row['trace']['evidence']]
        regions = [SourceRegion.model_validate(r) for r in row['sources']['pages'].values()]
        by_chunk = {e.chunk_id: [r for r in regions if str(r.article_id) == e.article_id
                    and e.page_start <= r.page_number <= e.page_end
                    and r.text_layer == row['sources']['chunk_layers'].get(e.chunk_id)] for e in evidence}
        packet = build_packet(row['question'], evidence, row['sources']['chunk_layers'], associations, page_sources=by_chunk)
        pages = [SourcePage(str(r.article_id), r.region_id, r.page_number, r.text_layer, str(r.text_layer_id),
                            r.page_text, r.layer_pdf_path, r.layer_pdf_sha256) for r in regions]
        baseline_pages = complete_pages_in_request(row['current_prompt'], pages)
        candidate_pages = complete_pages_in_request('\n'.join(e['text'] for e in packet['wire']['evidence']), pages)
        scope_proven = bool(pages) and not row['sources']['diagnostics'] and all(
            aligned_pages(e, by_chunk[e.chunk_id], row['sources']['chunk_layers'].get(e.chunk_id)) for e in evidence)
        packet['scope'] = {'baseline_complete_pages': baseline_pages, 'candidate_complete_pages': candidate_pages,
            'page_registry_proven': scope_proven, 'network_eligible': scope_proven and not candidate_pages
                and packet['budget_status'] == 'within_budget' and row['baseline_status'] == 'context_prepared_before_generation',
            'diagnostic': 'Literal scope/budget check only; no inference or scientific context adequacy claim.'}
        rows.append({**row, 'packet': packet, 'baseline_prompt_bytes': len(row['current_prompt'].encode('utf-8'))})
        pdfs = ''.join('<a href="' + html.escape(Path(r.original_pdf_path).resolve().as_uri() + '#page=' + str(r.page_number), quote=True)
                      + '">PDF p.' + str(r.page_number) + '</a> ' for r in regions)
        def detail(label: str, value: Any) -> str:
            return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
                value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'
        cards.append('<article class="query"><h2>' + html.escape(row['id']) + '</h2><p>' + html.escape(row['question'])
            + '</p>' + pdfs + detail('Исходный контекст answer_question', row)
            + detail('Новый пакет: все evidence, связи и неопределённости', packet) + '</article>')
    summary = {'questions': len(rows), 'baseline_evidence_items': sum(len(r['trace']['evidence']) for r in rows),
        'anchored_contexts': sum(len(r['packet']['contexts']) for r in rows),
        'added_blocks': sum(len(r['packet']['attachments']) for r in rows),
        'network_eligible_packets': sum(r['packet']['scope']['network_eligible'] for r in rows),
        'new_model_calls': 0, 'scientific_precision': None, 'scientific_recall': None, 'scientific_admission': 'not_evaluated'}
    html_page = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — query evidence packets</title>'
        '<style>body{font:16px system-ui;margin:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto}'
        'article{border-top:1px solid #789;padding:12px}input{padding:10px;width:65%}[hidden]{display:none!important}</style>'
        '<h1>Пакеты доказательств под запрос</h1><p>' + html.escape(VERSION)
        + '. Offline development comparison, не новые ответы модели. Baseline evidence не удаляется; связи остаются предложениями.</p>'
        '<pre>' + html.escape(json.dumps(summary, ensure_ascii=False, indent=2)) + '</pre>'
        '<a href="report.json">JSON</a> · <a href="manifest.json">Manifest</a><p><label>Поиск <input id="q" type="search"></label></p>'
        + ''.join(cards) + '<script>const rows=[...document.querySelectorAll("article.query")];document.getElementById("q")'
        '.addEventListener("input",e=>{const q=e.target.value.toLocaleLowerCase();for(const r of rows)'
        'r.hidden=!r.textContent.toLocaleLowerCase().includes(q)});</script></html>\n')
    verify_hashes(bindings)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'report.json', {'version': VERSION, 'summary': summary, 'queries': rows})
    (output / 'review.html').write_text(html_page, encoding='utf-8')
    write_json(output / 'manifest.json', {'version': VERSION, 'phase': 'offline_packet_comparison', 'inputs': bindings, 'code': {},
        'outputs': {p.name: file_hash(p) for p in sorted(output.iterdir()) if p.is_file()}})
    return summary
