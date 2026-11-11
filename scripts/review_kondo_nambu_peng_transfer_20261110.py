"""Open committed references only after closure; compare immutable actual results."""

from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

from app.generation.providers import _clean_generation_evidence_text
from scripts import gigachat_answer_smoke as f
from scripts import kondo_nambu_peng_transfer_20261110 as run

NOTES = {
    'Nambu_03': ('main_requested_content_agrees',
        'Порядок FETFEE > ETFEE≈EFEE > DEE и температурный тренд совпадают. Диапазон10–70°C не повторён; '
        'это полезная оговорка источника, но вопрос не запрашивает конкретные границы.'),
    'Nambu_10': ('unsupported_confirmation_status',
        '120 мА·ч/г на50-м цикле совпало. Однако native утверждает «состав подтверждён», '
        'тогда как источник использует can form/may, а эталон отделяет предположение от идентификации. '
        'Finite guard эту смысловую ошибку не проверял.'),
    'Peng_01': ('incomplete_composition_and_chemical_name_drift',
        'Растворители и объёмная/массовая основы в основном воспроизведены. Во всех четырёх составах опущен '
        '1M LiPF6. Развёрнутое название FEMC изменено относительно 2,2,2-trifluoroethyl methyl carbonate.'),
    'Peng_03': ('main_trend_and_explanation_agree_scope_caveat',
        'Пониженная проводимость/повышенная вязкость и преимущество электрохимического поведения FFT отражены. '
        'Авторский текст о3C относится к LCO/Li-полуячейке; native не различает явно полуячейку и полную ячейку.'),
    'Peng_04': ('all_requested_voltage_ranges_agree',
        'Все три запрошенных диапазона совпали. Дополнительные условия0.1C/0.5C из эталона не объявляются '
        'обязательными частями вопроса, который запрашивает только диапазоны напряжения.'),
    'Peng_09': ('main_cathode_limitation_agrees',
        'Основной вывод о большей роли катода для высоковольтной полной ячейки совпадает. '
        'Он действительно присутствует в процитированном E1, во вводном тексте PDF2. '
        'Детали EET–EE, окислительной устойчивости/CEI не раскрыты.'),
}
PATTERNS = {
    'Nambu_03': [('E2', r'FETFEE\s*>\s*ETFEE.*?DEE\.')],
    'Nambu_10': [('E2', r'The discharge capacity in the EC[–−-]FETFEE system.*?other systems over 50 cycles\.'),
                 ('E2', r'The cathodic decomposition of the FETFEE.based.*?surface\s+ﬁlm\.')],
    'Peng_01': [('E1', r'2,2,2.tri.*?methyl carbonate \(FEMC\)'),
                ('E1', r'The\s+base electrolyte was 1 M LiPF6.*?weight\.\s*2\.2')],
    'Peng_03': [('E2', r'FFT provides relatively worst ionic transport property\.'),
                ('E2', r'FFT\s+electrolyte also oﬀers enhanced rate capability.*?LCO/Li cell\.')],
    'Peng_04': [('E2', r'The LCO/Li, MCMB/Li and LCO/MCMB cell were cycled.*?respectively')],
    'Peng_09': [('E1', r'It is concluded that the electrochemical property.*?on the anode\.')],
}


def read(path):
    return json.loads(path.read_bytes())


def references(text, cases):
    result = {}
    for case in cases:
        start = case['question_span']['end']
        following = re.search(r'^#{1,3}\s', text[start:], re.M)
        end = start + following.start() if following else len(text)
        marker = re.search(r'\*\*Эталонный ответ:\*\*', text[start:end])
        if marker is None:
            raise ValueError('Missing committed reference marker')
        left = start + marker.end()
        if not text[left:end].strip():
            raise ValueError('Empty reference')
        result[case['id']] = {'start': left, 'end': end, 'text': text[left:end],
                              'scientific_validation': 'user_declared_self_authored; not independently verified'}
    return result


def main():
    closed = read(run.BASE / 'scope_closed_v01.json')
    if closed['remaining_allowance'] != 0 or len(closed['cases']) != 30:
        raise ValueError('References stay closed until all thirty allowances close')
    run.fixed_version()
    commit = read(run.BASE / 'input_freeze_v01/reference_commitment.json')
    raw = Path(commit['input_path']).read_bytes()
    if f.sha(raw) != commit['input_sha256']:
        raise ValueError('Reference document changed after pre-inference commitment')
    text = raw.decode('utf-8-sig')
    cases = run.cases()
    ref = references(text, cases)
    output = run.BASE / 'review_v01'
    output.mkdir(exist_ok=False)
    rows, anchors, counts, totals, bindings = [], [], Counter(), Counter(), [Path(__file__),
        run.BASE / 'input_freeze_v01/manifest.json', run.BASE / 'approval_v01.json', run.BASE / 'scope_closed_v01.json',
        run.BASE / 'identity_v02/manifest.json', run.BASE / 'source_review_v01/manifest.json']
    for case in cases:
        cid = case['id']
        prepared, live = run.BASE / 'prepared_v01' / cid, run.BASE / 'live' / cid
        f.verify_manifest(prepared)
        f.verify_manifest(live)
        contract, result = read(prepared / 'contract.json'), read(live / 'result.json')
        row = {'id': cid, 'question': case['question_original'], 'actual_question': case['question'],
            'reference': ref[cid], 'preparation_status': contract['preparation_status'], 'result': result,
            'api_response': None, 'assessment': None, 'score': None, 'scientific_accuracy': None}
        if result['model_attempts']:
            api = read(live / 'api_response.json')
            row['api_response'] = api
            body = api['body']
            if api['http_status'] == 200:
                row['assessment'] = {'category': NOTES[cid][0], 'note': NOTES[cid][1],
                                     'reviewer': 'implementation_agent_posthoc_not_independent_expert'}
                counts[body['answer']['status']] += 1
                counts['guard:' + body['delivery_status']] += 1
                if (live / 'request.json').read_bytes() != (prepared / 'request.json').read_bytes():
                    raise ValueError('Actual native differs from frozen input')
                if body['review'] is None:
                    raise ValueError('Actual model result has no guard review')
                native = read(live / 'response.bin')
                choice, = native['choices']
                if choice['finish_reason'] != 'stop' or json.loads(choice['message']['content']) != {
                        k: body['review']['native_result'][k] for k in ('answerable', 'claims')}:
                    raise ValueError('Native answer changed or was incomplete')
                prompt = read(live / 'request.json')['messages'][1]['content']
                evidence_start = prompt.index('\n\nEvidence:\n\n') + len('\n\nEvidence:\n\n')
                sources = {e['citation_id']: e for e in body['review']['evidence']}
                for source in sources.values():
                    if _clean_generation_evidence_text(source['text']) not in prompt[evidence_start:]:
                        raise ValueError('Actual prompt lacks unchanged raw source')
                for eid, pattern in PATTERNS[cid]:
                    source = sources[eid]
                    matches = list(re.finditer(pattern, source['text'], re.S))
                    if len(matches) != 1:
                        raise ValueError('Source witness ambiguous/missing for ' + cid + '/' + eid)
                    m = matches[0]
                    quote = _clean_generation_evidence_text(m[0])
                    at = prompt.find(quote, evidence_start)
                    if at < 0:
                        raise ValueError('Raw witness absent from actual Evidence section')
                    anchors.append({'id': cid, 'citation_id': eid, 'article_id': source['article_id'],
                        'chunk_id': source['chunk_id'], 'page_range': [source['page_start'], source['page_end']],
                        'raw_text_sha256': f.sha(source['text'].encode()), 'raw_start': m.start(), 'raw_end': m.end(),
                        'raw_text': m[0], 'actual_prompt_start': at, 'actual_prompt_end': at + len(quote), 'actual_text': quote})
                for key, value in native['usage'].items():
                    totals[key] += value
            else:
                counts['api_error'] += 1
            slot = run.LEDGER / contract['request_sha256']
            if read(slot / 'result.json') != result or not read(slot / 'closed.json')['allowance_closed']:
                raise ValueError('Slot result/closure differs')
            bindings.extend([slot / 'result.json', slot / 'closed.json'])
        else:
            counts[result['status']] += 1
            row['api_response'] = read(prepared / 'preparation_api_response.json') if (
                prepared / 'preparation_api_response.json').exists() else None
        row['scope'] = read(prepared / 'scope.json')
        row['gate_metadata'] = read(prepared / 'trace.json')['metadata']
        row['reference_lookup'] = read(prepared / 'trace.json')['retrieval']['metadata'].get('explicit_source_reference')
        rows.append(row)
        bindings.extend([prepared / 'manifest.json', live / 'manifest.json'])
    report = {'cases': rows, 'counts': dict(counts), 'usage': dict(totals), 'source_witnesses': anchors,
        'actual_model_attempts': sum(r['result']['model_attempts'] for r in rows),
        'actual_oauth_attempts': sum(r['result']['oauth_attempts'] for r in rows), 'remaining_allowance': 0,
        'reference_commitment': commit, 'references_opened_only_after_closure': True,
        'rubric': 'user-supplied proposal, not automatically adopted; numeric scores null',
        'independent_scientific_accuracy': None, 'cost': None, 'bindings': f.bindings(bindings)}
    f.write(output / 'report.json', report)
    esc = html.escape
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — Kondo/Nambu/Peng</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:8px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'section{border:1px solid #abc;margin:18px 0;padding:12px}</style><h1>Новые30 вопросов: зафиксированная версия</h1>'
        '<p>6actual model POST/OAuth;17исходных отказов до модели;7отдельных остановок по области статьи. '
        'Все лимиты закрыты. Это6полученных ответов, а не6научно правильных. Guard: not_evaluated для всех6.</p>'
        '<p>Эталоны: пользователь заявил самостоятельную подготовку без LLM; hash зафиксирован до ответов, '
        'содержимое открыто только после закрытия. Проверка ниже post-hoc, не независимая научная приёмка.</p>'
        '<table><tr><th>ID</th><th>Вопрос</th><th>Результат</th><th>Сверка</th></tr>')
    for row in rows:
        note = row['assessment']['note'] if row['assessment'] else ('Запрос не отправлялся: ' + row['preparation_status'])
        body += '<tr><td><a href="#' + esc(row['id']) + '">' + esc(row['id']) + '</a></td><td>'
        body += esc(row['question']) + '</td><td>' + esc(row['result']['status']) + '</td><td>' + esc(note) + '</td></tr>'
    body += '</table>'
    for row in rows:
        case = next(c for c in cases if c['id'] == row['id'])
        body += '<section id="' + esc(row['id']) + '"><h2>' + esc(row['id']) + '</h2><p>' + esc(row['question']) + '</p>'
        body += '<p><a href="' + esc(Path(case['original_pdf_path']).as_uri(), quote=True) + '">Оригинальный PDF</a></p>'
        body += '<h3>Исходный ответ/доставка API</h3><pre>' + esc(json.dumps(row['api_response'], ensure_ascii=False, indent=2)) + '</pre>'
        body += '<h3>Присланный эталон и указатель</h3><pre>' + esc(row['reference']['text']) + '</pre>'
        if row['assessment']:
            body += '<p>' + esc(row['assessment']['note']) + '</p>'
        body += '<details><summary>Область, причины отказа, разрешение ссылки</summary><pre>' + esc(json.dumps(
            {'scope': row['scope'], 'reference_lookup': row['reference_lookup'], 'metadata': row['gate_metadata']},
            ensure_ascii=False, indent=2)) + '</pre></details>'
        for anchor in [a for a in anchors if a['id'] == row['id']]:
            body += '<details><summary>Точная цитата ' + esc(anchor['citation_id']) + ' · PDF range '
            body += esc(str(anchor['page_range'])) + '</summary><pre>' + esc(anchor['raw_text']) + '</pre></details>'
        for folder, name in ((run.BASE / 'prepared_v01' / row['id'], 'trace.json'),
                             (run.BASE / 'live' / row['id'], 'result.json'),
                             (run.BASE / 'live' / row['id'], 'response.bin')):
            path = folder / name
            if path.exists():
                body += '<p><a href="' + esc(path.as_uri(), quote=True) + '">' + esc(name) + '</a></p>'
        body += '</section>'
    body += '<p>Native usage: ' + esc(str(dict(totals))) + '; стоимость неизвестна. '
    body += 'Код и источники не менялись после новых вопросов. Новые источники не объявляются независимыми от разработки.</p></html>'
    f.save(output / 'review.html', body.encode())
    f.manifest(output)
    print(json.dumps({'cases': len(rows), 'counts': dict(counts), 'model_attempts': report['actual_model_attempts'],
                      'oauth_attempts': report['actual_oauth_attempts'], 'usage': dict(totals), 'anchors': len(anchors)}))


if __name__ == '__main__':
    policy = f.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    main()
