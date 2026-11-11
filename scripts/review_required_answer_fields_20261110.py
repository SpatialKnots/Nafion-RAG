"""Closed-scope native/field replay and exposed source review; no new inference."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from app.generation.fact_types import Anchor, verify_anchor
from app.generation.providers import Evidence, GeneratedClaim, _clean_generation_evidence_text
from app.generation.required_answer_fields import check, validate
from scripts import gigachat_answer_smoke as f
from scripts.run_required_answer_fields_20261110 import BASE, LEDGER, PARENT, SELECTED

NOTES = {
    "Satoh_07": "Целевой статус сохранён: соединения не идентифицированы, алкоксиды названы предполагаемыми.",
    "Fan_05": "LiF теперь назван. Причинная связь не установлена конечной картой, но модель всё равно утверждает "
        "механизм через плотность/стабильность SEI. Такой ответ требует удержания/ручной проверки; native не исправлен.",
    "Satoh_06": "EC–TFEME/EC–TFEMEE сохранены. Ответ стал короче: прежние 60%/30 циклов опущены. "
        "Сам вопрос просит влияние на эффективность, без явного численного значения; полного сохранения детализации нет.",
    "Fan_10": "Добавлена общая масса катода и анода; ограничение после 125 циклов сохранено. "
        "В новом тексте не повторены Li/NMC811 и однократный избыток Li; полнота вне проверенных полей не установлена.",
    "Satoh_03": "Добавлена плотность TFEME 1.1508×10³ кг/м³ при 25°C; EME 0.8472×10³ сохранена. "
        "Термин снова «трифторирование». Формулировка «после ... образуется TFEME» не установлена картой "
        "как реальный синтетический маршрут: отношения карты — буквальное сравнение, не доказательство химической идентичности.",
}


def read(path):
    return json.loads(path.read_bytes())


def main():
    freeze = BASE / "input_freeze_v01"
    f.verify_manifest(freeze)
    f.verify(read(freeze / "bindings.json"))
    if read(BASE / "closed_v01.json")["remaining_allowance"] != 0:
        raise ValueError("Scope must be closed")
    rows, witnesses, usage, bindings = [], [], {}, [Path(__file__), freeze / "manifest.json", BASE / "closed_v01.json"]
    for _, cid in SELECTED:
        live, prepared = BASE / "live" / cid, freeze / cid
        f.verify_manifest(live)
        f.verify_manifest(BASE / "diagnostics" / cid)
        inp, plan = read(prepared / "input.json"), read(prepared / "requirements.json")
        evidence = [Evidence(**e) for e in inp["evidence"]]
        source_map = {e.citation_id: e for e in evidence}
        validate(plan, inp["question"], evidence)
        native, result, parsed = read(live / "response.bin"), read(live / "result.json"), read(live / "provider_result.json")
        if (live / "request.json").read_bytes() != (prepared / "request.json").read_bytes():
            raise ValueError("Native differs from frozen candidate")
        choice, = native["choices"]
        if choice["finish_reason"] != "stop" or json.loads(choice["message"]["content"]) != {
                k: parsed[k] for k in ("answerable", "claims")}:
            raise ValueError("Incomplete or modified native answer")
        checked = check(inp["question"], [GeneratedClaim(**c) for c in parsed["claims"]], evidence)
        if checked != read(BASE / "diagnostics" / cid / "check.json"):
            raise ValueError("Field audit replay differs")
        prompt = json.loads((live / "request.json").read_bytes())["messages"][1]["content"]
        anchors = [o['anchor'] for r in plan['requirements'] for o in r['observations']]
        anchors += [r['anchor'] for r in plan['relations']]
        for item in anchors:
            anchor = Anchor(**item)
            verify_anchor(anchor, source_map[anchor.citation_id])
            raw = _clean_generation_evidence_text(anchor.text)
            offset = prompt.find(raw)
            if offset < 0:
                raise ValueError("Required-field witness absent from native raw-evidence prompt")
            witnesses.append({"id": cid, "anchor": item, "actual_prompt_start": offset,
                              "actual_prompt_end": offset + len(raw), "actual_text": raw})
        slot = LEDGER / inp['request_sha256']
        if read(slot / "result.json") != result or not read(slot / "answer_instruction_pilot_closed_v01.json")['allowance_closed']:
            raise ValueError("New scoped ledger closure mismatch")
        if result['model_attempts'] != 1 or result['oauth_attempts'] != 1 or result['network_denials']:
            raise ValueError("Transport budget/network failure")
        for key, value in native['usage'].items():
            usage[key] = usage.get(key, 0) + value
        rows.append({"id": cid, "question": inp['question'], "historical_baseline": read(prepared / 'historical_baseline.json'),
            "new_provider_result": parsed, "required_field_check": checked, "review_note": NOTES[cid],
            "prior_request_identical": (prepared / 'baseline_request.json').read_bytes() == (live / 'request.json').read_bytes(),
            "diagnostic_projection": "would_withhold_unresolved_fields" if plan['status'] == 'mapped'
                and checked['decision'] == 'required_fields_unresolved' else 'no_field_veto_not_scientific_acceptance',
            "projection_is_actual_API_result": False, "scientific_accuracy": None,
            "reviewer": "exposed_implementation_assistant_posthoc", "returned_model": native['model']})
        bindings.extend([live / 'manifest.json', BASE / 'diagnostics' / cid / 'manifest.json', slot / 'result.json',
                         PARENT / 'live' / cid / 'manifest.json'])
    output = BASE / 'review_v01'
    output.mkdir(exist_ok=False)
    report = {'cases': rows, 'source_witnesses': witnesses, 'model_calls': 5, 'oauth_calls': 5,
              'remaining_allowance': 0, 'usage': usage, 'cost': None, 'independent_accuracy': None,
              'scope': 'historical baseline/finite source-bound fields; no general entailment or API acceptance',
              'bindings': f.bindings(bindings)}
    f.verify(report['bindings'])
    f.write(output / 'report.json', report)
    esc = html.escape
    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — обязательные поля</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:10px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
        '<h1>Обязательные поля: пять реальных попыток</h1><p>5 model POST + 5 OAuth, без повторов; лимит закрыт. '
        'Все ответы native сохранены. Критерий: два численных пропуска заполнены, два контроля сохраняют целевые '
        'свойства, Fan05 остаётся незакрытым. Это не общая scientific accuracy. Диагностическое удержание — '
        'проекция, не фактический новый API отказ.</p><table><thead><tr><th>Вопрос</th><th>Было</th><th>Стало</th>'
        '<th>Сверка</th></tr></thead><tbody>')
    markdown = '# Обязательные поля: повторный прогон\n\n|Вопрос|Сверка|\n|---|---|\n'
    for row in rows:
        body += '<tr><td>' + esc(row['id']) + '</td>'
        for claims in (row['historical_baseline']['claims'], row['new_provider_result']['claims']):
            body += '<td>' + ''.join('<p>' + esc(c['text']) + ' [' + esc(', '.join(c['citation_ids'])) + ']</p>'
                                     for c in claims) + '</td>'
        body += '<td>' + esc(row['review_note']) + '</td></tr>'
        markdown += '|' + row['id'] + '|' + row['review_note'] + '|\n'
    body += '</tbody></table>'
    for row in rows:
        body += '<section><h2>' + esc(row['id']) + '</h2><p>' + esc(row['question']) + '</p>'
        body += '<details><summary>Карта и проверки</summary><pre>' + esc(json.dumps(
            row['required_field_check'], ensure_ascii=False, indent=2)) + '</pre></details>'
        inp = read(freeze / row['id'] / 'input.json')
        body += '<details><summary>Полные исходные источники</summary>'
        for e in inp['evidence']:
            body += '<h3>' + esc(e['citation_id']) + ' · PDF range ' + str(e['page_start']) + '–' + str(e['page_end'])
            body += '</h3><pre>' + esc(e['text']) + '</pre>'
        body += '</details>'
        for name in ('request.json', 'response.bin', 'provider_result.json', 'result.json'):
            body += '<p><a href="' + esc((BASE / 'live' / row['id'] / name).as_uri(), quote=True) + '">' + name + '</a></p>'
        body += '</section>'
    body += '<p>Native usage: ' + esc(str(usage)) + '. Стоимость неизвестна. Основной режим не включён.</p></html>'
    markdown += '\nЭто конечные проверки полей, не научная приёмка; новые причинные/синтетические утверждения не подтверждены.\n'
    f.save(output / 'review.html', body.encode())
    f.save(output / 'comparison.md', markdown.encode())
    f.manifest(output)
    print(json.dumps({'cases': 5, 'model_calls': 5, 'oauth_calls': 5, 'usage': usage,
                      'source_witness_observations': len(witnesses), 'remaining_allowance': 0}))


if __name__ == '__main__':
    policy = f.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    main()
